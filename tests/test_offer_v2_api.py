from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import app as app_module
from backend.domain import Workflow


class OfferV2APITests(unittest.TestCase):
    def test_http_release_boundary_and_no_caller_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            workflow = Workflow(Path(temp) / 'api.sqlite3')
            with patch.object(app_module, 'workflow', workflow), TestClient(app_module.app) as client:
                base = '/api/v2/offers/OFR-SYN-1'
                initial = client.get('/api/v2/offers').json()
                self.assertEqual(initial['offer']['version'], 1)
                bad = client.post(base + '/test', json={'expected_version': 1, 'scenario': 'healthy', 'event_id': 'T1', 'owner': 'production-admin'})
                self.assertEqual(bad.status_code, 400)
                failed = client.post(base + '/test', json={'expected_version': 1, 'scenario': 'failed_verification', 'event_id': 'FAIL'}).json()
                failed_id = failed['tests'][-1]['id']
                release = {'expected_version': 1, 'test_id': failed_id, 'note': 'Synthetic owner review', 'event_id': 'RELEASE'}
                self.assertEqual(client.post(base + '/release', json=release).status_code, 409)
                good = client.post(base + '/test', json={'expected_version': 1, 'scenario': 'healthy', 'event_id': 'PASS'}).json()
                release['test_id'] = good['tests'][-1]['id']
                self.assertEqual(client.post(base + '/release', json={**release, 'execute_live': True}).status_code, 400)
                state = client.post(base + '/release', json=release).json()
                replay = client.post(base + '/release', json=release).json()
                self.assertEqual(state, replay)
                self.assertEqual(len(state['releases']), 1)
                changed = client.post(base + '/configure', json={'expected_version': 1, 'change': {'mapping_version': 'SYN-MAP-API2'}, 'event_id': 'EDIT'}).json()
                self.assertIsNone(changed['offer']['active_release_id'])
                self.assertEqual(client.post(base + '/release', json={**release, 'expected_version': 2, 'event_id': 'STALE'}).status_code, 409)
                self.assertEqual(client.post(base + '/batch', json={'expected_version': 2, 'scenario': 'mixed_quality', 'event_id': 'BATCH'}).status_code, 409)
                self.assertFalse(client.get('/api/v2/offers').json()['effects']['production_launch_enabled'])

    def test_unknown_offer_and_undeclared_fixture_payload_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(app_module, 'workflow', Workflow(Path(temp) / 'api.sqlite3')), TestClient(app_module.app) as client:
                base = '/api/v2/offers/OFR-SYN-1'
                self.assertEqual(client.post('/api/v2/offers/OTHER/test', json={'expected_version': 1, 'scenario': 'healthy', 'event_id': 'E'}).status_code, 400)
                self.assertEqual(client.post(base + '/configure', json={'expected_version': 1, 'change': {'platform': 'live'}, 'event_id': 'E'}).status_code, 400)
                self.assertEqual(client.post(base + '/test', json={'expected_version': 1, 'scenario': 'real-provider', 'event_id': 'E'}).status_code, 400)
                self.assertFalse(client.get('/api/v2/offers').json()['tests'])
