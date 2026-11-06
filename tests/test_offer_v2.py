from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.domain import Workflow
from backend.offer_v2 import OfferService, StaleOfferAction, sha, fixture


class OfferCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'offer-v2.sqlite3'
        self.w = Workflow(self.path);self.s = OfferService(self.w);self.n = 0

    def tearDown(self): self.temp.cleanup()

    def event(self):
        self.n += 1
        return 'EV-' + str(self.n)

    def offer(self): return self.s.state()['offer']

    def sandbox(self, scenario='healthy', event=None):
        # Run the configured synthetic sandbox.
        return self.s.test('OFR-SYN-1', self.offer()['version'], scenario, event or self.event())

    def released(self):
        state = self.sandbox()
        return self.s.release('OFR-SYN-1', state['offer']['version'], state['offer']['latest_test_id'], 'Synthetic owner checked current test and config', self.event())

    def configure(self, change):
        return self.s.configure('OFR-SYN-1', self.offer()['version'], change, self.event())

    def batch(self, scenario='mixed_quality'):
        return self.s.run_batch('OFR-SYN-1', self.offer()['version'], scenario, self.event())

    def feedback(self, batch_id, scenario='buyer_outcomes'):
        return self.s.feedback('OFR-SYN-1', batch_id, scenario, self.event())

    def reconcile(self, batch_id, note, event_id=None):
        feedback_id = next(f['id'] for f in reversed(self.s.state()['feedback']) if f['batch_id'] == batch_id)
        return self.s.reconcile('OFR-SYN-1', batch_id, feedback_id, note, event_id or self.event())

    def test_seed_and_readonly_state_keep_one_generic_offer_and_no_effects(self):
        first = self.s.state()
        self.assertEqual(first, self.s.state())
        self.assertEqual(first['offer']['version'], 1)
        self.assertEqual(first['offer']['margin_pct'], '37.500')
        self.assertEqual(first['offer']['config_sha'], sha(first['offer']['config']))
        self.assertEqual(first['advertiser']['id'], 'ADV-SYN-1')
        self.assertEqual(first['channel']['id'], 'CH-SYN-1')
        self.assertFalse(any(first['effects'].values()))
        self.assertIn('separate adapter', first['adapter_contract']['call'])
        self.assertEqual(first['quality_capacity']['status'], 'no_placement_or_feedback')

    def test_exact_configuration_test_and_owner_release_are_immutably_bound(self):
        state = self.released();offer = state['offer'];test = state['tests'][0];release = state['releases'][0]
        self.assertEqual(offer['status'], 'released_simulated')
        self.assertEqual(release['test_id'], test['id'])
        self.assertEqual(release['config_sha'], offer['config_sha'])
        self.assertEqual(test['evidence']['config_version'], 1)
        self.assertEqual(test['evidence']['external_calls'], 0)
        self.assertIn('Demo', release['owner'])
        self.assertFalse(state['effects']['production_launch_enabled'])

    def test_failed_missing_unknown_or_later_failed_evidence_never_releases(self):
        for scenario in ('failed_verification', 'missing_mapping', 'unknown_outcome'):
            with self.subTest(scenario=scenario):
                self.w.reset();passed = self.sandbox();old_test = passed['offer']['latest_test_id']
                failed = self.sandbox(scenario)
                for test_id in (failed['offer']['latest_test_id'], old_test):
                    with self.assertRaises(StaleOfferAction):
                        self.s.release('OFR-SYN-1', 1, test_id, 'Must not release failed or superseded proof', self.event())
                self.assertFalse(self.s.state()['releases'])
                self.assertIsNone(self.s.state()['offer']['active_release_id'])

    def test_terms_and_mapping_changes_invalidate_release_and_old_proof(self):
        for change in ({'revenue_cpl':'42.00'}, {'mapping_version':'SYN-MAP-2'}):
            with self.subTest(change=change):
                self.w.reset();old = self.released();old_test = old['offer']['latest_test_id']
                original = deepcopy(old['config_versions'][0]);new = self.configure(change)
                self.assertEqual(new['offer']['version'], 2)
                self.assertIsNone(new['offer']['latest_test_id'])
                self.assertIsNone(new['offer']['active_release_id'])
                self.assertEqual(new['config_versions'][0], original)
                self.assertFalse(new['tests'][0]['current_configuration'])
                self.assertFalse(new['releases'][0]['current_configuration'])
                with self.assertRaises(StaleOfferAction):
                    self.s.release('OFR-SYN-1', 2, old_test, 'Old proof cannot approve material change', self.event())
                self.released()
                self.assertEqual(len(self.s.state()['releases']), 2)

    def test_reverting_mapping_retains_distinct_version_without_hash_collision(self):
        original = self.offer()['config_sha'];self.configure({'mapping_version':'SYN-MAP-2'})
        self.configure({'mapping_version':'SYN-MAP-1'})
        state = self.s.state()
        self.assertEqual(state['offer']['version'], 3)
        self.assertNotEqual(original, state['offer']['config_sha'])
        self.assertEqual(state['offer']['config']['mapping_version'], 'SYN-MAP-1')
        self.assertEqual(state['offer']['config']['configuration_version'], 3)
        self.assertEqual(len(state['config_versions']), 3)

    def test_unapproved_terms_mapping_channel_margin_or_capacity_blocks_even_without_traffic(self):
        for change in ({'terms_approved':False}, {'mapping_approved':False}, {'channel_approved':False},
                       {'payout_cpl':'39.99'}, {'channel_capacity':10}):
            with self.subTest(change=change):
                self.w.reset();self.configure(change);state = self.sandbox()
                self.assertTrue(state['offer']['blockers'])
                self.assertEqual(state['tests'][-1]['status'], 'failed')
                self.assertFalse(state['batches'])
                with self.assertRaises(StaleOfferAction):
                    self.s.release('OFR-SYN-1', 2, state['offer']['latest_test_id'], 'Invalid gate', self.event())

    def test_invalid_changes_and_stale_versions_never_mutate_config(self):
        before = self.s.state()
        for change in ({'revenue_cpl':40.0}, {'payout_cpl':'NaN'}, {'daily_cap':True}, {'daily_cap':0},
                       {'channel_capacity':501}, {'terms_approved':'yes'}, {'mapping_version':''}, {'margin_floor_pct':'0'}, {'platform':'live'}):
            with self.subTest(change=change), self.assertRaises(ValueError): self.configure(change)
        self.assertEqual(before, self.s.state())
        with self.assertRaises(StaleOfferAction): self.s.test('OFR-SYN-1', 2, 'healthy', self.event())

    def test_duplicate_request_and_competing_release_produce_one_effect_record(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.s.test('OFR-SYN-1', 1, 'healthy', 'SAME-TEST'), range(10)))
        state = self.s.state();test_id = state['offer']['latest_test_id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.s.release('OFR-SYN-1', 1, test_id, 'Same verified owner note', 'SAME-RELEASE'), range(10)))
        state = self.s.state()
        self.assertEqual(len(state['tests']), 1);self.assertEqual(len(state['releases']), 1)
        with self.assertRaises(StaleOfferAction): self.s.test('OFR-SYN-1', 1, 'failed_verification', 'SAME-TEST')
        with self.assertRaises(StaleOfferAction): self.s.release('OFR-SYN-1', 1, test_id, 'Changed payload', 'SAME-RELEASE')
        self.s.release('OFR-SYN-1', 1, test_id, 'New request identity, same winning proof', self.event())
        self.assertEqual(len(self.s.state()['releases']), 1)

    def test_config_change_race_is_serialized_and_noop_replay_does_not_invalidate(self):
        state = self.released();offer = state['offer']
        self.s.configure('OFR-SYN-1', 1, {'daily_cap':20}, 'NOOP')
        self.assertEqual(offer, self.offer())
        def change(i):
            try: self.s.configure('OFR-SYN-1', 1, {'mapping_version':'SYN-MAP-2'}, 'RACE-'+str(i));return True
            except StaleOfferAction:return False
        with ThreadPoolExecutor(max_workers=4) as pool: self.assertEqual(sum(pool.map(change, range(10))), 1)
        self.assertEqual(self.offer()['version'], 2)
        self.assertIsNone(self.offer()['active_release_id'])

    def test_placement_requires_release_and_enforces_daily_cap_across_new_request_ids(self):
        with self.assertRaises(StaleOfferAction): self.batch()
        self.configure({'daily_cap':3});self.released()
        first = self.batch('all_qualified')['batches'][-1]['payload']
        second = self.batch('all_qualified')['batches'][-1]['payload']
        self.assertEqual(first['qualified_delivered'], 3)
        self.assertEqual(second['qualified_delivered'], 0)
        self.assertEqual(second['prior_UTC_day_delivered'], 3)
        self.w.tick(24)
        self.assertEqual(self.batch('all_qualified')['batches'][-1]['payload']['qualified_delivered'], 3)

    def test_mixed_qualification_and_delivery_ids_are_bound_to_one_offer_channel_release(self):
        self.released();state = self.batch();batch = state['batches'][-1]
        self.assertEqual(batch['payload']['qualified_delivered'], 2)
        self.assertEqual(batch['payload']['rejected'], 2)
        self.assertEqual(batch['release_id'], state['offer']['active_release_id'])
        self.assertTrue(all(r['advertiser_id']=='ADV-SYN-1' and r['channel_id']=='CH-SYN-1' and r['sub_id']=='SUB-SYN-1' for r in batch['payload']['rows']))
        for row in batch['payload']['rows']:
            if row['qualification'] == 'rejected': self.assertIsNone(row['delivered_at'])
        self.assertFalse(state['quality_capacity']['quality_known'])
        self.assertEqual(state['quality_capacity']['counts']['buyer_feedback'], 0)
        for field in ('connected', 'appointments', 'closed_won'):
            self.assertIsNone(state['quality_capacity']['counts'][field])
        self.assertIsNone(state['quality_capacity']['contact_rate_pct'])
        self.assertIsNone(state['quality_capacity']['sales_close_rate_pct'])
        self.assertIsNone(state['quality_capacity']['quality_window']['buyer_feedback_observed_at'])
        self.assertTrue(all('unknown' in r['action'] for r in state['recommendations']))

    def test_buyer_outcomes_quality_capacity_and_provisional_reconciliation_close_owned_loop(self):
        self.released();state = self.batch();batch = state['batches'][-1]
        state = self.feedback(batch['id']);quality = state['quality_capacity']
        self.assertTrue(quality['quality_known'])
        self.assertEqual(quality['counts'], {'delivered':2,'rejected_at_intake':2,'buyer_feedback':2,'connected':2,'appointments':1,'closed_won':1})
        self.assertEqual(quality['contact_rate_pct'], '100');self.assertEqual(quality['sales_close_rate_pct'], '50.0')
        self.assertEqual(quality['available_channel_capacity'], 28)
        self.assertEqual({r['role'] for r in state['recommendations']}, {'BD','AM','AdOps'})
        state = self.reconcile(batch['id'], 'Finance checked exact synthetic delivered and accepted rows')
        reconciliation = state['reconciliations'][-1]['payload']
        self.assertEqual(reconciliation['status'], 'reviewed_fixture')
        self.assertEqual(reconciliation['provisional_receivable_usd'], '80.00')
        self.assertEqual(reconciliation['provisional_channel_cost_usd'], '50.00')
        self.assertFalse(reconciliation['payment_enabled'])

    def test_current_day_capacity_rolls_forward_separately_from_historical_quality_window(self):
        self.released();batch = self.batch()['batches'][-1];before = self.feedback(batch['id'])['quality_capacity']
        self.assertEqual(before['available_channel_capacity'], 28)
        self.assertEqual(before['capacity_window']['server_counted_delivered'], 2)
        old_quality_window = deepcopy(before['quality_window'])
        self.w.tick(24)
        state = self.s.state();after = state['quality_capacity']
        self.assertEqual(after['available_channel_capacity'], 30)
        self.assertEqual(after['capacity_window']['server_counted_delivered'], 0)
        self.assertNotEqual(before['capacity_window']['date_utc'], after['capacity_window']['date_utc'])
        self.assertEqual(after['capacity_window']['observed_at'], self.w.state()['now'])
        self.assertEqual(after['quality_window'], old_quality_window)
        self.assertEqual(after['counts']['connected'], 2)
        self.assertEqual(after['counts']['closed_won'], 1)
        self.assertTrue(after['quality_known'])  # Known historical batch observations, not refreshed quality.
        self.assertEqual(next(r for r in state['recommendations'] if r['role']=='BD')['available_channel_capacity'], 30)
        self.assertEqual(self.batch()['batches'][-1]['payload']['prior_UTC_day_delivered'], 0)

    def test_return_dispute_blocks_financial_treatment_and_supersedes_prior_feedback_review(self):
        self.released();batch = self.batch()['batches'][-1]
        self.feedback(batch['id']);self.reconcile(batch['id'], 'First fixture review')
        state = self.feedback(batch['id'], 'return_dispute')
        prior = state['reconciliations'][0]
        self.assertFalse(prior['current_feedback'])
        self.assertEqual(prior['effective_status'], 'historical_feedback_superseded')
        self.assertTrue(all('unresolved' in r['action'] for r in state['recommendations']))
        state = self.reconcile(batch['id'], 'Do not decide unconfirmed return policy')
        result = state['reconciliations'][-1]['payload']
        self.assertEqual(result['status'], 'blocked_rules_decision')
        self.assertIsNone(result['provisional_receivable_usd']);self.assertIsNone(result['provisional_channel_cost_usd'])
        self.assertEqual(len(result['blocked_by']), 4)

    def test_finance_review_is_bound_to_exact_feedback_and_rejects_changed_evidence(self):
        self.released();batch = self.batch()['batches'][-1]
        first = self.feedback(batch['id'])['feedback'][-1]
        latest = self.feedback(batch['id'], 'return_dispute')['feedback'][-1]
        self.assertNotEqual(first['id'], latest['id'])
        with self.assertRaises(StaleOfferAction):
            self.s.reconcile('OFR-SYN-1', batch['id'], first['id'], 'Reviewed the earlier buyer feedback', self.event())
        self.assertFalse(self.s.state()['reconciliations'])
        state = self.s.reconcile('OFR-SYN-1', batch['id'], latest['id'], 'Current dispute requires finance decision', self.event())
        self.assertEqual(state['reconciliations'][-1]['feedback_id'], latest['id'])
        self.assertEqual(state['reconciliations'][-1]['payload']['status'], 'blocked_rules_decision')

    def test_historical_quality_feedback_and_reconciliation_do_not_represent_changed_config(self):
        self.released();batch = self.batch()['batches'][-1];self.feedback(batch['id'])
        self.reconcile(batch['id'], 'Fixture review')
        self.configure({'mapping_version':'SYN-MAP-2'})
        state = self.s.state()
        self.assertEqual(state['quality_capacity']['status'], 'historical_revalidation_required')
        self.assertIsNone(state['quality_capacity']['available_channel_capacity'])
        for name in ('batches','feedback','reconciliations'):
            self.assertFalse(state[name][0]['current_configuration'])
        self.assertTrue(all(not r['quality_known'] for r in state['recommendations']))
        with self.assertRaises(StaleOfferAction): self.batch()

    def test_current_adapter_rules_change_invalidates_release_until_new_test(self):
        state = self.sandbox();test_id = state['offer']['latest_test_id'];new = deepcopy(fixture());new['rules_version'] = 'changed-adapter-v2'
        with patch('backend.offer_v2.fixture', return_value=new):
            with self.assertRaises(StaleOfferAction): self.s.release('OFR-SYN-1', 1, test_id, 'Old adapter proof', self.event())
            fresh = self.sandbox()
            self.s.release('OFR-SYN-1', 1, fresh['offer']['latest_test_id'], 'New adapter proof', self.event())

    def test_duplicate_batch_feedback_reconciliation_and_restart_preserve_exact_history(self):
        self.released()
        for _ in range(10):self.s.run_batch('OFR-SYN-1', 1, 'mixed_quality', 'SAME-BATCH')
        batch = self.s.state()['batches'][0]
        for _ in range(10): self.s.feedback('OFR-SYN-1', batch['id'], 'buyer_outcomes', 'SAME-FEEDBACK')
        for _ in range(10): self.reconcile(batch['id'], 'Same fixture note', 'SAME-FINANCE')
        before = self.s.state()
        self.assertEqual([len(before[k]) for k in ('batches','feedback','reconciliations')], [1,1,1])
        reopened = OfferService(Workflow(self.path)).state();self.assertEqual(before, reopened)
        self.assertFalse(any(reopened['effects'].values()))
        self.w.reset();state = self.s.state()
        self.assertEqual(state['offer']['version'], 1)
        self.assertFalse(state['tests']);self.assertFalse(state['releases']);self.assertFalse(state['batches'])
