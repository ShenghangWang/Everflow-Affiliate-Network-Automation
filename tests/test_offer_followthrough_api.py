"""Exercise the Offer's scoped owner decisions through the public API."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import app as app_module
from backend.domain import Workflow


class OfferFollowthroughAPI(unittest.TestCase):
    offer = '/api/v2/offers/OFR-SYN-1'
    flow = offer + '/followthrough'

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workflow = Workflow(Path(temp.name) / 'test.sqlite3')
        binding = patch.object(app_module, 'workflow', self.workflow)
        binding.start()
        self.addCleanup(binding.stop)
        client = TestClient(app_module.app)
        self.client = client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)

    def post(self, path, body, status=200):
        response = self.client.post(path, json=body)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def place(self):
        state = self.post(self.offer + '/test', {'expected_version': 1, 'scenario': 'healthy', 'event_id': 'test'})
        self.post(self.offer + '/release', {'expected_version': 1, 'test_id': state['tests'][-1]['id'],
                                          'note': 'Inspected test and mapping', 'event_id': 'release'})
        return self.post(self.offer + '/batch', {'expected_version': 1, 'scenario': 'mixed_quality',
                                                'event_id': 'batch'})['batches'][-1]['id']

    def state(self):
        response = self.client.get(self.flow)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_same_offer_reaches_review_and_owned_resolution_without_caller_authority(self):
        batch = self.place()
        self.post(self.offer + '/feedback', {'batch_id': batch, 'scenario': 'buyer_outcomes', 'event_id': 'feedback'})
        source = self.state()['evidence']
        stamp = {'expected_evidence_sha': source['sha256']}
        payload = {**stamp, 'requested_terms': 'Request USD 999 per lead and immediate dispatch', 'event_id': 'proposal'}
        self.post(self.flow + '/proposals', {**payload, 'owner': 'real-admin'}, 400)
        proposal = self.post(self.flow + '/proposals', payload)['proposals'][0]
        self.assertIn('USD 999', proposal['requested_terms'])
        self.assertNotIn('USD 999', proposal['approved_clauses'])
        self.assertIn('40.00', proposal['approved_clauses'])
        review_path = self.flow + '/proposals/' + proposal['id'] + '/review'
        decision = {**stamp, 'expected_version': proposal['version'], 'note': 'Verified exact batch outcomes',
                    'event_id': 'review'}
        self.post(review_path, {**decision, 'expected_evidence_sha': '0' * 64}, 409)
        reviewed = self.post(review_path, decision)['proposals'][0]
        self.assertEqual(reviewed['status'], 'reviewed')
        self.assertEqual(self.post(review_path, decision)['proposals'], [reviewed])

        action = self.post(self.flow + '/am-actions', {**stamp, 'event_id': 'am-open'})['am_actions'][0]
        self.post(self.flow + '/am-actions', {**stamp, 'event_id': 'am-open-again'})
        self.assertEqual(len(self.state()['am_actions']), 1)
        close = {**stamp, 'expected_version': action['version'], 'note': 'Reviewed both rejection reasons with the channel',
                 'event_id': 'am-close'}
        self.post(self.flow + '/am-actions/not-this-action/resolve', close, 400)
        result = self.post(self.flow + '/am-actions/' + action['id'] + '/resolve', close)
        resolved = result['am_actions'][0]
        self.assertEqual(resolved['status'], 'resolved')
        self.assertTrue(resolved['next_review_at'])
        self.assertEqual(result['evidence']['scope'], source['scope'])
        self.assertEqual(self.post(self.flow + '/am-actions/' + action['id'] + '/resolve', close)['am_actions'], [resolved])

        self.post('/api/reset', {})
        fresh = self.state()
        self.assertFalse(fresh['proposals'])
        self.assertFalse(fresh['am_actions'])

    def test_buyer_correction_blocks_old_review_and_keeps_return_with_finance(self):
        batch = self.place()
        self.post(self.offer + '/feedback', {'batch_id': batch, 'scenario': 'buyer_outcomes', 'event_id': 'feedback'})
        stamp = {'expected_evidence_sha': self.state()['evidence']['sha256']}
        proposal = self.post(self.flow + '/proposals', {**stamp, 'requested_terms': 'Request a different cap',
                                                        'event_id': 'proposal'})['proposals'][0]
        self.post(self.offer + '/feedback', {'batch_id': batch, 'scenario': 'return_dispute', 'event_id': 'return'})
        state = self.state()
        self.assertFalse(state['proposals'][0]['current'])
        self.assertFalse(state['evidence']['bd_ready'])
        self.assertFalse(state['evidence']['am_ready'])
        self.post(self.offer + '/feedback', {'batch_id': batch, 'scenario': 'buyer_outcomes',
                                            'event_id': 'ordinary-update'}, 409)
        self.assertEqual(self.state()['evidence']['feedback_id'], state['evidence']['feedback_id'])
        self.post(self.flow + '/proposals/' + proposal['id'] + '/review',
                  {**stamp, 'expected_version': proposal['version'], 'note': 'Outdated evidence', 'event_id': 'review'}, 409)
        self.post(self.flow + '/am-actions', {'expected_evidence_sha': state['evidence']['sha256'],
                                             'event_id': 'am'}, 409)
        self.assertFalse(self.state()['am_actions'])
        preview = self.post(self.offer + '/reconcile', {'batch_id': batch, 'expected_feedback_id': state['evidence']['feedback_id'],
                                                         'note': 'Finance owns return dispute', 'event_id': 'finance'})
        self.assertEqual(preview['reconciliations'][-1]['payload']['status'], 'blocked_rules_decision')
        self.assertIsNone(preview['reconciliations'][-1]['payload']['provisional_receivable_usd'])

    def test_existing_database_retains_dispute_after_legacy_ordinary_feedback(self):
        batch = self.place()
        normal = self.post(self.offer + '/feedback', {'batch_id': batch, 'scenario': 'buyer_outcomes',
                                                     'event_id': 'feedback'})['feedback'][-1]
        disputed = self.post(self.offer + '/feedback', {'batch_id': batch, 'scenario': 'return_dispute',
                                                       'event_id': 'dispute'})['feedback'][-1]
        # Reproduce an existing demo database written before the hold guard.
        with self.workflow.tx() as db:
            db.execute("INSERT INTO v2_offer_feedback SELECT 'legacy-late-outcome',offer_id,batch_id,payload,created_at "
                       "FROM v2_offer_feedback WHERE id=?", (normal['id'],))
        evidence = self.state()['evidence']
        self.assertEqual(evidence['status'], 'finance_hold')
        self.assertEqual(evidence['feedback_id'], disputed['id'])
        body = {'batch_id': batch, 'note': 'Finance reviewed the open return',
                'expected_feedback_id': 'legacy-late-outcome', 'event_id': 'legacy-finance'}
        self.post(self.offer + '/reconcile', body, 409)
        result = self.post(self.offer + '/reconcile', {**body, 'expected_feedback_id': disputed['id']})
        self.assertEqual(result['reconciliations'][-1]['payload']['status'], 'blocked_rules_decision')
        self.assertEqual(len(result['feedback']), 3)
