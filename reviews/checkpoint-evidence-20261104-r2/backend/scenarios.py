"""Pure deterministic sensitivity calculation, separate from workflow records.

No database, credential, inference, dispatch or external I/O boundary is imported.
The only read is the explicitly synthetic configuration fixture. Calculations use
Decimal with 64 significant digits for bounded financial products/sums and 28
digits for nonterminating ratios. Monetary components are not rounded before
computing contribution.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "source_stress.json"
INPUTS = {"affected_source", "volume_shock_pct", "acquisition_cost_change_pct"}
COST_COMPONENTS = ("partner_payout_usd", "acquisition_usd", "media_usd", "inference_usd", "channel_usd")
SUM_COMPONENTS = ("expected_opportunities", "expected_accepted", "expected_billable", "revenue_usd", "refunds_usd", *COST_COMPONENTS)


def decimal_value(value, name, low="0", high="1000000000", *, optional=False):
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{name} must be a finite decimal value")
    source = str(value)
    if len(source) > 32:
        raise ValueError(f"{name} is too long")
    try:
        result = Decimal(source)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a finite decimal value") from exc
    if not result.is_finite() or not Decimal(low) <= result <= Decimal(high):
        raise ValueError(f"{name} must be between {low} and {high}")
    if result.as_tuple().exponent < -4:
        raise ValueError(f"{name} supports at most four decimal places")
    return result


def shown(value):
    return None if value is None else format(value, "f")


def optional_product(left, right):
    # Unknown component stays unknown even at zero volume. The fixture does not
    # provide evidence that an absent cost field means a waived cost.
    return None if left is None or right is None else left * right


def complete_sum(values):
    return None if any(value is None for value in values) else sum(values, Decimal("0"))


def ratio(numerator, denominator):
    if numerator is None or not denominator:
        return None
    with localcontext() as context:
        context.prec = 28
        return numerator / denominator


def compute_cohort(source, volume_factor, acquisition_factor):
    volume = decimal_value(source.get("opportunities"), "opportunities") * volume_factor
    accepted = volume * decimal_value(source.get("acceptance_rate"), "acceptance_rate", high="1")
    billable = accepted * decimal_value(source.get("billable_rate_of_accepted"), "billable_rate_of_accepted", high="1")
    revenue = optional_product(billable, decimal_value(source.get("revenue_per_billable"), "revenue_per_billable", optional=True))
    refunds = optional_product(revenue, decimal_value(source.get("refund_fraction_of_revenue"), "refund_fraction_of_revenue", high="1", optional=True))
    result = {
        "source_id": source["source_id"], "label": source["label"], "currency": source["currency"],
        "expected_opportunities": volume, "expected_accepted": accepted,
        "expected_billable": billable, "revenue_usd": revenue, "refunds_usd": refunds,
        "partner_payout_usd": optional_product(billable, decimal_value(source.get("partner_payout_per_billable"), "partner_payout_per_billable", optional=True)),
        "acquisition_usd": optional_product(volume, optional_product(decimal_value(source.get("acquisition_per_opportunity"), "acquisition_per_opportunity", optional=True), acquisition_factor)),
        "media_usd": optional_product(volume, decimal_value(source.get("media_per_opportunity"), "media_per_opportunity", optional=True)),
        "inference_usd": optional_product(volume, decimal_value(source.get("inference_per_opportunity"), "inference_per_opportunity", optional=True)),
        "channel_usd": optional_product(volume, decimal_value(source.get("channel_per_opportunity"), "channel_per_opportunity", optional=True))
    }
    result["missing_components"] = [name for name in ("revenue_usd", "refunds_usd", *COST_COMPONENTS) if result[name] is None]
    result["total_cost_usd"] = complete_sum([result[name] for name in COST_COMPONENTS])
    result["contribution_usd"] = (revenue - refunds - result["total_cost_usd"]
                                  if not result["missing_components"] else None)
    result["cost_per_accepted_usd"] = ratio(result["total_cost_usd"], accepted)
    result["cost_per_billable_usd"] = ratio(result["total_cost_usd"], billable)
    result["acceptance_rate"] = decimal_value(source.get("acceptance_rate"), "acceptance_rate", high="1")
    result["billable_rate_of_accepted"] = decimal_value(source.get("billable_rate_of_accepted"), "billable_rate_of_accepted", high="1")
    result["acquisition_per_opportunity_usd"] = optional_product(decimal_value(source.get("acquisition_per_opportunity"), "acquisition_per_opportunity", optional=True), acquisition_factor)
    return result


def summarize(cohorts):
    totals = {name: complete_sum([cohort[name] for cohort in cohorts]) for name in SUM_COMPONENTS}
    totals["total_cost_usd"] = complete_sum([totals[name] for name in COST_COMPONENTS])
    totals["contribution_usd"] = complete_sum([cohort["contribution_usd"] for cohort in cohorts])
    totals["missing_components"] = sorted({name for cohort in cohorts for name in cohort["missing_components"]})
    totals["cost_per_accepted_usd"] = ratio(totals["total_cost_usd"], totals["expected_accepted"])
    totals["cost_per_billable_usd"] = ratio(totals["total_cost_usd"], totals["expected_billable"])
    denominator = totals["expected_accepted"]
    shares = {c["source_id"]: ratio(c["expected_accepted"], denominator) for c in cohorts}
    concentration = {
        "denominator": "expected_accepted",
        "denominator_description": "Expected accepted outcomes across the synthetic sources in the stated window",
        "total_expected_accepted": denominator,
        "top_source_share": max(shares.values()) if denominator else None,
        "hhi": ratio(sum((c["expected_accepted"] ** 2 for c in cohorts), Decimal("0")), denominator ** 2),
        "hhi_scale": "0..1; sum of squared expected accepted-outcome shares",
        "source_shares": shares,
        "source_count": len(cohorts),
        "zero_denominator_behavior": "Shares and HHI are unavailable when total expected accepted outcomes are zero"
    }
    return {"cohorts": cohorts, "totals": totals, "concentration": concentration}


def serialized(value):
    if isinstance(value, Decimal):
        return shown(value)
    if isinstance(value, dict):
        return {key: serialized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialized(item) for item in value]
    return value


def scenario(payload=None, *, fixture=None):
    """Return a new scenario without reading or mutating any workflow state.

    API callers can only change bounded shock inputs and the affected source.
    ``fixture`` is an internal test seam for missing-data/currency checks, not an
    API payload or a way to import employer or untrusted customer datasets.
    """
    payload = {} if payload is None else payload
    if not isinstance(payload, dict) or set(payload) - INPUTS:
        raise ValueError("Only affected_source, volume_shock_pct and acquisition_cost_change_pct are accepted")
    data = deepcopy(fixture) if fixture is not None else json.loads(FIXTURE.read_text())
    cohorts = data["cohorts"]
    if not isinstance(cohorts, list) or not 1 <= len(cohorts) <= 20:
        raise ValueError("Scenario must contain 1–20 explicitly synthetic cohorts")
    identifiers = [source.get("source_id") for source in cohorts]
    if any(not isinstance(source_id, str) or not source_id or len(source_id) > 80 for source_id in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Each scenario source must have a unique nonempty ID")
    if data.get("currency") != "USD" or any(source.get("currency") != data["currency"] for source in cohorts):
        raise ValueError("This USD scenario rejects mixed/unsupported currencies; no exchange rate is assumed")
    affected = payload.get("affected_source", data["defaults"]["affected_source"])
    if not isinstance(affected, str) or affected not in identifiers:
        raise ValueError("affected_source must match a configured synthetic source")
    volume_shock = decimal_value(payload.get("volume_shock_pct", data["defaults"]["volume_shock_pct"]), "volume_shock_pct", "-100", "100")
    cost_change = decimal_value(payload.get("acquisition_cost_change_pct", data["defaults"]["acquisition_cost_change_pct"]), "acquisition_cost_change_pct", "-100", "200")
    with localcontext() as context:
        context.prec = 64
        baseline = summarize([compute_cohort(source, Decimal("1"), Decimal("1")) for source in cohorts])
        stressed = summarize([compute_cohort(source,
                              Decimal("1") + volume_shock / 100 if source["source_id"] == affected else Decimal("1"),
                              Decimal("1") + cost_change / 100 if source["source_id"] == affected else Decimal("1")) for source in cohorts])
        delta = {name: stressed["totals"][name] - baseline["totals"][name]
                 if stressed["totals"][name] is not None and baseline["totals"][name] is not None else None
                 for name in ("expected_opportunities", "expected_accepted", "expected_billable", "revenue_usd", "contribution_usd")}
    return serialized({
        "label": data["label"], "classification": data["classification"], "entity_boundary": data["entity_boundary"],
        "window": data["window"], "currency": data["currency"], "billable_event": data["billable_event"],
        "assumptions": data["assumptions"],
        "inputs": {"affected_source": affected, "volume_shock_pct": volume_shock, "acquisition_cost_change_pct": cost_change},
        "input_bounds": {"volume_shock_pct": [-100, 100], "acquisition_cost_change_pct": [-100, 200], "max_decimal_places": 4, "sources": identifiers},
        "metric_definitions": {
            "expected_accepted": "expected_opportunities × assumed acceptance_rate",
            "expected_billable": "expected_accepted × assumed billable_rate_of_accepted",
            "revenue_usd": "expected_billable × assumed revenue_per_billable",
            "refunds_usd": "revenue_usd × assumed refund_fraction_of_revenue; contra-revenue, not an additional cost component",
            "total_cost_usd": "partner_payout + disjoint acquisition procurement + media + inference + channel; all required components must be supplied",
            "contribution_usd": "revenue − refunds − total_cost; modeled cohort contribution before fixed overhead, not total company profit",
            "cost_per_accepted_usd": "total_cost / expected_accepted; unavailable if any modeled cost is missing or accepted outcomes are zero",
            "cost_per_billable_usd": "total_cost / expected_billable; unavailable if any modeled cost is missing or billable outcomes are zero",
            "precision": "Bounded Decimal products/sums use 64 significant digits without intermediate monetary rounding; nonterminating ratios use 28 significant digits",
            "fractional_outcomes": "Expected values under synthetic assumptions, not actual accepted or billable events"
        },
        "baseline": baseline, "stressed": stressed, "delta": delta,
        "effects": {"external_effects": False, "model_calls": 0, "workflow_mutations": False}
    })
