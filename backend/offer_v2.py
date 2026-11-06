"""Local-only synthetic Offer operating cycle, with deterministic launch authority.

No platform, channel, model, certificate provider, bank or buyer API is called.
The configuration/release boundary is reusable behind the proposed Nexus gateway;
this fixture is neither a production deployment nor sponsor acceptance.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / 'fixtures/offer_v2.json'
TABLES = ('v2_offer_reconciliations', 'v2_offer_feedback', 'v2_offer_batches', 'v2_offer_events',
          'v2_offer_releases', 'v2_offer_tests', 'v2_offer_configs', 'v2_offers')
TEST_SCENARIOS = ('healthy', 'failed_verification', 'missing_mapping', 'unknown_outcome')
BATCH_SCENARIOS = ('mixed_quality', 'all_qualified')
FEEDBACK_SCENARIOS = ('buyer_outcomes', 'return_dispute')


class StaleOfferAction(ValueError):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def fixture():
    return json.loads(FIXTURE.read_text())


def ensure_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS v2_offers(
      id TEXT PRIMARY KEY,version INTEGER NOT NULL,status TEXT NOT NULL,config_sha TEXT NOT NULL,
      latest_test_id TEXT,active_release_id TEXT,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS v2_offer_configs(
      sha256 TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),version INTEGER NOT NULL,
      payload TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(offer_id,version));
    CREATE TABLE IF NOT EXISTS v2_offer_tests(
      id TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),config_version INTEGER NOT NULL,
      config_sha TEXT NOT NULL,scenario TEXT NOT NULL,status TEXT NOT NULL,evidence TEXT NOT NULL,
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS v2_offer_releases(
      id TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),config_version INTEGER NOT NULL,
      config_sha TEXT NOT NULL,test_id TEXT NOT NULL REFERENCES v2_offer_tests(id),owner TEXT NOT NULL,
      note TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(offer_id,test_id));
    CREATE TABLE IF NOT EXISTS v2_offer_events(
      event_id TEXT PRIMARY KEY,request_sha TEXT NOT NULL,kind TEXT NOT NULL,result_id TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS v2_offer_batches(
      id TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),release_id TEXT NOT NULL REFERENCES v2_offer_releases(id),
      config_sha TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS v2_offer_feedback(
      id TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),batch_id TEXT NOT NULL REFERENCES v2_offer_batches(id),
      payload TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS v2_offer_reconciliations(
      id TEXT PRIMARY KEY,offer_id TEXT NOT NULL REFERENCES v2_offers(id),batch_id TEXT NOT NULL REFERENCES v2_offer_batches(id),
      feedback_id TEXT NOT NULL REFERENCES v2_offer_feedback(id),payload TEXT NOT NULL,created_at TEXT NOT NULL);
    ''')


def ensure_seed(c):
    """Call under Workflow's transaction after settings/reset, never from a GET."""
    data = fixture();now_row = c.execute("SELECT value FROM settings WHERE key='now'").fetchone()
    if not now_row:
        raise ValueError('Initialize the synthetic clock before Offer seed')
    now = json.loads(now_row[0])
    config = deepcopy(data['config']);reference = sha(config)
    c.execute("INSERT OR IGNORE INTO v2_offers VALUES(?,1,'configuration_ready',?,NULL,NULL,?)",
              (data['offer_id'], reference, now))
    c.execute('INSERT OR IGNORE INTO v2_offer_configs VALUES(?,?,1,?,?)',
              (reference, data['offer_id'], encode(config), now))


def _decimal(value):
    if not isinstance(value, str) or len(value) > 24:
        raise ValueError('Money must be a decimal string')
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('Invalid money') from exc
    if not number.is_finite() or number < 0 or number > Decimal('1000000') or number.as_tuple().exponent < -2:
        raise ValueError('Money must be finite, nonnegative, within fixture range and at most two decimals')
    return number


