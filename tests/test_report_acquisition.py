from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from backend.domain import Workflow
from backend.reconciliation import ReconciliationService, compare_reports, load_fixture, digest
from backend.report_acquisition import FixturePageSource, LIMITS, acquisition_matches, collect, fixture_report


class MutablePageTests(unittest.TestCase):
    def setUp(self):
        self.base = load_fixture('matched')['internal']

    def test_stable_manifest_matches_exact_rows_and_controls(self):
        report = fixture_report(self.base, 'stable')
        self.assertTrue(acquisition_matches(report))
        self.assertEqual(report['rows'], self.base['rows'])
        self.assertEqual(compare_reports(self.base, report)['result'], 'matched')
        self.assertEqual(len(report['acquisition']['attempts']), 1)
        self.assertEqual(len(report['acquisition']['attempts'][0]['pages']), 2)

    def test_changes_duplicates_missing_and_equal_totals_never_gain_authority(self):
        for scenario in ('insert', 'remove', 'reorder', 'correction', 'same_total_change', 'duplicate', 'missing', 'token_change', 'unproven', 'loop'):
            with self.subTest(scenario=scenario):
                report = fixture_report(self.base, scenario)
                self.assertFalse(acquisition_matches(report))
                self.assertFalse(report['snapshot']['complete'])
                self.assertEqual(len(report['acquisition']['attempts']), LIMITS['max_attempts'])
                result = compare_reports(self.base, report)
                self.assertEqual(result['result'], 'blocked')
                self.assertIsNone(result['difference'])
                self.assertFalse(result['threshold_exceeded'])
                self.assertTrue(all(len(a['pages']) <= LIMITS['max_pages'] for a in report['acquisition']['attempts']))

    def test_changed_values_with_identical_ids_count_and_amount_are_detected(self):
        report = fixture_report(self.base, 'same_total_change')
        self.assertEqual(report['snapshot']['control_count'], self.base['snapshot']['control_count'])
        self.assertEqual(report['snapshot']['control_amount'], self.base['snapshot']['control_amount'])
        reasons = report['acquisition']['attempts'][-1]['problems']
        self.assertIn('content_control_mismatch', reasons)
        self.assertNotIn('duplicate_event_ids', reasons)

    def test_identical_unproven_passes_do_not_become_immutable(self):
        report = fixture_report(self.base, 'unproven')
        first, second = report['acquisition']['attempts']
        self.assertEqual(first['pages'], second['pages'])
        self.assertEqual(report['acquisition']['classification'], 'partial_or_uncertain')
        self.assertIn('upstream_snapshot_not_proven', second['problems'])

    def test_settled_retry_discards_failed_pages_and_retains_both_attempts(self):
        report = fixture_report(self.base, 'settles')
        self.assertTrue(acquisition_matches(report))
        first, second = report['acquisition']['attempts']
        self.assertTrue(first['problems'])
        self.assertFalse(second['problems'])
        self.assertEqual(report['rows'], self.base['rows'])
        self.assertNotEqual(first['pages'], second['pages'])

    def test_transient_page_retry_and_exhaustion_are_bounded_and_auditable(self):
        report = fixture_report(self.base, 'transient')
        self.assertTrue(acquisition_matches(report))
        calls = report['acquisition']['attempts'][0]['calls']
        self.assertEqual([c['outcome'] for c in calls], ['response', 'timeout', 'response'])
        self.assertEqual(calls[1]['retry_delay_seconds'], 1)
        exhausted = fixture_report(self.base, 'timeout')
        self.assertFalse(acquisition_matches(exhausted))
        self.assertEqual(sum(len(a['calls']) for a in exhausted['acquisition']['attempts']), 4)
        self.assertTrue(all('page_retry_exhausted' in a['problems'] for a in exhausted['acquisition']['attempts']))
        permanent = collect(FixturePageSource(self.base, 'forbidden'))
        self.assertEqual(len(permanent['attempts']), 1)
        self.assertEqual(permanent['attempts'][0]['calls'], [])
        self.assertIn('permanent_source_error:PermissionError', permanent['attempts'][0]['problems'])

    def test_row_or_proof_tampering_and_false_complete_flag_remain_blocked(self):
        for mutation in ('row', 'token', 'window', 'classification'):
            report = fixture_report(self.base, 'stable' if mutation != 'classification' else 'same_total_change')
            if mutation == 'row': report['rows'][0]['amount'] = '99.00'
            elif mutation == 'token': report['acquisition']['attempts'][-1]['pages'][0]['snapshot_token'] = 'forged'
            elif mutation == 'window': report['acquisition']['attempts'][-1]['contract']['header']['window_start'] = '2025-01-01T00:00:00+00:00'
            else:
                report['snapshot']['complete'] = True
                report['acquisition']['classification'] = 'verified_fixture'
                report['acquisition']['attempts'][-1]['problems'] = []
            self.assertEqual(compare_reports(self.base, report)['result'], 'blocked')

    def test_corrected_full_window_reopens_finance_even_for_old_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'pages.sqlite3'
            w = Workflow(db);service = ReconciliationService(w)
            state = service.compare_fixture('paged_mutating')
            run, case = state['runs'][0], state['cases'][0]
            self.assertEqual(case['status'], 'blocked')
            self.assertEqual(run['drafts'], [])
            with self.assertRaises(ValueError):
                service.decide(case['id'], run['id'], case['version'], 'review_complete', 'review', 'source')
            state = service.decide(case['id'], run['id'], case['version'], 'request_correction', 'Refresh entire closed window', 'Changing values with same totals; no complete snapshot')
            w.tick(24);w.tick(0)
            state = service.compare_fixture('paged_corrected')
            self.assertEqual(len(state['cases']), 1)
            self.assertEqual(state['cases'][0]['status'], 'review_required')
            self.assertEqual(state['tasks'][0]['status'], 'completed')
            case, run = state['cases'][0], state['runs'][-1]
            service.decide(case['id'], run['id'], case['version'], 'review_complete', 'Full closed-window correction verified', 'All original event IDs and exact content controls')
            final = ReconciliationService(Workflow(db)).state()
            self.assertEqual(final['cases'][0]['status'], 'resolved')
            self.assertEqual(len(final['runs']), 2)
            self.assertEqual(len(final['decisions']), 2)
            self.assertEqual(service.compare_fixture('paged_mutating'), final)
            with w.db() as c:
                for row in c.execute('SELECT sha256,payload FROM recon_snapshots'):
                    import json
                    self.assertEqual(digest(json.loads(row['payload'])), row['sha256'])
            self.assertEqual(w.state()['messages'], [])
