from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend import app as app_module
from backend.domain import Workflow
from backend.scenarios import FIXTURE, scenario


class ScenarioTests(unittest.TestCase):
    def fixture(self):
        return json.loads(FIXTURE.read_text())

    def test_default_shock_reduces_modeled_outcomes_and_contribution(self):
        result = scenario()
        base, stress = result["baseline"], result["stressed"]
        self.assertEqual(Decimal(base["totals"]["expected_accepted"]), Decimal("450"))
        self.assertEqual(Decimal(stress["totals"]["expected_accepted"]), Decimal("325"))
        self.assertEqual(Decimal(base["totals"]["expected_billable"]), Decimal("380"))
        self.assertEqual(Decimal(stress["totals"]["expected_billable"]), Decimal("280"))
        self.assertEqual(Decimal(base["totals"]["contribution_usd"]), Decimal("2260.00"))
        self.assertEqual(Decimal(stress["totals"]["contribution_usd"]), Decimal("1862.50"))
        self.assertEqual(Decimal(result["delta"]["contribution_usd"]), Decimal("-397.50"))
        self.assertEqual(Decimal(stress["cohorts"][0]["cost_per_accepted_usd"]), Decimal("13.02"))
        self.assertEqual(Decimal(base["cohorts"][0]["cost_per_accepted_usd"]), Decimal("12.52"))
        self.assertIn("separate from B2B partner prospect", result["entity_boundary"])
        self.assertEqual(result["effects"], {"external_effects": False, "model_calls": 0, "workflow_mutations": False})

    def test_cost_components_are_disjoint_and_refunds_are_contra_revenue(self):
        result = scenario({"volume_shock_pct": 0, "acquisition_cost_change_pct": 25})
        total = result["baseline"]["totals"]
        self.assertEqual(Decimal(total["revenue_usd"]), Decimal("7600"))
        self.assertEqual(Decimal(total["refunds_usd"]), Decimal("380"))
        self.assertEqual(Decimal(total["partner_payout_usd"]), Decimal("3040"))
        self.assertEqual(Decimal(total["acquisition_usd"]), Decimal("625"))
        self.assertEqual(Decimal(total["media_usd"]), Decimal("1250"))
        self.assertEqual(Decimal(total["inference_usd"]), Decimal("15"))
        self.assertEqual(Decimal(total["channel_usd"]), Decimal("30"))
        self.assertEqual(Decimal(total["total_cost_usd"]), Decimal("4960"))
        # Only source A's disjoint acquisition procurement component increases
        # by 25% of USD500. No media or refund component is counted twice.
        self.assertEqual(Decimal(result["delta"]["contribution_usd"]), Decimal("-125"))

    def test_concentration_uses_accepted_outcomes_not_raw_opportunities(self):
        result = scenario()
        base, stress = result["baseline"]["concentration"], result["stressed"]["concentration"]
        self.assertIn("expected_accepted", base["denominator"])
        self.assertEqual(Decimal(base["total_expected_accepted"]), Decimal("450"))
        self.assertEqual(Decimal(base["top_source_share"]), Decimal(250) / Decimal(450))
        self.assertEqual(Decimal(base["hhi"]), Decimal(102500) / Decimal(202500))
        self.assertEqual(Decimal(stress["top_source_share"]), Decimal(200) / Decimal(325))
        self.assertGreater(Decimal(stress["hhi"]), Decimal(base["hhi"]))

    def test_zero_shock_is_identity_and_fractional_outcomes_are_labeled(self):
        unchanged = scenario({"volume_shock_pct": 0, "acquisition_cost_change_pct": 0})
        self.assertEqual(unchanged["baseline"], unchanged["stressed"])
        fractional = scenario({"volume_shock_pct": "-33.3333", "acquisition_cost_change_pct": 0})
        self.assertEqual(Decimal(fractional["stressed"]["cohorts"][0]["expected_accepted"]), Decimal("166.66675"))
        self.assertIn("Expected values", fractional["metric_definitions"]["fractional_outcomes"])

    def test_missing_modeled_cost_is_unavailable_not_zero(self):
        fixture = self.fixture()
        fixture["cohorts"][0]["media_per_opportunity"] = None
        result = scenario(fixture=fixture)
        total = result["baseline"]["totals"]
        self.assertIsNone(total["media_usd"])
        self.assertIsNone(total["total_cost_usd"])
        self.assertIsNone(total["contribution_usd"])
        self.assertIsNone(total["cost_per_accepted_usd"])
        self.assertIn("media_usd", total["missing_components"])
        self.assertEqual(Decimal(total["revenue_usd"]), Decimal("7600"))
        self.assertEqual(Decimal(result["baseline"]["cohorts"][1]["contribution_usd"]), Decimal("1590"))
        fixture["cohorts"][0]["media_per_opportunity"] = "0"
        self.assertIsNotNone(scenario(fixture=fixture)["baseline"]["totals"]["contribution_usd"])

    def test_missing_revenue_or_refund_policy_prevents_contribution(self):
        for field in ("revenue_per_billable", "refund_fraction_of_revenue"):
            with self.subTest(field=field):
                fixture = self.fixture()
                del fixture["cohorts"][0][field]
                total = scenario(fixture=fixture)["baseline"]["totals"]
                self.assertIsNone(total["contribution_usd"])
                self.assertIsNotNone(total["total_cost_usd"])

    def test_zero_accepted_denominator_is_unavailable_while_costs_remain(self):
        fixture = self.fixture()
        for cohort in fixture["cohorts"]:
            cohort["acceptance_rate"] = "0"
        result = scenario(fixture=fixture)
        total, concentration = result["baseline"]["totals"], result["baseline"]["concentration"]
        self.assertEqual(Decimal(total["expected_accepted"]), 0)
        self.assertIsNone(total["cost_per_accepted_usd"])
        self.assertIsNone(total["cost_per_billable_usd"])
        self.assertEqual(Decimal(total["contribution_usd"]), Decimal("-1920"))
        self.assertIsNone(concentration["hhi"])
        self.assertIsNone(concentration["top_source_share"])
        self.assertTrue(all(value is None for value in concentration["source_shares"].values()))

    def test_zero_volume_with_known_costs_has_zero_contribution(self):
        fixture = self.fixture()
        for cohort in fixture["cohorts"]:
            cohort["opportunities"] = "0"
        total = scenario(fixture=fixture)["baseline"]["totals"]
        self.assertEqual(Decimal(total["contribution_usd"]), 0)
        self.assertIsNone(total["cost_per_accepted_usd"])

    def test_input_bounds_reject_negative_nonfinite_oversized_and_unknown(self):
        bad = [
            {"volume_shock_pct": -101}, {"volume_shock_pct": 101},
            {"acquisition_cost_change_pct": -101}, {"acquisition_cost_change_pct": 201},
            {"volume_shock_pct": "NaN"}, {"volume_shock_pct": "Infinity"},
            {"volume_shock_pct": float("nan")}, {"volume_shock_pct": True},
            {"volume_shock_pct": "1e100000"}, {"volume_shock_pct": "1e-99999"},
            {"volume_shock_pct": "0.00001"}, {"volume_shock_pct": "1" * 1000},
            {"volume_shock_pct": []}, {"affected_source": "unknown"},
            {"currency": "EUR"}, {"execute": "dispatch"}, []
        ]
        for payload in bad:
            with self.subTest(payload=str(payload)[:70]):
                with self.assertRaises(ValueError):
                    scenario(payload)
        fixture = self.fixture()
        fixture["cohorts"][0]["media_per_opportunity"] = "-0.01"
        with self.assertRaises(ValueError):
            scenario(fixture=fixture)

    def test_mixed_currency_and_duplicate_sources_are_rejected(self):
        fixture = self.fixture()
        fixture["cohorts"][1]["currency"] = "EUR"
        with self.assertRaisesRegex(ValueError, "mixed/unsupported currencies"):
            scenario(fixture=fixture)
        fixture = self.fixture()
        fixture["cohorts"][1]["source_id"] = fixture["cohorts"][0]["source_id"]
        with self.assertRaisesRegex(ValueError, "unique"):
            scenario(fixture=fixture)

    def test_extreme_supported_inputs_remain_decimal_and_finite(self):
        result = scenario({"volume_shock_pct": -100, "acquisition_cost_change_pct": 200})
        self.assertEqual(Decimal(result["stressed"]["cohorts"][0]["expected_accepted"]), 0)
        self.assertEqual(Decimal(result["stressed"]["concentration"]["hhi"]), 1)
        self.assertTrue(Decimal(result["stressed"]["totals"]["contribution_usd"]).is_finite())

    def test_api_source_swaps_and_invalid_input_do_not_mutate_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_workflow = app_module.workflow
            try:
                app_module.workflow = Workflow(str(Path(tmp) / "scenario-separation.sqlite3"))
                app_module.workflow.draft("L001")
                with TestClient(app_module.app) as client:
                    before = client.get("/api/state").json()
                    first = client.get("/api/scenario")
                    swapped = client.post("/api/scenario", json={"affected_source": "partner_feed", "volume_shock_pct": -50, "acquisition_cost_change_pct": 25})
                    self.assertEqual(first.status_code, 200)
                    self.assertEqual(swapped.status_code, 200)
                    self.assertNotEqual(first.json()["stressed"]["totals"]["contribution_usd"], swapped.json()["stressed"]["totals"]["contribution_usd"])
                    self.assertEqual(client.post("/api/scenario", json={"volume_shock_pct": "NaN"}).status_code, 400)
                    after = client.get("/api/state").json()
                    self.assertEqual(before, after)
                    self.assertEqual(after["actions"][0]["status"], "scheduled")
                    self.assertEqual(len(after["messages"]), 0)
                    self.assertEqual(after["cost"]["provider_attempts"], 0)
            finally:
                app_module.workflow = original_workflow


if __name__ == "__main__":
    unittest.main()