def validate_config(config):
    for name in ('revenue_cpl', 'payout_cpl'):
        _decimal(config[name])
    if _decimal(config['revenue_cpl']) <= 0:
        raise ValueError('Positive advertiser revenue required')
    for name in ('daily_cap', 'channel_capacity'):
        if type(config[name]) is not int or not 1 <= config[name] <= 500:
            raise ValueError('Synthetic cap/capacity must be integer 1–500')
    for name in ('terms_approved', 'mapping_approved', 'channel_approved'):
        if type(config[name]) is not bool:
            raise ValueError('Readiness approval flags must be explicit booleans')
    for name in ('mapping_version', 'postback_event', 'terms_version'):
        if not isinstance(config[name], str) or not 1 <= len(config[name]) <= 100:
            raise ValueError('Nonempty bounded terms/mapping/event references required')


def margin(config):
    revenue = _decimal(config['revenue_cpl']);payout = _decimal(config['payout_cpl'])
    value = (revenue - payout) / revenue * 100
    return format(value, 'f')


def blockers(config):
    problems = []
    if not config['terms_approved']: problems.append('BD approved terms missing')
    if not config['mapping_approved']: problems.append('AdOps mapping approval missing')
    if not config['channel_approved']: problems.append('AM channel placement approval missing')
    if config['daily_cap'] > config['channel_capacity']: problems.append('Placement cap exceeds AM confirmed synthetic capacity')
    if Decimal(margin(config)) < Decimal(config['margin_floor_pct']): problems.append('Synthetic base CPL margin below configured floor')
    return problems


