"""Exact comparison and durable owned review of synthetic immutable reports.

No model, mailbox, settlement or tracking-provider client is available here.
Final conclusions require aligned, complete snapshots with verified controls.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "reconciliation.json"
TABLES = ("recon_decisions", "recon_runs", "recon_cases", "recon_snapshots")
FIXTURES = [
    {"id": "variance", "label": "Aligned reports · USD 12.50 discrepancy"},
    {"id": "corrected", "label": "Corrected counterparty report · new version"},
    {"id": "matched", "label": "Aligned reports · all events match"},
    {"id": "partial", "label": "Incomplete snapshot · comparison blocked"},
    {"id": "window_mismatch", "label": "Different report windows · comparison blocked"},
]


class StaleReconciliation(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def instant(value):
    if not isinstance(value, str):
        raise ValueError("Timezone-qualified timestamp required")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Timezone-qualified timestamp required")
    return dt.astimezone(timezone.utc)


def money(value):
    if not isinstance(value, str) or len(value) > 24:
        raise ValueError("Amounts require finite decimal strings")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if not result.is_finite() or result < 0 or result > Decimal("1000000000") or result.as_tuple().exponent < -2:
        raise ValueError("Amounts require 0–1000000000 with at most two decimal places")
    return result


def amount(value):
    return format(value, ".2f")


def load_fixture(fixture_id):
    if fixture_id not in {f["id"] for f in FIXTURES}:
        raise ValueError("Unknown reconciliation fixture")
    data = json.loads(FIXTURE.read_text())
    if fixture_id in ("corrected", "matched"):
        data["counterparty"]["rows"] = deepcopy(data["internal"]["rows"])
        data["counterparty"]["snapshot"]["control_amount"] = "50.00"
        data["counterparty"]["revision"] = 2
        data["counterparty"]["snapshot"]["id"] = "COUNTERPARTY-W44-r2"
    if fixture_id == "matched":
        for side in ("internal", "counterparty"):
            data[side]["account_id"] = "DEMO-ACCOUNT-02"
    elif fixture_id == "partial":
        for side in ("internal", "counterparty"):
            data[side]["account_id"] = "DEMO-ACCOUNT-03"
        data["counterparty"]["snapshot"]["complete"] = False
        data["counterparty"]["rows"].pop()
    elif fixture_id == "window_mismatch":
        for side in ("internal", "counterparty"):
            data[side]["account_id"] = "DEMO-ACCOUNT-04"
        data["counterparty"]["window_start"] = "2026-10-25T00:00:00+00:00"
    return data


def ensure_schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS recon_snapshots(
      sha256 TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS recon_cases(
      id TEXT PRIMARY KEY, account_id TEXT NOT NULL, owner TEXT NOT NULL,
      version INTEGER NOT NULL, status TEXT NOT NULL, current_run_id TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, next_check_at TEXT);
    CREATE TABLE IF NOT EXISTS recon_runs(
      id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES recon_cases(id),
      fixture_id TEXT NOT NULL, internal_sha256 TEXT NOT NULL REFERENCES recon_snapshots(sha256),
      counterparty_sha256 TEXT NOT NULL REFERENCES recon_snapshots(sha256),
      terms_sha256 TEXT NOT NULL, rules_version TEXT NOT NULL,
      result TEXT NOT NULL, drafts TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS recon_decisions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      case_id TEXT NOT NULL REFERENCES recon_cases(id), run_id TEXT NOT NULL REFERENCES recon_runs(id),
      case_version INTEGER NOT NULL, decision TEXT NOT NULL,
      note TEXT NOT NULL, evidence TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL,
      UNIQUE(case_id,case_version));
    """)


