from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import app as app_module
from backend.domain import Workflow
from backend.reconciliation import (
    ReconciliationService, StaleReconciliation, compare_reports, digest, load_fixture,
)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.data = load_fixture("variance")

    def compare(self, data=None):
        data = data or self.data
        return compare_reports(data["internal"], data["counterparty"])

    def test_aligned_exact_difference_ids_statuses_and_threshold(self):
        result = self.compare()
        self.assertEqual(result["result"], "discrepant")
        self.assertEqual((result["internal_total"], result["counterparty_total"], result["difference"]), ("50.00", "37.50", "12.50"))
        self.assertEqual(result["discrepancy_percent"], "25.00")
        self.assertTrue(result["threshold_exceeded"])
        row = next(row for row in result["rows"] if row["event_id"] == "DEMO-E004")
        self.assertEqual(row["issues"], ["status_mismatch", "amount_mismatch"])
        self.assertEqual((row["internal_amount"], row["counterparty_amount"]), ("12.50", "0.00"))
        self.assertFalse(result["external_effects"])
        self.assertEqual(result["model_calls"], 0)

    def test_alignment_mismatches_never_produce_final_amount_or_draft(self):
        for key, value in [("account_id", "OTHER"), ("currency", "EUR"), ("unit", "clicks"),
                           ("reporting_timezone", "America/New_York"), ("billable_event", "different event"),
                           ("status_basis", "pending outcomes"), ("window_start", "2026-10-25T00:00:00+00:00")]:
            with self.subTest(key=key):
                data = deepcopy(self.data)
                data["counterparty"][key] = value
                result = self.compare(data)
                self.assertEqual(result["result"], "blocked")
                self.assertIsNone(result["difference"])
                self.assertEqual(result["rows"], [])

    def test_partial_or_mutated_control_totals_remain_unknown(self):
        for mutation in ("partial", "control_count", "control_amount", "missing_row", "changed_amount", "unknown_kind"):
            with self.subTest(mutation=mutation):
                data = deepcopy(self.data)
                report = data["counterparty"]
                if mutation == "partial": report["snapshot"]["complete"] = False
                elif mutation == "control_count": report["snapshot"]["control_count"] = 99
                elif mutation == "control_amount": report["snapshot"]["control_amount"] = "99.00"
                elif mutation == "missing_row": report["rows"].pop()
                elif mutation == "changed_amount": report["rows"][0]["amount"] = "13.00"
                else: report["snapshot"]["kind"] = "all_pages_fetched"
                result = self.compare(data)
                self.assertEqual(result["result"], "blocked")
                self.assertIsNone(result["internal_total"])
                self.assertIsNone(result["discrepancy_percent"])

    def test_duplicate_ids_and_out_of_window_event_cannot_hide_in_controls(self):
        data = deepcopy(self.data)
        data["counterparty"]["rows"][1]["event_id"] = "DEMO-E001"
        result = self.compare(data)
        self.assertEqual(result["result"], "blocked")
        self.assertTrue(any(b["code"] == "duplicate_event_id" for b in result["blockers"]))
        data = deepcopy(self.data)
        data["counterparty"]["rows"][0]["occurred_at"] = data["counterparty"]["window_end"]
        self.assertEqual(self.compare(data)["result"], "blocked")

    def test_invalid_amounts_statuses_and_schema_block_financial_conclusion(self):
        for value in (None, 12.50, "NaN", "Infinity", "-1.00", "0.001", "1000000001", "9" * 100):
            with self.subTest(value=value):
                data = deepcopy(self.data)
                data["counterparty"]["rows"][0]["amount"] = value
                self.assertEqual(self.compare(data)["result"], "blocked")
        data = deepcopy(self.data)
        data["counterparty"]["revision"] = True
        self.assertEqual(self.compare(data)["result"], "blocked")
        data = deepcopy(self.data)
        data["counterparty"]["rows"][0]["status"] = "maybe approved"
        self.assertEqual(self.compare(data)["result"], "blocked")

    def test_equivalent_utc_instants_align_but_unqualified_timestamps_do_not(self):
        data = deepcopy(self.data)
        data["counterparty"]["window_start"] = "2026-10-26T08:00:00+08:00"
        data["counterparty"]["window_end"] = "2026-11-02T08:00:00+08:00"
        self.assertEqual(self.compare(data)["result"], "discrepant")
        data["counterparty"]["window_end"] = "2026-11-02T00:00:00"
        self.assertEqual(self.compare(data)["result"], "blocked")

    def test_zero_denominator_is_unavailable_and_exact_five_percent_is_not_above(self):
        data = load_fixture("matched")
        for side in ("internal", "counterparty"):
            data[side]["rows"] = []
            data[side]["snapshot"].update(control_count=0, control_amount="0.00")
        result = self.compare(data)
        self.assertEqual(result["result"], "matched")
        self.assertIsNone(result["discrepancy_percent"])
        self.assertIsNone(result["threshold_exceeded"])
        data = load_fixture("matched")
        data["counterparty"]["rows"][0]["amount"] = "10.00"
        data["counterparty"]["snapshot"]["control_amount"] = "47.50"
        result = self.compare(data)
        self.assertEqual(result["discrepancy_percent"], "5.00")
        self.assertFalse(result["threshold_exceeded"])
        self.assertEqual(result["result"], "discrepant")

    def test_missing_event_in_complete_report_is_explicit_not_a_matching_zero(self):
        data = deepcopy(self.data)
        data["counterparty"]["rows"].pop()
        data["counterparty"]["snapshot"].update(control_count=3, control_amount="37.50")
        result = self.compare(data)
        row = next(r for r in result["rows"] if r["event_id"] == "DEMO-E004")
        self.assertIsNone(row["counterparty_amount"])
        self.assertIn("missing_counterparty_event", row["issues"])
        self.assertEqual(result["result"], "discrepant")


class ReconciliationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "reconciliation.sqlite3")
        self.w = Workflow(self.path)
        self.service = ReconciliationService(self.w)

    def tearDown(self):
        self.tmp.cleanup()

    def decision(self, case=None, decision="review_complete"):
        state = self.service.state()
        case = case or state["cases"][0]
        return self.service.decide(case["id"], case["current_run_id"], case["version"], decision,
                                   "Synthetic finance review completed", "Fixture event IDs, immutable report hashes and controls checked")

    def test_compare_draft_and_owned_finance_resolution_no_external_effects(self):
        before = self.w.state()
        state = self.service.compare_fixture("variance")
        case, run = state["cases"][0], state["runs"][0]
        self.assertEqual(case["owner"], "Demo finance owner")
        self.assertEqual(case["status"], "review_required")
        self.assertEqual(len(run["drafts"]), 2)
        self.assertTrue(all(not draft["dispatch_enabled"] for draft in run["drafts"]))
        self.assertIn("DEMO-E004", run["drafts"][0]["content"])
        self.assertIn("50.00", run["drafts"][0]["content"])
        self.assertIn("37.50", run["drafts"][0]["content"])
        resolved = self.decision(case)
        self.assertEqual(resolved["cases"][0]["status"], "resolved")
        self.assertEqual(resolved["decisions"][0]["run_id"], run["id"])
        after = self.w.state()
        for key in ("leads", "actions", "messages", "authorizations", "policy", "terms", "cost"):
            self.assertEqual(before[key], after[key])
        audit = next(e for e in after["audit"] if e["event"] == "reconciliation_finance_decision")
        self.assertFalse(audit["detail"]["financial_effect"])
        self.assertFalse(audit["detail"]["dispatch_enabled"])

    def test_snapshot_terms_rules_hashes_resolve_to_exact_retained_payloads(self):
        state = self.service.compare_fixture("variance")
        run = state["runs"][0]
        with self.w.db() as c:
            for key in ("internal_sha256", "counterparty_sha256", "terms_sha256"):
                row = c.execute("SELECT payload FROM recon_snapshots WHERE sha256=?", (run[key],)).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(digest(json.loads(row["payload"])), run[key])
            row = c.execute("SELECT payload FROM recon_snapshots WHERE sha256=?", (run["result"]["rules_sha256"],)).fetchone()
            self.assertEqual(digest(json.loads(row["payload"])), run["result"]["rules_sha256"])

    def test_repeat_comparison_and_competing_claims_create_one_case_and_run(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.service.compare_fixture("variance"), range(10)))
        state = self.service.state()
        self.assertEqual((len(state["cases"]), len(state["runs"])), (1, 1))
        self.assertEqual(state["cases"][0]["version"], 1)
        before = self.w.state()
        self.service.compare_fixture("variance")
        self.assertEqual(before, self.w.state())

    def test_required_evidence_and_stale_resolution_cannot_change_case(self):
        state = self.service.compare_fixture("variance")
        case = state["cases"][0]
        for note, evidence in (("", "evidence"), ("note", ""), ("note", {"fake": "evidence"})):
            with self.assertRaises(ValueError):
                self.service.decide(case["id"], case["current_run_id"], case["version"], "review_complete", note, evidence)
        self.decision(case)
        with self.assertRaises(StaleReconciliation):
            self.decision(case)
        self.assertEqual(len(self.service.state()["decisions"]), 1)

    def test_corrected_report_reopens_and_preserves_prior_decision(self):
        initial = self.service.compare_fixture("variance")
        prior = initial["cases"][0]
        self.decision(prior)
        state = self.service.compare_fixture("corrected")
        self.assertEqual(len(state["cases"]), 1)
        case = state["cases"][0]
        self.assertEqual((case["status"], case["version"]), ("review_required", 3))
        self.assertEqual(state["runs"][-1]["result"]["result"], "matched")
        self.assertEqual(len(state["decisions"]), 1)
        with self.assertRaises(StaleReconciliation):
            self.decision(prior)
        self.decision(case)
        self.assertEqual(len(self.service.state()["decisions"]), 2)
        before = self.w.state()
        self.service.compare_fixture("variance")
        self.assertEqual(before, self.w.state(), "Previously seen old report cannot roll current evidence backward")

    def test_unseen_older_report_and_conflicting_same_revision_do_not_replace_current(self):
        self.service.compare_fixture("corrected")
        before = self.w.state()
        with self.assertRaises(StaleReconciliation):
            self.service.compare_fixture("variance")
        self.assertEqual(before, self.w.state())
        data = load_fixture("corrected")
        data["counterparty"]["rows"][0]["amount"] = "1.00"
        data["counterparty"]["snapshot"]["control_amount"] = "38.50"
        with patch("backend.reconciliation.load_fixture", return_value=data):
            with self.assertRaises(StaleReconciliation):
                self.service.compare_fixture("corrected")
        self.assertEqual(before, self.w.state())

    def test_partial_report_blocks_final_resolution_but_retains_owned_correction_task(self):
        state = self.service.compare_fixture("partial")
        case = state["cases"][0]
        self.assertEqual(state["runs"][0]["drafts"], [])
        self.assertEqual(case["status"], "blocked")
        with self.assertRaises(ValueError):
            self.decision(case)
        state = self.decision(case, "request_correction")
        self.assertEqual(state["cases"][0]["status"], "awaiting_correction")
        self.assertIsNotNone(state["cases"][0]["next_check_at"])
        self.assertEqual(state["cases"][0]["owner"], "Demo finance owner")

    def test_reminder_draft_requires_known_due_date_and_unpaid_evidence(self):
        for change in ({"due_at": None}, {"payment_status": "paid"}, {"payment_evidence": ""}):
            with self.subTest(change=change):
                self.w.reset()
                data = load_fixture("variance")
                data["terms"].update(change)
                with patch("backend.reconciliation.load_fixture", return_value=data):
                    state = self.service.compare_fixture("variance")
                self.assertEqual([d["kind"] for d in state["runs"][0]["drafts"]], ["discrepancy_review"])

    def test_restart_preserves_exact_case_reports_and_finance_decision_and_reset_is_explicit(self):
        self.service.compare_fixture("variance")
        self.decision()
        before = self.w.state()
        reopened = Workflow(self.path)
        self.assertEqual(before, reopened.state())
        reopened.reset()
        self.assertEqual(ReconciliationService(reopened).state()["cases"], [])
        self.assertEqual(len(reopened.state()["leads"]), 3)

    def test_http_path_blocks_extra_authority_and_rejects_stale_versions(self):
        app_module.workflow = self.w
        with TestClient(app_module.app) as client:
            self.assertEqual(client.post("/api/reconciliation/compare", json={"fixture_id": "../../.env"}).status_code, 400)
            self.assertEqual(client.post("/api/reconciliation/compare", json={"fixture_id": "variance", "send": True}).status_code, 400)
            state = client.post("/api/reconciliation/compare", json={"fixture_id": "variance"}).json()
            case = state["cases"][0]
            body = {"expected_run_id": case["current_run_id"], "expected_version": case["version"], "decision": "review_complete", "note": "Synthetic review", "evidence": "Fixture controls checked"}
            route = f"/api/reconciliation/cases/{case['id']}/decision"
            self.assertEqual(client.post(route, json={**body, "actor": "admin"}).status_code, 400)
            self.assertEqual(client.post(route, json=body).status_code, 200)
            self.assertEqual(client.post(route, json=body).status_code, 409)
            self.assertEqual(client.get("/api/reconciliation").json()["cases"][0]["status"], "resolved")
            self.assertFalse(client.get("/api/state").json()["reconciliation"]["effects"]["external_effects"])
