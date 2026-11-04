"""Unsent proposal preparation with notes separated from approved terms.

This local owner review is not commercial approval, a signature or dispatch.
There is no language-model generation in binding sections.
"""
import json
from .reconciliation import digest

TABLES = ('commercial_decisions', 'commercial_events', 'commercial_drafts')
RULES = {'version': 'synthetic-proposal-v1', 'owner': 'Demo commercial owner',
         'note_policy': 'Every meeting note is an unverified request; never copy into binding draft clauses'}


def ensure_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS commercial_drafts(
      id TEXT PRIMARY KEY,lead_id TEXT NOT NULL REFERENCES leads(id),version INTEGER NOT NULL,
      status TEXT NOT NULL,owner TEXT NOT NULL,note TEXT NOT NULL,bound_facts TEXT NOT NULL,
      content TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS commercial_events(event_id TEXT PRIMARY KEY,request_sha TEXT NOT NULL,draft_id TEXT NOT NULL REFERENCES commercial_drafts(id));
    CREATE TABLE IF NOT EXISTS commercial_decisions(
      id TEXT PRIMARY KEY,draft_id TEXT NOT NULL REFERENCES commercial_drafts(id),bound_version INTEGER NOT NULL,
      note TEXT NOT NULL,evidence TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);
    ''')


def render(facts):
    terms = facts['terms']
    # No meeting note, profile or arbitrary model prose is accepted by this renderer.
    return ('Synthetic affiliate proposal — unsent draft, not an agreement\n'
            f"Approved fixture offer: {terms['offer_id']}\n"
            f"Payout: {terms['currency']} {terms['payout']} per {terms['billable_event']}.\n"
            f"Settlement: {terms['settlement']}.\nTraffic: {terms['traffic']}.\n"
            f"Bound approved terms: {terms['version']}\n"
            'Requested exceptions in meeting notes are excluded. Any change requires a new approved structured terms version.\n'
            'Commercial/legal approval, signature and dispatch are separate unimplemented effects.')


class CommercialService:
    def __init__(self, workflow): self.w = workflow

    def facts(self, c, lead):
        return {'lead_id': lead['id'], 'lead_version': lead['version'], 'recipient': lead['recipient'],
                'terms': self.w._get(c, 'terms'), 'rules': RULES}

    def eligible(self, lead):
        return not lead['suppressed'] and lead['stage'] == 'handoff' and lead['score'] >= 80

    def prepare(self, lead_id, meeting_note, event_id):
        if not isinstance(meeting_note, str) or not 1 <= len(meeting_note.strip()) <= 4000:
            raise ValueError('A meeting note of 1–4000 characters is required')
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 200:
            raise ValueError('Stable proposal event ID required')
        request = digest([lead_id, meeting_note])
        with self.w.tx() as c:
            previous = c.execute('SELECT * FROM commercial_events WHERE event_id=?', (event_id,)).fetchone()
            if previous:
                if previous['request_sha'] != request: raise ValueError('Proposal event conflicts with its retained original')
                return self.state(c)
            lead = self.w._lead(c, lead_id)
            if not self.eligible(lead): raise ValueError('Proposal requires an eligible, unsuppressed owned BD handoff')
            facts = self.facts(c, lead)
            key = 'PRP-' + digest([request, facts])[:16]
            c.execute("INSERT OR IGNORE INTO commercial_drafts VALUES(?,?,1,'owner_review',?,?,?,?,?)",
                      (key, lead_id, RULES['owner'], meeting_note, json.dumps(facts, sort_keys=True), render(facts), self.w._get(c, 'now')))
            c.execute('INSERT INTO commercial_events VALUES(?,?,?)', (event_id, request, key))
            self.w._audit(c, 'proposal_prepared_for_owner', lead_id, draft_id=key, owner=RULES['owner'],
                          terms_version=facts['terms']['version'], note_trusted_as_terms=False, external_effect=False)
            return self.state(c)

    def review(self, draft_id, expected_version, note, evidence):
        if type(expected_version) is not int or expected_version < 1: raise ValueError('Positive draft version required')
        if not all(isinstance(v, str) and 1 <= len(v.strip()) <= 2000 for v in (note, evidence)):
            raise ValueError('Owner review note and evidence required')
        with self.w.tx() as c:
            row = c.execute('SELECT * FROM commercial_drafts WHERE id=?', (draft_id,)).fetchone()
            if row is None: raise ValueError('Unknown proposal')
            lead = self.w._lead(c, row['lead_id']);facts = json.loads(row['bound_facts'])
            if row['version'] != expected_version or row['status'] != 'owner_review': raise ValueError('Draft changed or already reviewed')
            if not self.eligible(lead) or facts != self.facts(c, lead) or row['content'] != render(facts):
                raise ValueError('Terms, source, rules or draft changed; prepare current evidence before review')
            c.execute('INSERT INTO commercial_decisions VALUES(?,?,?,?,?,?,?)',
                      ('PDEC-' + digest([draft_id, expected_version])[:16], draft_id, expected_version, note.strip(), evidence.strip(),
                       'Synthetic local commercial reviewer', self.w._get(c, 'now')))
            c.execute("UPDATE commercial_drafts SET status='reviewed_draft',version=version+1 WHERE id=?", (draft_id,))
            self.w._audit(c, 'proposal_owner_review_recorded', row['lead_id'], draft_id=draft_id, owner=row['owner'],
                          verification=evidence.strip(), contract_approved=False, signature_enabled=False, dispatch_enabled=False)
            return self.state(c)

    def state(self, c=None):
        if c is None:
            with self.w.db() as opened: return self.state(opened)
        drafts = []
        for row in c.execute('SELECT * FROM commercial_drafts ORDER BY rowid'):
            item = dict(row);facts = json.loads(item['bound_facts']);lead = self.w._lead(c, item['lead_id'])
            item['bound_facts'] = facts
            item['evidence_sha256'] = digest(facts)
            item['blocked'] = not self.eligible(lead) or facts != self.facts(c, lead) or item['content'] != render(facts)
            item['next_action'] = 'Prepare current draft; earlier review is historical' if item['blocked'] else ('Commercial/legal approval and signature remain separate' if item['status'] == 'reviewed_draft' else 'Review approved clauses and requested changes; record evidence')
            drafts.append(item)
        return {'drafts': drafts, 'decisions': [dict(r) for r in c.execute('SELECT * FROM commercial_decisions ORDER BY rowid')],
                'rules': RULES, 'effects': {'external_effects': False, 'model_calls': 0, 'dispatch_enabled': False,
                                           'signature_enabled': False, 'terms_change_enabled': False},
                'limitations': ['Meeting notes remain unverified requests, including numbers, spelled-out prices and instructions',
                                'Synthetic local review is not authenticated commercial/legal approval or signed onboarding']}