def check_report(report, side):
    problems, rows, total = [], {}, Decimal("0")
    required = ("account_id", "currency", "unit", "reporting_timezone", "billable_event", "status_basis", "source", "report_id")
    if not isinstance(report, dict):
        return [{"side": side, "code": "invalid_report"}], {}, None
    if report.get("schema_version") != 1 or isinstance(report.get("revision"), bool) or not isinstance(report.get("revision"), int) or report["revision"] < 1:
        problems.append({"side": side, "code": "invalid_schema_or_revision"})
    for name in required:
        if not isinstance(report.get(name), str) or not report[name].strip():
            problems.append({"side": side, "code": "missing_" + name})
    if report.get("currency") != "USD" or report.get("unit") != "currency_amount":
        problems.append({"side": side, "code": "unsupported_currency_or_unit"})
    try:
        start, end = instant(report.get("window_start")), instant(report.get("window_end"))
        observed = instant(report.get("observed_at"))
        if start >= end or observed < end:
            raise ValueError("Unsettled report window")
    except (ValueError, OverflowError):
        problems.append({"side": side, "code": "invalid_or_unsettled_window"})
        start = end = None
    snapshot = report.get("snapshot")
    if not isinstance(snapshot, dict):
        snapshot = {}
    if snapshot.get("kind") != "immutable_fixture" or not snapshot.get("id") or snapshot.get("complete") is not True:
        problems.append({"side": side, "code": "unproven_snapshot"})
    records = report.get("rows")
    if not isinstance(records, list) or len(records) > 5000:
        return problems + [{"side": side, "code": "invalid_rows"}], {}, None
    for i, row in enumerate(records):
        try:
            event_id = row["event_id"]
            if not isinstance(event_id, str) or not 1 <= len(event_id.strip()) <= 120 or event_id != event_id.strip():
                raise ValueError("Invalid event ID")
            if event_id in rows:
                problems.append({"side": side, "code": "duplicate_event_id", "event_id": event_id})
                continue
            row_amount = money(row["amount"])
            if row["status"] not in ("billable", "rejected") or (row["status"] == "rejected" and row_amount != 0):
                raise ValueError("Unknown status or nonzero rejected amount")
            at = instant(row["occurred_at"])
            if start is not None and not start <= at < end:
                raise ValueError("Event outside declared window")
            rows[event_id] = {"amount": row_amount, "status": row["status"]}
            total += row_amount
        except (TypeError, KeyError, ValueError, OverflowError):
            problems.append({"side": side, "code": "invalid_row", "row_index": i})
    try:
        count = snapshot.get("control_count")
        if isinstance(count, bool) or not isinstance(count, int) or count != len(records) or count != len(rows):
            raise ValueError("Count mismatch")
        if money(snapshot.get("control_amount")) != total:
            raise ValueError("Amount mismatch")
    except (ValueError, TypeError):
        problems.append({"side": side, "code": "snapshot_control_mismatch"})
    return problems, rows, total if not problems else None


def compare_reports(internal, counterparty, threshold_percent="5"):
    """Compute evidence only after quality and alignment gates; never infer fraud."""
    internal = internal if isinstance(internal, dict) else {}
    counterparty = counterparty if isinstance(counterparty, dict) else {}
    errors_l, left, left_total = check_report(internal, "internal")
    errors_r, right, right_total = check_report(counterparty, "counterparty")
    blockers = errors_l + errors_r
    for name in ("account_id", "currency", "unit", "reporting_timezone", "billable_event", "status_basis"):
        if internal.get(name) != counterparty.get(name):
            blockers.append({"side": "alignment", "code": name + "_mismatch"})
    for name in ("window_start", "window_end"):
        try:
            if instant(internal.get(name)) != instant(counterparty.get(name)):
                blockers.append({"side": "alignment", "code": name + "_mismatch"})
        except (ValueError, OverflowError):
            pass  # Already retained by the report's quality check.
    base = {"classification": "PROPOSED DESIGN", "synthetic": True,
            "currency": internal.get("currency"), "window_start": internal.get("window_start"),
            "window_end": internal.get("window_end"), "window_semantics": "[start,end), UTC instants",
            "billable_event": internal.get("billable_event"), "blockers": blockers,
            "denominator": "internal immutable report amount, same account/window/currency/status basis",
            "threshold_percent": threshold_percent, "internal_total": None, "counterparty_total": None,
            "difference": None, "absolute_difference": None, "discrepancy_percent": None,
            "threshold_exceeded": None, "rows": [], "external_effects": False, "model_calls": 0}
    if blockers:
        return {**base, "result": "blocked", "reason": "Incomplete, inconsistent or unaligned inputs; no final variance or collection draft"}
    rows = []
    for event_id in sorted(set(left) | set(right)):
        l, r = left.get(event_id), right.get(event_id)
        difference = (l["amount"] if l else Decimal("0")) - (r["amount"] if r else Decimal("0"))
        issues = []
        if l is None or r is None:
            issues.append("missing_internal_event" if l is None else "missing_counterparty_event")
        if l is not None and r is not None and l["status"] != r["status"]:
            issues.append("status_mismatch")
        if difference:
            issues.append("amount_mismatch")
        rows.append({"event_id": event_id, "internal_amount": amount(l["amount"]) if l else None,
                     "counterparty_amount": amount(r["amount"]) if r else None,
                     "internal_status": l["status"] if l else None, "counterparty_status": r["status"] if r else None,
                     "difference": amount(difference), "issues": issues})
    difference = left_total - right_total
    with localcontext() as ctx:
        ctx.prec = 28
        percent = abs(difference) / left_total * 100 if left_total else None
    threshold = money(threshold_percent)
    return {**base, "result": "discrepant" if any(r["issues"] for r in rows) else "matched",
            "internal_total": amount(left_total), "counterparty_total": amount(right_total),
            "difference": amount(difference), "absolute_difference": amount(abs(difference)),
            "discrepancy_percent": format(percent, "f") if percent is not None else None,
            "threshold_exceeded": percent > threshold if percent is not None else None,
            "rows": rows, "reason": "Exact ID/amount/status comparison; no fraud or causal conclusion"}