class OfferService:
    def __init__(self, workflow):
        self.w = workflow

    def _offer(self, c, offer_id):
        row = c.execute('SELECT * FROM v2_offers WHERE id=?', (offer_id,)).fetchone()
        if row is None: raise ValueError('Unknown synthetic Offer')
        return dict(row)

    def _config(self, c, offer):
        row = c.execute('SELECT payload FROM v2_offer_configs WHERE sha256=?', (offer['config_sha'],)).fetchone()
        return json.loads(row[0])

    def pricing_preview(self, offer_id, advertiser_price):
        price = _decimal(advertiser_price)
        if price <= 0:
            raise ValueError('Positive advertiser price required')
        with self.w.db() as c:
            c.execute('BEGIN')
            offer = self._offer(c, offer_id)
            config = self._config(c, offer)
        price_text = format(price, '.2f')
        preview_margin = margin({**config, 'revenue_cpl': price_text})
        floor = config['margin_floor_pct']
        return {
            'config_version': offer['version'],
            'currency': config['currency'],
            'advertiser_price': price_text,
            'channel_payout': format(_decimal(config['payout_cpl']), '.2f'),
            'margin_pct': preview_margin,
            'margin_floor_pct': floor,
            'clears_floor': Decimal(preview_margin) >= Decimal(floor),
        }

    def _version(self, offer, expected_version):
        if type(expected_version) is not int or expected_version < 1: raise ValueError('Positive configuration version required')
        if offer['version'] != expected_version: raise StaleOfferAction('Offer configuration changed; refresh exact version')

    def _replay(self, c, event_id, request):
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 200:
            raise ValueError('Stable event ID of 1–200 characters required')
        prior = c.execute('SELECT * FROM v2_offer_events WHERE event_id=?', (event_id,)).fetchone()
        if prior and prior['request_sha'] != sha(request): raise StaleOfferAction('Event identity conflicts with retained request')
        return prior is not None

    def _record(self, c, event_id, request, kind, result_id):
        c.execute('INSERT INTO v2_offer_events VALUES(?,?,?,?)', (event_id, sha(request), kind, result_id))

    def _now(self, c):
        return self.w._get(c, 'now')

    def _delivered_today(self, c, offer_id):
        return sum(json.loads(r[0])['qualified_delivered'] for r in c.execute(
            'SELECT payload FROM v2_offer_batches WHERE offer_id=? AND substr(created_at,1,10)=?',
            (offer_id, self._now(c)[:10])))

    def _current_release(self, c, offer):
        if offer['status'] != 'released_simulated' or not offer['active_release_id']:
            return False
        release = c.execute('SELECT * FROM v2_offer_releases WHERE id=?', (offer['active_release_id'],)).fetchone()
        if not release or release['config_sha'] != offer['config_sha'] or release['config_version'] != offer['version']:
            return False
        test = c.execute('SELECT * FROM v2_offer_tests WHERE id=?', (release['test_id'],)).fetchone()
        if not test or test['id'] != offer['latest_test_id'] or test['status'] != 'passed':
            return False
        evidence = json.loads(test['evidence'])
        return (evidence.get('status') == 'passed' and evidence.get('config_sha256') == offer['config_sha']
                and evidence.get('adapter_rule_version') == fixture()['rules_version'])

    def configure(self, offer_id, expected_version, change, event_id):
        allowed = {'revenue_cpl', 'payout_cpl', 'daily_cap', 'mapping_version', 'postback_event',
                   'channel_capacity', 'terms_approved', 'mapping_approved', 'channel_approved'}
        if not isinstance(change, dict) or not change or set(change) - allowed:
            raise ValueError('Only explicit synthetic commercial, capacity and mapping fields may change')
        request = ['configure', offer_id, expected_version, change]
        with self.w.tx() as c:
            if self._replay(c, event_id, request): return self.state(c)
            offer = self._offer(c, offer_id);self._version(offer, expected_version)
            config = self._config(c, offer);candidate = {**config, **deepcopy(change)}
            validate_config(candidate)
            material = candidate != config
            if material:
                version = offer['version'] + 1
                candidate['configuration_version'] = version
                if set(change) & {'revenue_cpl', 'payout_cpl'}:
                    candidate['terms_version'] = f'SYN-TERMS-{version}'
                reference = sha(candidate)
                c.execute('INSERT INTO v2_offer_configs VALUES(?,?,?,?,?)', (reference, offer_id, version, encode(candidate), self._now(c)))
                c.execute("UPDATE v2_offers SET version=?,status='configuration_changed',config_sha=?,latest_test_id=NULL,active_release_id=NULL,updated_at=? WHERE id=?",
                          (version, reference, self._now(c), offer_id))
                self.w._audit(c, 'v2_offer_configuration_changed', offer_id, version=version, configuration_sha256=reference,
                              old_evidence_and_release_invalidated=True, simulated_only=True)
            self._record(c, event_id, request, 'configure', offer_id)
            return self.state(c)

    def test(self, offer_id, expected_version, scenario, event_id):
        if scenario not in TEST_SCENARIOS: raise ValueError('Choose an allowlisted mock platform scenario')
        request = ['test', offer_id, expected_version, scenario]
        with self.w.tx() as c:
            if self._replay(c, event_id, request): return self.state(c)
            offer = self._offer(c, offer_id);self._version(offer, expected_version);config = self._config(c, offer)
            problems = blockers(config)
            if scenario == 'failed_verification': problems.append('Mock postback verification failed')
            if scenario == 'missing_mapping': problems.append('Mock platform mapping readback absent')
            if scenario == 'unknown_outcome': problems.append('Mock platform outcome unknown; owner investigation required')
            status = 'passed' if not problems else 'unknown' if scenario == 'unknown_outcome' else 'failed'
            test_id = 'VT-' + sha([request, event_id])[:16]
            evidence = {'label': 'Synthetic mock platform test; no external verification', 'offer_id': offer_id,
                        'config_version': offer['version'], 'config_sha256': offer['config_sha'],
                        'adapter': 'Everflow CPL mock', 'adapter_rule_version': fixture()['rules_version'],
                        'adapter_rules_sha256': sha({'version': fixture()['rules_version'], 'gate': 'exact config + approved base terms + current mappings + capacity + synthetic margin'}),
                        'checks': {'terms_and_mapping': not any('approval' in p or 'terms' in p for p in problems),
                                   'click_to_sub_id': scenario != 'missing_mapping',
                                   'postback_round_trip': scenario not in ('failed_verification', 'unknown_outcome'),
                                   'margin_pct': margin(config), 'margin_scope': 'Base CPL only; full-cost production definition unresolved'},
                        'problems': problems, 'status': status, 'recorded_at': self._now(c),
                        'request_timeout_tested': False, 'external_calls': 0}
            c.execute('INSERT INTO v2_offer_tests VALUES(?,?,?,?,?,?,?,?)',
                      (test_id, offer_id, offer['version'], offer['config_sha'], scenario, status, encode(evidence), self._now(c)))
            c.execute('UPDATE v2_offers SET status=?,latest_test_id=?,active_release_id=NULL,updated_at=? WHERE id=?',
                      ('sandbox_passed' if status == 'passed' else 'sandbox_' + status, test_id, self._now(c), offer_id))
            self._record(c, event_id, request, 'test', test_id)
            self.w._audit(c, 'v2_mock_sandbox_test', offer_id, test_id=test_id, configuration_sha256=offer['config_sha'], status=status, external_effect=False)
            return self.state(c)

    def release(self, offer_id, expected_version, test_id, note, event_id):
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000: raise ValueError('Owner verification note required')
        request = ['release', offer_id, expected_version, test_id, note]
        with self.w.tx() as c:
            if self._replay(c, event_id, request): return self.state(c)
            offer = self._offer(c, offer_id);self._version(offer, expected_version);config = self._config(c, offer)
            test = c.execute('SELECT * FROM v2_offer_tests WHERE id=? AND offer_id=?', (test_id, offer_id)).fetchone()
            if (test is None or test['id'] != offer['latest_test_id'] or test['status'] != 'passed'
                    or test['config_sha'] != offer['config_sha'] or test['config_version'] != offer['version'] or blockers(config)):
                raise StaleOfferAction('Release requires the latest successful mock test of this exact approved configuration')
            evidence = json.loads(test['evidence'])
            if evidence['adapter_rule_version'] != fixture()['rules_version']:
                raise StaleOfferAction('Adapter rules changed; re-test before release')
            release_id = 'VR-' + sha([offer_id, test_id])[:16]
            c.execute('INSERT OR IGNORE INTO v2_offer_releases VALUES(?,?,?,?,?,?,?,?)',
                      (release_id, offer_id, offer['version'], offer['config_sha'], test_id, fixture()['owners']['launch'], note.strip(), self._now(c)))
            c.execute("UPDATE v2_offers SET status='released_simulated',active_release_id=?,updated_at=? WHERE id=?", (release_id, self._now(c), offer_id))
            self._record(c, event_id, request, 'release', release_id)
            self.w._audit(c, 'v2_owner_release_recorded', offer_id, release_id=release_id, test_id=test_id,
                          configuration_sha256=offer['config_sha'], owner=fixture()['owners']['launch'], external_effect=False, sponsor_acceptance=False)
            return self.state(c)

    def run_batch(self, offer_id, expected_version, scenario, event_id):
        if scenario not in BATCH_SCENARIOS: raise ValueError('Choose an allowlisted synthetic lead batch')
        request = ['run_batch', offer_id, expected_version, scenario]
        with self.w.tx() as c:
            if self._replay(c, event_id, request): return self.state(c)
            offer = self._offer(c, offer_id);self._version(offer, expected_version);config = self._config(c, offer)
            if not self._current_release(c, offer) or blockers(config):
                raise StaleOfferAction('Synthetic placement requires a current exact-version owner release')
            rows = deepcopy(fixture()['batch_leads'])
            if scenario == 'all_qualified':
                for row in rows: row.update(certificate='SYN-CERT', phone_verified=True, geo_match=True)
            batch_id = 'VB-' + sha([request, event_id])[:16]
            prior_delivered = self._delivered_today(c, offer_id)
            qualified = 0
            for row in rows:
                row['fixture_lead_id'] = row['lead_id']
                row['lead_id'] += '-' + batch_id[-8:]
                reasons = []
                if not row['certificate']: reasons.append('synthetic consent certificate missing')
                if not row['phone_verified']: reasons.append('synthetic phone verification failed')
                if not row['geo_match']: reasons.append('outside synthetic approved geography')
                if prior_delivered + qualified >= config['daily_cap']: reasons.append('synthetic UTC-day Offer cap reached')
                if prior_delivered + qualified >= config['channel_capacity']: reasons.append('synthetic UTC-day AM capacity reached')
                row.update(qualification='rejected' if reasons else 'qualified', reasons=reasons,
                           delivery_status='not_delivered' if reasons else 'mock_buyer_accepted',
                           generated_at=self._now(c), delivered_at=None if reasons else self._now(c),
                           advertiser_id=fixture()['advertiser']['id'], channel_id=fixture()['channel']['id'],
                           sub_id=fixture()['channel']['sub_id'])
                if not reasons: qualified += 1
            payload = {'label': 'Synthetic lead intake, qualification and mock buyer delivery', 'rows': rows,
                       'received': len(rows), 'qualified_delivered': qualified, 'rejected': len(rows) - qualified,
                       'revenue_cpl': config['revenue_cpl'], 'payout_cpl': config['payout_cpl'],
                       'prior_UTC_day_delivered': prior_delivered,
                       'remaining_channel_capacity': max(config['channel_capacity'] - prior_delivered - qualified, 0),
                       'hygiene_latency_measured': False, 'real_consent_validation': False, 'external_calls': 0}
            c.execute('INSERT INTO v2_offer_batches VALUES(?,?,?,?,?,?)',
                      (batch_id, offer_id, offer['active_release_id'], offer['config_sha'], encode(payload), self._now(c)))
            self._record(c, event_id, request, 'batch', batch_id)
            self.w._audit(c, 'v2_synthetic_offer_delivery', offer_id, batch_id=batch_id, qualified=qualified, rejected=len(rows)-qualified, external_effect=False)
            return self.state(c)

    def _finance_feedback(self, c, offer_id, batch_id):
        # A retained dispute remains the effective Finance evidence until a
        # decision exists. Older demo databases may contain later ordinary feedback.
        latest = None
        for row in c.execute(
            'SELECT * FROM v2_offer_feedback WHERE offer_id=? AND batch_id=? ORDER BY rowid DESC',
            (offer_id, batch_id),
        ):
            if latest is None:
                latest = row
            if json.loads(row['payload'])['status'] == 'finance_review_required':
                return row
        return latest

    def feedback(self, offer_id, batch_id, scenario, event_id):
        if scenario not in FEEDBACK_SCENARIOS: raise ValueError('Choose an allowlisted synthetic buyer outcome scenario')
        request = ['feedback', offer_id, batch_id, scenario]
        with self.w.tx() as c:
            if self._replay(c, event_id, request): return self.state(c)
            self._offer(c, offer_id)
            batch = c.execute('SELECT * FROM v2_offer_batches WHERE id=? AND offer_id=?', (batch_id, offer_id)).fetchone()
            if batch is None: raise ValueError('Unknown Offer batch')
            if scenario == 'buyer_outcomes':
                # An ordinary outcome fixture cannot adjudicate a disputed return.
                prior = self._finance_feedback(c, offer_id, batch_id)
                if prior and json.loads(prior['payload'])['status'] == 'finance_review_required':
                    raise StaleOfferAction('This batch has a Finance-owned return dispute; ordinary outcomes cannot clear the hold')
            delivered = [r for r in json.loads(batch['payload'])['rows'] if r['delivery_status'] == 'mock_buyer_accepted']
            if not delivered: raise ValueError('No delivered synthetic leads for outcome feedback')
            rows = [{'lead_id': row['lead_id'], 'connected': True, 'appointment': index == 0, 'closed_won': index == 0,
                     'return_requested': scenario == 'return_dispute' and index == 0,
                     'status': 'disputed_pending_finance' if scenario == 'return_dispute' and index == 0 else 'buyer_confirmed_accepted',
                     'evidence': 'Synthetic buyer feedback; no CRM read'} for index, row in enumerate(delivered)]
            feedback_id = 'VF-' + sha([request, event_id])[:16]
            payload = {'label': 'Synthetic buyer quality and sales outcomes', 'rows': rows,
                       'status': 'finance_review_required' if scenario == 'return_dispute' else 'complete_fixture_feedback',
                       'open_billing_rules': fixture()['open_rules'] if scenario == 'return_dispute' else [],
                       'evidence_sha256': sha(rows), 'external_calls': 0}
            c.execute('INSERT INTO v2_offer_feedback VALUES(?,?,?,?,?)', (feedback_id, offer_id, batch_id, encode(payload), self._now(c)))
            self._record(c, event_id, request, 'feedback', feedback_id)
            self.w._audit(c, 'v2_buyer_feedback_recorded', offer_id, feedback_id=feedback_id, batch_id=batch_id, billing_mutated=False, routing_mutated=False)
            return self.state(c)

    def reconcile(self, offer_id, batch_id, expected_feedback_id, note, event_id):
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000: raise ValueError('Finance evidence review note required')
        if not isinstance(expected_feedback_id, str) or not 1 <= len(expected_feedback_id) <= 100:
            raise ValueError('Exact reviewed buyer-feedback ID required')
        request = ['reconcile', offer_id, batch_id, expected_feedback_id, note]
        with self.w.tx() as c:
            if self._replay(c, event_id, request): return self.state(c)
            self._offer(c, offer_id)
            batch = c.execute('SELECT * FROM v2_offer_batches WHERE id=? AND offer_id=?', (batch_id, offer_id)).fetchone()
            feedback = self._finance_feedback(c, offer_id, batch_id)
            if batch is None or feedback is None: raise ValueError('Current delivered batch and buyer feedback are required')
            if feedback['id'] != expected_feedback_id:
                raise StaleOfferAction('Buyer feedback changed or is held; review the exact current Finance evidence')
            info = json.loads(batch['payload']);facts = json.loads(feedback['payload'])
            disputed = any(r['return_requested'] for r in facts['rows'])
            count = len(facts['rows'])
            reconciliation_id = 'VREC-' + sha([offer_id, batch_id, feedback['id']])[:16]
            payload = {'label': 'Synthetic provisional Offer reconciliation; no invoice or payout instruction',
                       'status': 'blocked_rules_decision' if disputed else 'reviewed_fixture',
                       'owner': fixture()['owners']['finance'], 'note': note.strip(), 'delivered_count': count,
                       'buyer_confirmed_count': sum(r['status'] == 'buyer_confirmed_accepted' for r in facts['rows']),
                       'provisional_receivable_usd': None if disputed else format(_decimal(info['revenue_cpl']) * count, '.2f'),
                       'provisional_channel_cost_usd': None if disputed else format(_decimal(info['payout_cpl']) * count, '.2f'),
                       'source_batch_sha256': sha(info), 'source_feedback_sha256': sha(facts),
                       'blocked_by': fixture()['open_rules'] if disputed else [],
                       'next_action': 'Finance/commercial owner must resolve conflicting return rules before financial treatment' if disputed else 'Finance owner reviewed fixture totals; actual settlement remains separate',
                       'payment_enabled': False, 'routing_change_enabled': False}
            c.execute('INSERT OR IGNORE INTO v2_offer_reconciliations VALUES(?,?,?,?,?,?)',
                      (reconciliation_id, offer_id, batch_id, feedback['id'], encode(payload), self._now(c)))
            self._record(c, event_id, request, 'reconcile', reconciliation_id)
            self.w._audit(c, 'v2_offer_finance_review', offer_id, reconciliation_id=reconciliation_id, status=payload['status'], payment_enabled=False)
            return self.state(c)

    def state(self, c=None):
        if c is None:
            with self.w.db() as opened: return self.state(opened)
        data = fixture();offer = self._offer(c, data['offer_id']);config = self._config(c, offer)
        release_current = self._current_release(c, offer)
        offer.update(config=config, margin_pct=margin(config), blockers=blockers(config), owners=data['owners'],release_current=release_current,
                     next_action='Record exact-version sandbox evidence' if offer['latest_test_id'] is None else
                     'Owner may release this exact passed configuration' if offer['status'] == 'sandbox_passed' else
                     'Place a synthetic batch, collect buyer outcomes and review quality/capacity' if offer['status'] == 'released_simulated' else
                     'AdOps owner resolves failed/unknown verification; re-test before release')
        if offer['status'] == 'released_simulated' and not release_current:
            offer['next_action'] = 'Adapter evidence outdated: AdOps must re-test and owner re-release exact configuration'
        configs = [dict(r) for r in c.execute('SELECT * FROM v2_offer_configs ORDER BY version')]
        for row in configs: row['payload'] = json.loads(row['payload'])
        collections = {}
        finance_feedback = {}
        for key, table, field in [('tests','v2_offer_tests','evidence'), ('releases','v2_offer_releases',None),
                                  ('batches','v2_offer_batches','payload'), ('feedback','v2_offer_feedback','payload'),
                                  ('reconciliations','v2_offer_reconciliations','payload')]:
            rows = [dict(r) for r in c.execute(f'SELECT * FROM {table} ORDER BY rowid')]
            for row in rows:
                if field: row[field] = json.loads(row[field])
                if key in ('feedback', 'reconciliations'):
                    batch_config = c.execute('SELECT config_sha FROM v2_offer_batches WHERE id=?', (row['batch_id'],)).fetchone()
                    row['current_configuration'] = bool(batch_config and batch_config[0] == offer['config_sha'])
                else:
                    row['current_configuration'] = row.get('config_sha', offer['config_sha']) == offer['config_sha']
                if key in ('feedback', 'reconciliations'):
                    batch_key = row['offer_id'], row['batch_id']
                    if batch_key not in finance_feedback:
                        effective = self._finance_feedback(c, *batch_key)
                        finance_feedback[batch_key] = effective['id'] if effective else None
                    if key == 'feedback':
                        row['current_for_finance'] = finance_feedback[batch_key] == row['id']
                if key == 'reconciliations':
                    row['current_feedback'] = finance_feedback[batch_key] == row['feedback_id']
                    row['effective_status'] = row['payload']['status'] if row['current_feedback'] else 'historical_feedback_superseded'
                    row['next_action'] = row['payload']['next_action'] if row['current_feedback'] else 'Buyer feedback changed; finance owner must review the new feedback version'
            collections[key] = rows
        recommendations = []
        capacity_delivered = self._delivered_today(c, offer['id'])
        capacity_available = max(config['channel_capacity'] - capacity_delivered, 0) if release_current else None
        capacity_window = {'date_utc': self._now(c)[:10], 'observed_at': self._now(c),
                           'configured_daily_capacity': config['channel_capacity'], 'server_counted_delivered': capacity_delivered,
                           'config_sha256': offer['config_sha'], 'available': capacity_available,
                           'scope': 'This synthetic Offer/channel UTC day only; not verified live S/A inventory'}
        quality_capacity = {'status': 'no_placement_or_feedback', 'quality_known': False, 'counts': None,
                            'quality_window': None, 'capacity_window': capacity_window,
                            'available_channel_capacity': capacity_available}
        if collections['batches']:
            latest_batch = collections['batches'][-1];payload = latest_batch['payload']
            matching_feedback = [f for f in collections['feedback']
                                 if f['batch_id'] == latest_batch['id'] and f['current_for_finance']]
            quality = matching_feedback[-1]['payload'] if matching_feedback else None
            current = latest_batch['config_sha'] == offer['config_sha'] and release_current
            quality_rows = quality['rows'] if quality else []
            count = len(quality_rows)
            quality_capacity = {'status': 'historical_revalidation_required' if not current else 'awaiting_buyer_feedback' if not quality else quality['status'],
                                'quality_known': bool(quality and current), 'batch_id': latest_batch['id'],
                                'counts': {'delivered': payload['qualified_delivered'], 'rejected_at_intake': payload['rejected'],
                                           'buyer_feedback': count, 'connected': None if quality is None else sum(r['connected'] for r in quality_rows),
                                           'appointments': None if quality is None else sum(r['appointment'] for r in quality_rows),
                                           'closed_won': None if quality is None else sum(r['closed_won'] for r in quality_rows)},
                                'quality_window': {'batch_observed_at': latest_batch['created_at'],
                                                   'buyer_feedback_observed_at': matching_feedback[-1]['created_at'] if matching_feedback else None,
                                                   'scope': 'Exact historical synthetic batch, not current-day capacity or a seven-day quality cohort'},
                                'capacity_window': capacity_window,
                                'contact_rate_pct': None if not count else format(Decimal(sum(r['connected'] for r in quality_rows)) / Decimal(count) * 100, 'f'),
                                'sales_close_rate_pct': None if not count else format(Decimal(sum(r['closed_won'] for r in quality_rows)) / Decimal(count) * 100, 'f'),
                                'denominator': 'Mock delivered leads in this exact batch with complete allowlisted buyer feedback; not a seven-day company cohort',
                                'available_channel_capacity': capacity_available,
                                'capacity_scope': 'Synthetic confirmed UTC-day channel capacity less server-counted deliveries',
                                'evidence_sha256': None if quality is None else quality['evidence_sha256']}
            recommendations = [
                {'role':'BD','owner':data['owners']['bd'],'action':'Use quality plus AM confirmed spare capacity as negotiation evidence; no automatic repricing',
                 'quality_evidence':None if quality is None else quality['evidence_sha256'],'available_channel_capacity':capacity_available},
                {'role':'AM','owner':data['owners']['am'],'action':'Review rejected intake and confirm channel capacity before any expansion',
                 'rejected_count':payload['rejected'],'next_check':'Named owner review, synthetic cadence not adopted'},
                {'role':'AdOps','owner':data['owners']['adops'],'action':'Review qualification and buyer outcomes; propose route change only after current mapping/authority checks',
                 'delivery_evidence':sha(payload),'route_mutation_enabled':False}]
            for recommendation in recommendations:
                recommendation['current_configuration'] = current
                recommendation['quality_known'] = bool(quality and current)
                recommendation['quality_capacity_evidence'] = quality_capacity
                if quality is None and current:
                    recommendation['action'] = 'Buyer quality is unknown: collect buyer feedback before using quality as negotiation or routing evidence'
                elif quality and quality['status'] == 'finance_review_required' and current:
                    recommendation['action'] = 'Return treatment unresolved: finance/commercial owner reviews before pricing, payout or route changes'
                if not current:
                    recommendation['action'] = 'Historical quality/capacity only: revalidate against current configuration and release before use'
                    if 'available_channel_capacity' in recommendation: recommendation['available_channel_capacity'] = None
        return {'label':data['label'],'offer':offer,'advertiser':data['advertiser'],'channel':data['channel'],
                'config_versions':configs,**collections,'recommendations':recommendations,'quality_capacity':quality_capacity,
                'scenarios':{'test':list(TEST_SCENARIOS),'batch':list(BATCH_SCENARIOS),'feedback':list(FEEDBACK_SCENARIOS)},
                'adapter_contract':{'gateway':'Nexus deterministic service boundary; Dify cannot call native writes',
                                    'CPL':'Mock EF-01/02/04 configuration, mapping and postback verification',
                                    'call':'Future RB-01/02 number/target mapping and duration qualification, separate adapter; no number bought',
                                    'production_contract_verified':False},
                'open_rules':data['open_rules'],'effects':{'external_effects':False,'model_calls':0,'live_platform_calls':0,
                                                        'pricing_change_enabled':False,'payout_enabled':False,'production_launch_enabled':False},
                'limitations':['All approvals, tests, buyer outcomes and capacity are synthetic; no real credentials/provider verification',
                               'Local SQLite does not verify PostgreSQL or durable worker deployment',
                               'Production provisioning, hygiene throughput and trial acceptance remain unverified']}
