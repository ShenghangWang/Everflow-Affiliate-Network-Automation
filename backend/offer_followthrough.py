"""Offer-scoped commercial review and AM follow-through over synthetic evidence."""
from datetime import datetime, timedelta, timezone
import json

from .offer_v2 import OfferService, StaleOfferAction, encode, sha


FRESHNESS = timedelta(hours=24)
REVIEW_INTERVAL = timedelta(hours=24)
EVIDENCE_RULES = 'synthetic-offer-followthrough-v1'
TABLES = (
    'v2_offer_am_steps',
    'v2_offer_am_actions',
    'v2_offer_proposal_reviews',
    'v2_offer_proposals',
    'v2_offer_followthrough_evidence',
)


def ensure_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS v2_offer_followthrough_evidence(
      sha256 TEXT PRIMARY KEY,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS v2_offer_proposals(
      id TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),owner TEXT NOT NULL,
      evidence_sha256 TEXT NOT NULL REFERENCES v2_offer_followthrough_evidence(sha256),
      approved_clauses TEXT NOT NULL,requested_terms TEXT NOT NULL,created_at TEXT NOT NULL,
      UNIQUE(offer_id,evidence_sha256,requested_terms));
    CREATE TABLE IF NOT EXISTS v2_offer_proposal_reviews(
      proposal_id TEXT PRIMARY KEY REFERENCES v2_offer_proposals(id),note TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS v2_offer_am_actions(
      id TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),
      batch_id TEXT NOT NULL REFERENCES v2_offer_batches(id),kind TEXT NOT NULL,
      owner TEXT NOT NULL,next_action TEXT NOT NULL,created_at TEXT NOT NULL,
      UNIQUE(offer_id,batch_id,kind));
    CREATE TABLE IF NOT EXISTS v2_offer_am_steps(
      action_id TEXT NOT NULL REFERENCES v2_offer_am_actions(id),version INTEGER NOT NULL,
      status TEXT NOT NULL,evidence_sha256 TEXT NOT NULL REFERENCES v2_offer_followthrough_evidence(sha256),
      note TEXT,next_review_at TEXT,created_at TEXT NOT NULL,PRIMARY KEY(action_id,version));
    ''')


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Offer evidence requires a timezone-aware timestamp')
    return result.astimezone(timezone.utc)


def valid_text(value, limit, label):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ValueError(f'{label} of 1–{limit} characters required')
    return value.strip()


def valid_version(version):
    if type(version) is not int or version < 1:
        raise ValueError('Positive record version required')


def approved_clauses(config):
    return (
        f"Offer: {config['offer_name']} ({config['model']}).\n"
        f"Advertiser price: {config['currency']} {config['revenue_cpl']} per qualified lead.\n"
        f"Daily cap: {config['daily_cap']} qualified leads per UTC day.\n"
        f"Approved synthetic terms: {config['terms_version']}."
    )


def evidence_status(facts, status, reason, *, bd_ready=False, am_ready=False):
    return {
        **facts,
        'sha256': sha(facts) if bd_ready or am_ready else None,
        'status': status,
        'reason': reason,
        'bd_ready': bd_ready,
        'am_ready': am_ready,
    }


class OfferFollowthrough:
    def __init__(self, workflow):
        self.w = workflow
        self.offers = OfferService(workflow)

    def _context(self, c, offer_id):
        state = self.offers.state(c)
        offer = state['offer']
        if offer['id'] != offer_id:
            raise ValueError('Unknown synthetic Offer')
        return offer, self._evidence(state, timestamp(self.w._get(c, 'now')))

    def _evidence(self, state, now):
        offer = state['offer']
        scope = {'advertiser_id': state['advertiser']['id'], 'offer_id': offer['id'],
                 'channel_id': state['channel']['id'], 'sub_id': state['channel']['sub_id']}
        facts = {'scope': scope, 'rules_version': EVIDENCE_RULES, 'config_version': offer['version'],
                 'config_sha': offer['config_sha'], 'release_id': offer['active_release_id'],
                 'batch_id': None, 'batch_sha256': None, 'batch_observed_at': None,
                 'feedback_id': None, 'feedback_sha256': None, 'feedback_observed_at': None,
                 'quality': None, 'capacity': None}
        if not offer['release_current'] or offer['blockers']:
            return evidence_status(facts, 'unavailable', 'Release the exact current Offer configuration first.')
        batches = [batch for batch in state['batches'] if batch['offer_id'] == offer['id']]
        if not batches:
            return evidence_status(facts, 'unavailable', 'Run a synthetic delivery batch before follow-through.')
        batch = batches[-1]
        if batch['release_id'] != offer['active_release_id'] or batch['config_sha'] != offer['config_sha']:
            return evidence_status(facts, 'stale', 'The latest delivery batch belongs to an earlier release. Run a batch for this release.')
        rows = batch['payload']['rows']
        if not rows or any(any(row.get(key) != scope[key] for key in ('advertiser_id', 'channel_id', 'sub_id')) for row in rows):
            return evidence_status(facts, 'stale', 'Delivery evidence does not match the advertiser, Offer and channel scope.')
        quality_capacity = state['quality_capacity']
        capacity = quality_capacity['capacity_window']
        if (quality_capacity.get('batch_id') != batch['id'] or capacity['config_sha256'] != offer['config_sha']
                or capacity['date_utc'] != now.date().isoformat() or capacity['available'] is None):
            return evidence_status(facts, 'stale', 'Quality and current UTC day capacity must match the exact Offer configuration.')
        facts.update(batch_id=batch['id'], batch_sha256=sha(batch['payload']), batch_observed_at=batch['created_at'],
                     quality=quality_capacity['counts'],
                     capacity={key: value for key, value in capacity.items() if key not in ('observed_at', 'scope')})
        feedback = next((item for item in state['feedback']
                         if item['batch_id'] == batch['id'] and item['offer_id'] == offer['id']
                         and item['current_for_finance']), None)
        if feedback:
            payload = feedback['payload']
            facts.update(feedback_id=feedback['id'], feedback_sha256=sha(payload), feedback_observed_at=feedback['created_at'])
            if payload['status'] == 'finance_review_required' or any(row['return_requested'] for row in payload['rows']):
                return evidence_status(facts, 'finance_hold', 'Finance owns this disputed return. BD and AM decisions are held.')
            delivered = [row['lead_id'] for row in rows if row['delivery_status'] == 'mock_buyer_accepted']
            observed = [row['lead_id'] for row in payload['rows']]
            if (payload['status'] != 'complete_fixture_feedback' or not delivered or sorted(delivered) != sorted(observed)
                    or len(set(observed)) != len(observed) or payload['evidence_sha256'] != sha(payload['rows'])):
                return evidence_status(facts, 'stale', 'Buyer outcomes must cover the exact delivered lead IDs for this batch.')
        observed_times = [timestamp(batch['created_at'])]
        if feedback:
            observed_times.append(timestamp(feedback['created_at']))
        if any(not timedelta() <= now - observed <= FRESHNESS for observed in observed_times):
            return evidence_status(facts, 'stale', 'Synthetic batch and feedback evidence must be at most 24 hours old.')
        if feedback:
            return evidence_status(facts, 'ready', 'Current delivery, buyer outcomes and UTC day capacity are available.',
                                   bd_ready=True, am_ready=True)
        if facts['quality']['rejected_at_intake']:
            return evidence_status(facts, 'delivery_evidence', 'AM can review intake rejections. BD awaits complete buyer feedback.', am_ready=True)
        return evidence_status(facts, 'unavailable', 'Await complete buyer feedback before a proposal or AM action.')

    def _expect(self, evidence, expected_sha, readiness):
        if not evidence[readiness]:
            raise StaleOfferAction(evidence['reason'])
        if expected_sha != evidence['sha256']:
            raise StaleOfferAction('Offer evidence changed. Review the exact current evidence before recording a decision.')

    def _retain(self, c, evidence):
        c.execute('INSERT OR IGNORE INTO v2_offer_followthrough_evidence VALUES(?,?)',
                  (evidence['sha256'], encode(evidence)))

    def prepare(self, offer_id, expected_evidence_sha, requested_terms, event_id):
        request = ['offer_bd_prepare', offer_id, expected_evidence_sha, requested_terms]
        requested_terms = valid_text(requested_terms, 4000, 'Requested terms')
        with self.w.tx() as c:
            if self.offers._replay(c, event_id, request):
                return self.state(offer_id, c)
            offer, evidence = self._context(c, offer_id)
            self._expect(evidence, expected_evidence_sha, 'bd_ready')
            self._retain(c, evidence)
            proposal_id = 'VBD-' + sha([offer_id, evidence['sha256'], requested_terms])[:20]
            inserted = c.execute('INSERT OR IGNORE INTO v2_offer_proposals VALUES(?,?,?,?,?,?,?)',
                                 (proposal_id, offer_id, offer['owners']['bd'], evidence['sha256'],
                                  approved_clauses(offer['config']), requested_terms, self.w._get(c, 'now')))
            if inserted.rowcount:
                self.w._audit(c, 'offer_bd_proposal_prepared', offer_id, proposal_id=proposal_id,
                              evidence_sha256=evidence['sha256'], dispatch_enabled=False)
            self.offers._record(c, event_id, request, 'offer_bd_prepare', proposal_id)
            return self.state(offer_id, c)

    def review(self, offer_id, proposal_id, expected_evidence_sha, expected_version, note, event_id):
        request = ['offer_bd_review', offer_id, proposal_id, expected_evidence_sha, expected_version, note]
        valid_version(expected_version)
        note = valid_text(note, 2000, 'BD review note')
        with self.w.tx() as c:
            if self.offers._replay(c, event_id, request):
                return self.state(offer_id, c)
            offer, evidence = self._context(c, offer_id)
            self._expect(evidence, expected_evidence_sha, 'bd_ready')
            proposal = c.execute('SELECT * FROM v2_offer_proposals WHERE id=? AND offer_id=?', (proposal_id, offer_id)).fetchone()
            if proposal is None:
                raise ValueError('Unknown synthetic Offer proposal')
            if (proposal['evidence_sha256'] != expected_evidence_sha
                    or proposal['approved_clauses'] != approved_clauses(offer['config']) or expected_version != 1):
                raise StaleOfferAction('Proposal version, scope or approved evidence changed. Prepare a current proposal for review.')
            prior = c.execute('SELECT note FROM v2_offer_proposal_reviews WHERE proposal_id=?', (proposal_id,)).fetchone()
            if prior is not None and prior['note'] != note:
                raise StaleOfferAction('This exact proposal has already been reviewed.')
            if prior is None:
                c.execute('INSERT INTO v2_offer_proposal_reviews VALUES(?,?,?)', (proposal_id, note, self.w._get(c, 'now')))
                self.w._audit(c, 'offer_bd_proposal_reviewed', offer_id, proposal_id=proposal_id,
                              evidence_sha256=expected_evidence_sha, commercial_approval=False)
            self.offers._record(c, event_id, request, 'offer_bd_review', proposal_id)
            return self.state(offer_id, c)

    def _am_step(self, c, action_id):
        return c.execute('SELECT * FROM v2_offer_am_steps WHERE action_id=? ORDER BY version DESC LIMIT 1', (action_id,)).fetchone()

    def open_action(self, offer_id, expected_evidence_sha, event_id):
        request = ['offer_am_open', offer_id, expected_evidence_sha]
        with self.w.tx() as c:
            if self.offers._replay(c, event_id, request):
                return self.state(offer_id, c)
            offer, evidence = self._context(c, offer_id)
            self._expect(evidence, expected_evidence_sha, 'am_ready')
            if evidence['quality']['rejected_at_intake']:
                kind = 'delivery_rejection'
                next_action = 'Inspect synthetic intake rejection reasons with the channel and record the operational follow-up.'
            else:
                kind = 'buyer_outcome_review'
                next_action = 'Review the observed buyer outcomes with the channel and record the operational follow-up.'
            action_id = 'VAM-' + sha([offer_id, evidence['batch_id'], kind])[:20]
            now = self.w._get(c, 'now')
            c.execute('INSERT OR IGNORE INTO v2_offer_am_actions VALUES(?,?,?,?,?,?,?)',
                      (action_id, offer_id, evidence['batch_id'], kind, offer['owners']['am'], next_action, now))
            step = self._am_step(c, action_id)
            if step is None or (step['status'] == 'open' and step['evidence_sha256'] != expected_evidence_sha):
                version = 1 if step is None else step['version'] + 1
                self._retain(c, evidence)
                c.execute("INSERT INTO v2_offer_am_steps VALUES(?,?,'open',?,NULL,NULL,?)",
                          (action_id, version, expected_evidence_sha, now))
                self.w._audit(c, 'offer_am_action_opened' if version == 1 else 'offer_am_action_evidence_refreshed', offer_id,
                              action_id=action_id, version=version, evidence_sha256=expected_evidence_sha)
            self.offers._record(c, event_id, request, 'offer_am_open', action_id)
            return self.state(offer_id, c)

    def resolve(self, offer_id, action_id, expected_evidence_sha, expected_version, note, event_id):
        request = ['offer_am_resolve', offer_id, action_id, expected_evidence_sha, expected_version, note]
        valid_version(expected_version)
        note = valid_text(note, 2000, 'AM resolution note')
        with self.w.tx() as c:
            if self.offers._replay(c, event_id, request):
                return self.state(offer_id, c)
            _, evidence = self._context(c, offer_id)
            self._expect(evidence, expected_evidence_sha, 'am_ready')
            action = c.execute('SELECT * FROM v2_offer_am_actions WHERE id=? AND offer_id=?', (action_id, offer_id)).fetchone()
            if action is None:
                raise ValueError('Unknown synthetic Offer AM action')
            step = self._am_step(c, action_id)
            if step is None or step['evidence_sha256'] != expected_evidence_sha or action['batch_id'] != evidence['batch_id']:
                raise StaleOfferAction('AM action scope or evidence changed. Open or refresh the current action before resolving it.')
            if step['status'] == 'open' and step['version'] == expected_version:
                now = self.w._get(c, 'now')
                due = (timestamp(now) + REVIEW_INTERVAL).isoformat()
                c.execute("INSERT INTO v2_offer_am_steps VALUES(?,?,'resolved',?,?,?,?)",
                          (action_id, expected_version + 1, expected_evidence_sha, note, due, now))
                self.w._audit(c, 'offer_am_action_resolved', offer_id, action_id=action_id, evidence_sha256=expected_evidence_sha,
                              next_review_at=due, outcome_improvement_verified=False)
            elif not (step['status'] == 'resolved' and step['version'] == expected_version + 1 and step['note'] == note):
                raise StaleOfferAction('AM action version changed or the resolution is already recorded.')
            self.offers._record(c, event_id, request, 'offer_am_resolve', action_id)
            return self.state(offer_id, c)

    def state(self, offer_id, c=None):
        if c is None:
            with self.w.db() as opened:
                opened.execute('BEGIN')
                return self.state(offer_id, opened)
        _, evidence = self._context(c, offer_id)
        retained = {row['sha256']: json.loads(row['payload']) for row in c.execute('SELECT * FROM v2_offer_followthrough_evidence')}
        proposals = []
        for row in c.execute('SELECT * FROM v2_offer_proposals WHERE offer_id=? ORDER BY rowid', (offer_id,)):
            proposal = dict(row)
            review = c.execute('SELECT * FROM v2_offer_proposal_reviews WHERE proposal_id=?', (proposal['id'],)).fetchone()
            reference = proposal['evidence_sha256']
            proposal.update(version=2 if review else 1, status='reviewed' if review else 'pending_review',
                            current=evidence['bd_ready'] and evidence['sha256'] == reference, evidence=retained[reference],
                            review={'owner': proposal['owner'], 'note': review['note'], 'created_at': review['created_at'],
                                    'evidence_sha256': reference} if review else None)
            proposals.append(proposal)
        actions = []
        now = timestamp(self.w._get(c, 'now'))
        latest_resolution = c.execute('''
            SELECT steps.action_id FROM v2_offer_am_steps steps
            JOIN v2_offer_am_actions actions ON actions.id=steps.action_id
            WHERE actions.offer_id=? AND steps.status='resolved' ORDER BY steps.rowid DESC LIMIT 1
        ''', (offer_id,)).fetchone()
        for row in c.execute('SELECT * FROM v2_offer_am_actions WHERE offer_id=? ORDER BY rowid', (offer_id,)):
            action = dict(row)
            history = [dict(step) for step in c.execute('SELECT * FROM v2_offer_am_steps WHERE action_id=? ORDER BY version', (action['id'],))]
            latest = history[-1]
            reference = latest['evidence_sha256']
            due = latest['next_review_at']
            resolved = latest['status'] == 'resolved'
            schedule_active = resolved and latest_resolution['action_id'] == action['id']
            for step in history:
                step['evidence'] = retained[step['evidence_sha256']]
            action.update(version=latest['version'], status=latest['status'],
                          current=evidence['am_ready'] and evidence['sha256'] == reference,
                          evidence_sha256=reference, evidence=retained[reference], history=history,
                          resolution={'owner': action['owner'], 'note': latest['note'], 'created_at': latest['created_at'],
                                      'evidence_sha256': reference} if resolved else None,
                          next_review_at=due, review_schedule_active=schedule_active,
                          review_due=schedule_active and timestamp(due) <= now)
            if resolved:
                action['next_action'] = 'Review new delivery and buyer evidence at the next synthetic cadence.'
            actions.append(action)
        return {'evidence': evidence, 'proposals': proposals, 'am_actions': actions}