def build_drafts(result, data, now):
    if result["result"] == "blocked":
        return []
    drafts, terms = [], data["terms"]
    currency = result["currency"]
    if result["result"] == "discrepant":
        ids = ", ".join(row["event_id"] for row in result["rows"] if row["issues"])
        drafts.append({"kind": "discrepancy_review", "mode": "deterministic template draft", "recipient": terms["recipient"],
                       "subject": "Synthetic report reconciliation — review requested",
                       "content": f"Hello, please review our synthetic reports for {result['window_start']} to {result['window_end']} (end exclusive). Our internal total is {currency} {result['internal_total']}; your report totals {currency} {result['counterparty_total']}. The signed difference (internal minus counterparty) is {currency} {result['difference']}. Affected event IDs: {ids}. Please confirm the reporting basis or provide a corrected report. This is a synthetic demonstration draft, not an allegation or agreed settlement.",
                       "dispatch_enabled": False, "terms_version": terms.get("version")})
    try:
        overdue = instant(now) > instant(terms.get("due_at"))
    except (ValueError, OverflowError):
        overdue = False
    if (overdue and terms.get("payment_status") == "unpaid" and terms.get("payment_evidence")
            and terms.get("version") and money(result["counterparty_total"]) > 0):
        drafts.append({"kind": "overdue_reminder", "mode": "deterministic template draft", "recipient": terms["recipient"],
                       "subject": "Synthetic payment status — review requested",
                       "content": f"Hello, our synthetic unpaid-ledger fixture lists {currency} {result['counterparty_total']} from the counterparty report, due at {terms['due_at']}. Please confirm payment status. The internal difference of {currency} {result['difference']} remains a separate reconciliation item. All values and terms are assumed demonstration data; this draft creates no actual debt, dispatch or payment instruction.",
                       "dispatch_enabled": False, "terms_version": terms["version"], "payment_evidence": terms["payment_evidence"]})
    return drafts


