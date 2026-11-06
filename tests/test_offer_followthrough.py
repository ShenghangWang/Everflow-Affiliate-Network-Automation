from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from backend.domain import Workflow
from backend.offer_followthrough import OfferFollowthrough
from backend.offer_v2 import OfferService, StaleOfferAction, encode


OFFER = 'OFR-SYN-1'
SCOPE = {'advertiser_id': 'ADV-SYN-1', 'offer_id': OFFER, 'channel_id': 'CH-SYN-1', 'sub_id': 'SUB-SYN-1'}
REQUEST = 'Advertiser requests USD 12.34, Net 7 and a fifty percent bonus.'


class OfferFollowthroughTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'offer-followthrough.sqlite3'
        self.w = Workflow(self.path)
        self.offers = OfferService(self.w)
        self.follow = OfferFollowthrough(self.w)
        self.sequence = 0
        self.release()

    def event(self):
        self.sequence += 1
        return f'FOLLOW-{self.sequence}'

    def release(self):
        version = self.offers.state()['offer']['version']
        state = self.offers.test(OFFER, version, 'healthy', self.event())
        return self.offers.release(OFFER, version, state['offer']['latest_test_id'], 'Exact test evidence reviewed', self.event())

    def batch(self, scenario='mixed_quality'):
        version = self.offers.state()['offer']['version']
        state = self.offers.run_batch(OFFER, version, scenario, self.event())
        return state['batches'][-1]['id']

    def feedback(self, batch_id, scenario='buyer_outcomes'):
        return self.offers.feedback(OFFER, batch_id, scenario, self.event())['feedback'][-1]['id']

    def evidence(self):
        return self.follow.state(OFFER)['evidence']

    def prepare(self, digest, event=None):
        return self.follow.prepare(OFFER, digest, REQUEST, event or self.event())['proposals'][-1]

    def open_action(self, digest):
        return self.follow.open_action(OFFER, digest, self.event())['am_actions'][-1]

    def review(self, proposal, digest=None, note='Approved clauses and buyer outcomes reviewed', event=None):
        return self.follow.review(OFFER, proposal['id'], digest or proposal['evidence_sha256'], proposal['version'], note, event or self.event())

    def resolve(self, action, digest=None, note='Channel owner recorded a synthetic verification follow-up', event=None):
        return self.follow.resolve(OFFER, action['id'], digest or action['evidence_sha256'], action['version'], note, event or self.event())

    def test_delivery_issue_refreshes_once_and_bd_separates_requests_from_approved_terms(self):
        batch_id = self.batch()
        delivery = self.evidence()
        self.assertFalse(delivery['bd_ready'])
        self.assertTrue(delivery['am_ready'])
        self.assertEqual(delivery['scope'], SCOPE)
        self.assertIsNone(delivery['feedback_id'])
        self.assertIsNone(delivery['quality']['connected'])
        with self.assertRaises(StaleOfferAction):
            self.prepare(delivery['sha256'])
        action = self.open_action(delivery['sha256'])
        self.assertEqual(action['kind'], 'delivery_rejection')
        self.assertEqual(action['evidence']['scope'], SCOPE)
        self.assertIn('channel', action['next_action'])

        feedback_id = self.feedback(batch_id)
        current = self.evidence()
        self.assertEqual(current['feedback_id'], feedback_id)
        self.assertNotEqual(current['sha256'], delivery['sha256'])
        self.assertEqual(current['quality']['closed_won'], 1)
        self.assertEqual(current['capacity']['available'], 28)
        with self.assertRaises(StaleOfferAction):
            self.resolve(action)
        refreshed = self.open_action(current['sha256'])
        self.assertEqual(refreshed['id'], action['id'])
        self.assertEqual(refreshed['version'], 2)
        self.assertEqual(refreshed['history'][0]['evidence'], delivery)
        self.assertEqual(self.open_action(current['sha256']), refreshed)
        with self.assertRaises(StaleOfferAction):
            self.resolve(action, current['sha256'])

        proposal = self.prepare(current['sha256'])
        self.assertEqual(proposal['requested_terms'], REQUEST)
        self.assertIn('USD 40.00', proposal['approved_clauses'])
        for unapproved in ('12.34', 'Net 7', 'fifty'):
            self.assertNotIn(unapproved, proposal['approved_clauses'])
        self.assertEqual(self.prepare(current['sha256']), proposal)
        self.assertEqual(proposal['evidence'], current)
        reviewed = self.review(proposal)
        self.assertEqual(reviewed['proposals'][-1]['status'], 'reviewed')
        self.assertEqual(reviewed['proposals'][-1]['review']['evidence_sha256'], current['sha256'])
        self.assertEqual(self.review(proposal), reviewed)
        with self.assertRaises(StaleOfferAction):
            self.review(proposal, note='Different review attempts must not overwrite the recorded decision')
        resolved = self.resolve(refreshed)
        self.assertEqual(self.resolve(refreshed), resolved)
        self.assertEqual(len(resolved['am_actions']), 1)
        self.assertEqual(len(resolved['proposals']), 1)
        completed = resolved['am_actions'][0]
        self.assertEqual(completed['status'], 'resolved')
        self.assertEqual(len(completed['history']), 3)
        self.assertEqual(completed['resolution']['evidence_sha256'], current['sha256'])
        self.assertEqual(datetime.fromisoformat(completed['next_review_at']) - datetime.fromisoformat(completed['resolution']['created_at']), timedelta(hours=24))
        self.assertTrue(completed['review_schedule_active'])
        self.assertFalse(completed['review_due'])
        with self.w.db() as conn:
            for audit in ('offer_bd_proposal_prepared', 'offer_bd_proposal_reviewed', 'offer_am_action_opened', 'offer_am_action_resolved'):
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM audit WHERE event=?', (audit,)).fetchone()[0], 1)
        self.assertFalse(any(self.offers.state()['effects'].values()))

    def test_new_feedback_and_exact_release_require_a_fresh_proposal(self):
        batch_id = self.batch()
        self.feedback(batch_id)
        original = self.evidence()
        proposal = self.prepare(original['sha256'])
        self.feedback(batch_id)
        changed = self.evidence()
        self.assertNotEqual(changed['feedback_id'], original['feedback_id'])
        self.assertNotEqual(changed['sha256'], original['sha256'])
        with self.assertRaises(StaleOfferAction):
            self.review(proposal)
        with self.assertRaises(StaleOfferAction):
            self.review(proposal, changed['sha256'])
        replacement = self.prepare(changed['sha256'])
        self.assertNotEqual(replacement['id'], proposal['id'])
        self.review(replacement)
        self.release()
        stale = self.evidence()
        self.assertEqual(stale['status'], 'stale')
        self.assertNotEqual(stale['release_id'], changed['release_id'])
        self.assertEqual(stale['config_sha'], changed['config_sha'])
        self.assertIsNone(stale['sha256'])
        self.assertTrue(all(not item['current'] for item in self.follow.state(OFFER)['proposals']))
        with self.assertRaises(StaleOfferAction):
            self.prepare(changed['sha256'])

    def test_material_terms_change_and_event_conflict_preserve_old_review(self):
        self.feedback(self.batch())
        snapshot = self.evidence()
        event = self.event()
        proposal = self.prepare(snapshot['sha256'], event)
        self.assertEqual(self.prepare(snapshot['sha256'], event), proposal)
        with self.assertRaises(StaleOfferAction):
            self.follow.prepare(OFFER, snapshot['sha256'], 'Changed requested terms', event)
        self.review(proposal)
        self.offers.configure(OFFER, 1, {'revenue_cpl': '45.00'}, self.event())
        self.assertEqual(self.evidence()['status'], 'unavailable')
        self.release()
        self.feedback(self.batch())
        new = self.prepare(self.evidence()['sha256'])
        old, current = self.follow.state(OFFER)['proposals']
        self.assertFalse(old['current'])
        self.assertEqual(old['status'], 'reviewed')
        self.assertIn('USD 40.00', old['approved_clauses'])
        self.assertEqual(current, new)
        self.assertEqual(current['status'], 'pending_review')
        self.assertIn('USD 45.00', current['approved_clauses'])
        with self.assertRaises(StaleOfferAction):
            self.review(proposal, current['evidence_sha256'])

    def test_cross_batch_scope_and_fabricated_references_are_rejected(self):
        earlier_batch = self.batch()
        self.feedback(earlier_batch)
        older = self.evidence()
        earlier_action = self.open_action(older['sha256'])
        latest_batch = self.batch('all_qualified')
        no_feedback = self.evidence()
        self.assertEqual(no_feedback['batch_id'], latest_batch)
        self.assertIsNone(no_feedback['feedback_id'])
        self.assertFalse(no_feedback['bd_ready'])
        self.assertFalse(no_feedback['am_ready'])
        self.feedback(latest_batch)
        current = self.evidence()
        self.assertEqual(current['batch_id'], latest_batch)
        self.assertEqual(self.open_action(current['sha256'])['kind'], 'buyer_outcome_review')
        with self.assertRaises(StaleOfferAction):
            self.resolve(earlier_action, current['sha256'])
        with self.assertRaises(StaleOfferAction):
            self.prepare('forged-evidence')
        with self.assertRaisesRegex(ValueError, 'Unknown synthetic Offer'):
            self.follow.open_action('ANOTHER-OFFER', current['sha256'], self.event())
        with self.w.tx() as c:
            payload = json.loads(c.execute('SELECT payload FROM v2_offer_batches WHERE id=?', (latest_batch,)).fetchone()[0])
            payload['rows'][0]['sub_id'] = 'WRONG-SUB-ID'
            c.execute('UPDATE v2_offer_batches SET payload=? WHERE id=?', (encode(payload), latest_batch))
        self.assertEqual(self.evidence()['status'], 'stale')
        with self.assertRaises(StaleOfferAction):
            self.open_action(current['sha256'])

    def test_dispute_stays_with_finance_without_changing_prior_reviews(self):
        batch_id = self.batch()
        self.feedback(batch_id)
        snapshot = self.evidence()
        proposal = self.prepare(snapshot['sha256'])
        action = self.open_action(snapshot['sha256'])
        dispute = self.feedback(batch_id, 'return_dispute')
        held = self.evidence()
        self.assertEqual(held['status'], 'finance_hold')
        self.assertEqual(held['feedback_id'], dispute)
        self.assertFalse(held['bd_ready'])
        self.assertFalse(held['am_ready'])
        with self.assertRaises(StaleOfferAction):
            self.review(proposal)
        with self.assertRaises(StaleOfferAction):
            self.resolve(action)
        with self.assertRaises(StaleOfferAction):
            self.open_action(snapshot['sha256'])
        reconciled = self.offers.reconcile(OFFER, batch_id, dispute, 'Finance retains unresolved contract treatment', self.event())
        self.assertEqual(reconciled['reconciliations'][-1]['payload']['status'], 'blocked_rules_decision')
        self.assertIsNone(reconciled['reconciliations'][-1]['payload']['provisional_receivable_usd'])
        self.assertEqual(self.follow.state(OFFER)['am_actions'][0]['status'], 'open')
        self.assertIsNone(self.follow.state(OFFER)['proposals'][0]['review'])

    def test_freshness_capacity_schedule_and_history_survive_restart(self):
        self.feedback(self.batch())
        first = self.evidence()
        self.w.tick(1)
        self.assertEqual(self.evidence(), first)
        action = self.open_action(first['sha256'])
        self.resolve(action)
        self.w.tick(24)
        expired = self.follow.state(OFFER)
        self.assertEqual(expired['evidence']['status'], 'stale')
        self.assertFalse(expired['am_actions'][0]['current'])
        self.assertTrue(expired['am_actions'][0]['review_due'])
        self.assertEqual(OfferFollowthrough(Workflow(self.path)).state(OFFER), expired)
        with self.assertRaises(StaleOfferAction):
            self.prepare(first['sha256'])
        self.feedback(self.batch())
        current = self.evidence()
        self.assertNotEqual(current['capacity']['date_utc'], first['capacity']['date_utc'])
        next_action = self.open_action(current['sha256'])
        next_state = self.resolve(next_action)
        self.assertEqual(len(next_state['am_actions']), 2)
        previous, active = next_state['am_actions']
        self.assertFalse(previous['review_schedule_active'])
        self.assertFalse(previous['review_due'])
        self.assertIsNotNone(previous['next_review_at'])
        self.assertTrue(active['review_schedule_active'])
        self.assertFalse(active['review_due'])
        self.assertEqual(OfferFollowthrough(Workflow(self.path)).state(OFFER), next_state)
        self.w.reset()
        reset = self.follow.state(OFFER)
        self.assertFalse(reset['am_actions'])
        self.assertFalse(reset['proposals'])
