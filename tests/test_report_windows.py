from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import app as app_module
from backend.domain import Workflow
from backend.reconciliation import ReconciliationService, compare_reports, digest, load_fixture
from backend.report_windows import billing_window, normalize_report


class BillingWindowTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path('backend/fixtures/reconciliation_dst.json').read_text())
        self.window = billing_window(**self.data['billing_window'])

    def test_fall_and_spring_boundaries_are_25_and_23_hours(self):
        for start, end, hours in [('2026-11-01', '2026-11-02', 25), ('2026-03-08', '2026-03-09', 23)]:
            window = billing_window(start, end, 'America/New_York')
            duration = datetime.fromisoformat(window['end_utc']) - datetime.fromisoformat(window['start_utc'])
            self.assertEqual(duration.total_seconds() / 3600, hours)
        self.assertEqual(self.window['start_utc'], '2026-11-01T04:00:00+00:00')
        self.assertEqual(self.window['end_utc'], '2026-11-02T05:00:00+00:00')

    def test_invalid_dates_zone_and_nonexistent_midnight_require_owner_review(self):
        for args in [(None, '2026-11-02', 'UTC'), ('20261101', '2026-11-02', 'UTC'),
                     ('2026-11-02', '2026-11-01', 'UTC'), ('2026-11-01', '2026-11-02', 'Unknown/Zone'),
                     ('2011-12-30', '2011-12-31', 'Pacific/Apia')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                billing_window(*args)

    def test_different_native_timezones_normalize_to_exact_matched_event_window(self):
        self.assertEqual(compare_reports(self.data['internal'], self.data['counterparty'])['result'], 'blocked')
        left = normalize_report(self.data['internal'], self.window)
        right = normalize_report(self.data['counterparty'], self.window)
        result = compare_reports(left, right)
        self.assertEqual((result['result'], result['internal_total'], result['difference']), ('matched', '50.00', '0.00'))
        self.assertEqual({r['event_id'] for r in result['rows']}, {'DST-START', 'DST-FOLD-A', 'DST-FOLD-B', 'DST-LAST'})
        self.assertEqual(left['snapshot']['control_count'], 4)
        self.assertEqual(left['normalization']['source_report']['snapshot']['control_count'], 6)
        self.assertEqual(left['normalization']['excluded_event_ids'], ['DST-PRE', 'DST-END'])
        self.assertFalse(result['external_effects'])
        self.assertEqual(result['model_calls'], 0)

    def test_adjacent_local_days_neither_duplicate_nor_drop_boundary_events(self):
        seen = []
        for start, end in [('2026-10-31', '2026-11-01'), ('2026-11-01', '2026-11-02'), ('2026-11-02', '2026-11-03')]:
            window = billing_window(start, end, 'America/New_York')
            report = normalize_report(self.data['internal'], window)
            ids = [r['event_id'] for r in report['rows']]
            self.assertFalse(set(seen) & set(ids))
            seen.extend(ids)
        self.assertEqual(set(seen), {r['event_id'] for r in self.data['internal']['rows']})

    def test_source_provenance_is_retained_without_mutating_original(self):
        original = deepcopy(self.data['counterparty'])
        normalized = normalize_report(original, self.window)
        proof = normalized['normalization']
        self.assertEqual(original, self.data['counterparty'])
        self.assertEqual(proof['source_report'], original)
        self.assertEqual(proof['source_sha256'], digest(original))
        self.assertEqual(proof['source_reporting_timezone'], 'America/New_York')
        normalized['rows'][0]['amount'] = '99.00'
        self.assertEqual(proof['source_report'], original)

    def test_incomplete_malformed_duplicate_and_future_source_cannot_be_upgraded(self):
        for mutation in ['partial', 'duplicate', 'naive_time', 'control', 'future', 'unproven']:
            report = deepcopy(self.data['internal'])
            if mutation == 'partial': report['snapshot']['complete'] = False
            elif mutation == 'duplicate': report['rows'][1]['event_id'] = report['rows'][0]['event_id']
            elif mutation == 'naive_time': report['rows'][0]['occurred_at'] = '2026-11-01T03:30:00'
            elif mutation == 'control': report['snapshot']['control_amount'] = '0.00'
            elif mutation == 'future': report['observed_at'] = '2027-01-01T00:00:00+00:00'
            else: report['snapshot']['kind'] = 'all_pages_fetched'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                normalize_report(report, self.window, as_of='2026-11-04T02:00:00+00:00')

    def test_insufficient_coverage_and_aggregate_only_input_cannot_be_normalized(self):
        window = billing_window('2026-10-30', '2026-11-02', 'America/New_York')
        with self.assertRaisesRegex(ValueError, 'cover'):
            normalize_report(self.data['internal'], window)
        report = deepcopy(self.data['internal'])
        report['rows'] = [{'day': '2026-11-01', 'amount': '75.00'}]
        with self.assertRaises(ValueError): normalize_report(report, self.window)

    def test_modified_bounds_and_nested_normalization_are_rejected(self):
        window = {**self.window, 'end_utc': '2026-11-02T04:00:00+00:00'}
        with self.assertRaises(ValueError): normalize_report(self.data['internal'], window)
        report = normalize_report(self.data['internal'], self.window)
        with self.assertRaises(ValueError): normalize_report(report, self.window)

    def test_normalized_proof_and_recomputed_controls_cannot_hide_tampering(self):
        data = load_fixture('dst_normalized')
        for mutation in ['amount', 'hash', 'raw', 'excluded', 'malformed']:
            candidate = deepcopy(data)
            report = candidate['counterparty']
            if mutation == 'amount':
                report['rows'][0]['amount'] = '13.50'
                report['snapshot']['control_amount'] = '51.00'
            elif mutation == 'hash': report['normalization']['source_sha256'] = '0' * 64
            elif mutation == 'raw': report['normalization']['source_report']['rows'][0]['amount'] = '99.00'
            elif mutation == 'excluded': report['normalization']['excluded_event_ids'] = []
            else: report['normalization'] = 'invalid'
            result = compare_reports(candidate['internal'], report)
            self.assertEqual(result['result'], 'blocked')
            self.assertIsNone(result['difference'])

    def test_connected_fixture_api_finance_review_and_reopen_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'verify.sqlite3'
            workflow = Workflow(db)
            with patch.object(app_module, 'workflow', workflow), TestClient(app_module.app) as client:
                state = client.post('/api/reconciliation/compare', json={'fixture_id': 'dst_normalized'}).json()
                case, run = state['cases'][0], state['runs'][0]
                self.assertEqual(run['result']['difference'], '0.00')
                repeated = client.post('/api/reconciliation/compare', json={'fixture_id': 'dst_normalized'}).json()
                self.assertEqual(len(repeated['runs']), 1)
                result = client.post(f"/api/reconciliation/cases/{case['id']}/decision", json={
                    'expected_run_id': run['id'], 'expected_version': case['version'], 'decision': 'review_complete',
                    'note': 'Synthetic billing window independently checked', 'evidence': 'Both repeated 01:30 instants, half-open bounds and retained source controls'})
                self.assertEqual(result.status_code, 200)
            reopened = ReconciliationService(Workflow(db)).state()
            self.assertEqual(reopened['cases'][0]['status'], 'resolved')
            with workflow.db() as conn:
                retained = json.loads(conn.execute('SELECT payload FROM recon_snapshots WHERE sha256=?', (run['internal_sha256'],)).fetchone()[0])
            self.assertEqual(retained['normalization']['source_sha256'], digest(self.data['internal']))
            self.assertEqual(len(retained['normalization']['source_report']['rows']), 6)