class ReconciliationService:
    def __init__(self, workflow):
        self.workflow = workflow

    def compare_fixture(self, fixture_id):
        data = load_fixture(fixture_id)
        left, right, terms = data["internal"], data["counterparty"], data["terms"]
        left_hash, right_hash, terms_hash = digest(left), digest(right), digest(terms)
        key = {name: left.get(name) for name in ("account_id", "currency", "unit", "reporting_timezone", "window_start", "window_end", "billable_event", "status_basis")}
        for name in ("window_start", "window_end"):
            try:
                key[name] = instant(key[name]).isoformat()
            except (ValueError, OverflowError):
                pass
        rules = {"version": data["rules_version"], "threshold_percent": data["review_threshold_percent"], "owner": data["owner"]}
        rules_hash = digest(rules)
        case_id = "REC-" + digest(key)[:16]
        run_id = "CMP-" + digest([case_id, left_hash, right_hash, terms_hash, rules_hash])[:16]
        with self.workflow.tx() as c:
            existing = c.execute("SELECT * FROM recon_runs WHERE id=?", (run_id,)).fetchone()
            current = c.execute("SELECT * FROM recon_cases WHERE id=?", (case_id,)).fetchone()
            if existing:
                # Replaying old report bytes never rolls a corrected case backward.
                return self.state(c)
            if current is not None:
                previous = c.execute("SELECT * FROM recon_runs WHERE id=?", (current["current_run_id"],)).fetchone()
                for side, candidate, sha in (("internal", left, left_hash), ("counterparty", right, right_hash)):
                    original_row = c.execute("SELECT payload FROM recon_snapshots WHERE sha256=?", (previous[side + "_sha256"],)).fetchone()
                    original = json.loads(original_row["payload"])
                    if candidate.get("source") == original.get("source") and candidate.get("report_id") == original.get("report_id"):
                        old_rev, new_rev = original.get("revision"), candidate.get("revision")
                        if isinstance(new_rev, int) and isinstance(old_rev, int) and (new_rev < old_rev or (new_rev == old_rev and sha != previous[side + "_sha256"])):
                            raise StaleReconciliation("Older or conflicting immutable report revision; original current evidence preserved")
            result = compare_reports(left, right, data["review_threshold_percent"])
            result["rules_sha256"] = rules_hash
            now = self.workflow._get(c, "now")
            drafts = build_drafts(result, data, now)
            if current is None:
                c.execute("INSERT INTO recon_cases VALUES(?,?,?,?,?,?,?,?,?)", (case_id, left.get("account_id"), data["owner"], 1,
                          "blocked" if result["result"] == "blocked" else "review_required" if result["result"] == "discrepant" else "matched",
                          None, now, now, None))
            for value, sha in ((left, left_hash), (right, right_hash), (terms, terms_hash), (rules, rules_hash)):
                c.execute("INSERT OR IGNORE INTO recon_snapshots VALUES(?,?,?)", (sha, canonical(value), now))
            c.execute("INSERT INTO recon_runs VALUES(?,?,?,?,?,?,?,?,?,?)", (run_id, case_id, fixture_id, left_hash, right_hash,
                      terms_hash, data["rules_version"], canonical(result), canonical(drafts), now))
            version = current["version"] + 1 if current else 1
            status = "blocked" if result["result"] == "blocked" else "review_required" if current or result["result"] == "discrepant" else "matched"
            c.execute("UPDATE recon_cases SET version=?,status=?,current_run_id=?,updated_at=?,next_check_at=NULL WHERE id=?",
                      (version, status, run_id, now, case_id))
            self.workflow._audit(c, "reconciliation_corrected_report_reopened" if current else "reconciliation_compared", case_id,
                                 case_id=case_id, run_id=run_id, case_version=version, owner=data["owner"],
                                 result=result["result"], internal_sha256=left_hash, counterparty_sha256=right_hash,
                                 previous_decisions_preserved=True, external_effect=False, model_calls=0)
            return self.state(c)

    def decide(self, case_id, expected_run_id, expected_version, decision, note, evidence):
        if decision not in ("review_complete", "request_correction"):
            raise ValueError("Unknown synthetic finance decision")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise ValueError("Expected case version must be a positive integer")
        if not all(isinstance(v, str) and 1 <= len(v.strip()) <= 2000 for v in (expected_run_id, note, evidence)):
            raise ValueError("Run reference, decision note and verification evidence are required")
        with self.workflow.tx() as c:
            case = c.execute("SELECT * FROM recon_cases WHERE id=?", (case_id,)).fetchone()
            if case is None:
                raise ValueError("Unknown reconciliation case")
            if case["current_run_id"] != expected_run_id or case["version"] != expected_version:
                raise StaleReconciliation("Report or case changed; refresh before recording the finance decision")
            run = c.execute("SELECT * FROM recon_runs WHERE id=?", (expected_run_id,)).fetchone()
            result = json.loads(run["result"])
            if result["result"] == "blocked" and decision == "review_complete":
                raise ValueError("Unproven/unaligned reports cannot receive a final reconciliation conclusion")
            if case["status"] == "resolved":
                raise StaleReconciliation("Case is already resolved; a new report is required to reopen review")
            now = self.workflow._get(c, "now")
            next_check = (instant(now) + timedelta(hours=24)).isoformat() if decision == "request_correction" else None
            c.execute("INSERT INTO recon_decisions(case_id,run_id,case_version,decision,note,evidence,actor,created_at) VALUES(?,?,?,?,?,?,?,?)",
                      (case_id, expected_run_id, expected_version, decision, note.strip(), evidence.strip(), "Synthetic local finance reviewer", now))
            c.execute("UPDATE recon_cases SET status=?,version=version+1,updated_at=?,next_check_at=? WHERE id=?",
                      ("resolved" if decision == "review_complete" else "awaiting_correction", now, next_check, case_id))
            self.workflow._audit(c, "reconciliation_finance_decision", case_id, case_id=case_id, run_id=expected_run_id,
                                 bound_case_version=expected_version, owner=case["owner"], decision=decision,
                                 evidence=evidence.strip(), note=note.strip(), next_check_at=next_check,
                                 financial_effect=False, dispatch_enabled=False, actor="Synthetic local finance reviewer")
            return self.state(c)

    def state(self, c=None):
        if c is None:
            with self.workflow.db() as opened:
                return self.state(opened)
        cases = [dict(r) for r in c.execute("SELECT * FROM recon_cases ORDER BY created_at,id")]
        runs = []
        for row in c.execute("SELECT * FROM recon_runs ORDER BY rowid"):
            run = dict(row)
            run["result"], run["drafts"] = json.loads(run["result"]), json.loads(run["drafts"])
            runs.append(run)
        return {"label": "Generic reconciliation — synthetic immutable report fixtures and assumed terms",
                "mode": "deterministic fixture comparison; drafts and internal finance review only",
                "fixtures": FIXTURES, "cases": cases, "runs": runs,
                "decisions": [dict(r) for r in c.execute("SELECT * FROM recon_decisions ORDER BY id")],
                "effects": {"external_effects": False, "model_calls": 0, "settlement_enabled": False, "dispatch_enabled": False},
                "limitations": ["Immutable fixture controls do not prove a live provider's mutable-report consistency",
                                "Local finance reviewer is a synthetic operator, not production authentication or signatory authority",
                                "A resolved review case does not record actual payment or authorize collection dispatch"]}
