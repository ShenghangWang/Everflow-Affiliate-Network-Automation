"""Deterministic billing windows and lossless normalization of fixture reports.

No vendor field, timezone setting or consistent-read capability is assumed here.
Only proven immutable synthetic reports can be normalized by this local adapter.
"""
from copy import deepcopy
from datetime import date, datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def billing_window(start_date, end_date, billing_timezone):
    """Convert local date boundaries separately; the end is exclusive."""
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if start.isoformat() != start_date or end.isoformat() != end_date or start >= end:
            raise ValueError("Invalid exclusive billing dates")
        zone = ZoneInfo(billing_timezone)
    except (TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Canonical ISO dates and a known IANA billing timezone required") from exc

    def boundary(day):
        wall = datetime.combine(day, time.min)
        candidates = set()
        for fold in (0, 1):
            utc = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
            if utc.astimezone(zone).replace(tzinfo=None) == wall:
                candidates.add(utc)
        if len(candidates) != 1:
            raise ValueError("Ambiguous or nonexistent billing midnight; explicit owner-approved bounds required")
        return candidates.pop().isoformat()

    try:
        return {"version": "synthetic-billing-window-v1", "billing_timezone": billing_timezone,
                "start_date": start_date, "end_date": end_date,
                "start_utc": boundary(start), "end_utc": boundary(end),
                "semantics": "[start,end), explicit UTC instants"}
    except (OverflowError, OSError) as exc:
        raise ValueError("Billing boundaries are outside the supported range") from exc


def normalize_report(report, window, as_of=None):
    """Retain complete source bytes/facts and filter by authoritative UTC bounds.

    Coverage and controls are checked before filtering. A buffer alone does not
    prove completeness. This does not upgrade mutable/live reports to immutable.
    """
    from .reconciliation import amount, check_report, digest, instant

    if not isinstance(report, dict) or "normalization" in report:
        raise ValueError("One original, unnormalized report required")
    if not isinstance(window, dict):
        raise ValueError("Explicit billing window required")
    expected = billing_window(window.get("start_date"), window.get("end_date"), window.get("billing_timezone"))
    if window != expected:
        raise ValueError("Billing window does not match its authoritative date/timezone contract")
    problems, _, _ = check_report(report, "source", as_of)
    if problems:
        raise ValueError("Source quality/coverage unproven: " + ", ".join(p["code"] for p in problems))
    start, end = instant(window["start_utc"]), instant(window["end_utc"])
    if instant(report["window_start"]) > start or instant(report["window_end"]) < end:
        raise ValueError("Source fetch window does not cover the entire billing window")
    selected, excluded = [], []
    for original in report["rows"]:
        at = instant(original["occurred_at"])
        if start <= at < end:
            selected.append({**original, "occurred_at": at.isoformat()})
        else:
            excluded.append(original["event_id"])
    raw = deepcopy(report)
    result = deepcopy(report)
    result.update(reporting_timezone=window["billing_timezone"],
                  window_start=window["start_utc"], window_end=window["end_utc"], rows=selected)
    result["snapshot"] = {"kind": "immutable_fixture", "id": "NORMALIZED-" + digest([raw, window])[:24],
                          "complete": True, "control_count": len(selected),
                          "control_amount": amount(sum((Decimal(r["amount"]) for r in selected), Decimal("0")))}
    result["normalization"] = {"version": "synthetic-event-window-v1", "billing_window": deepcopy(window),
                               "source_sha256": digest(raw), "source_reporting_timezone": raw["reporting_timezone"],
                               "source_report": raw, "excluded_event_ids": excluded,
                               "label": "Synthetic immutable fixture normalization; live provider contract unverified"}
    return result


def normalization_matches(report, as_of=None):
    """A normalized report must reproduce from its retained original and bounds."""
    from .reconciliation import digest

    try:
        proof = report["normalization"]
        if not isinstance(proof, dict):
            return False
        expected = normalize_report(proof["source_report"], proof["billing_window"], as_of)
        return digest(report) == digest(expected)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
