# Employer checkpoint — generic affiliate foundation

2026-11-04 · reproducible revision/tag: **demo-pagination-proposal-r1** (parent 4cdcfcb). Previous **demo-review-followthrough-r1** remains preserved. Sponsor acceptance: **pending**. All required Codex/Gemini architecture responses are received; findings/readiness are tracked separately. Current code is not independently approved by those historical reviews.

## Reproduce

Current preview: http://127.0.0.1:8013. To run a separate demonstration without replacing the preserved demo, use the existing installed environment:

```sh
cd /Users/shenghangwang/.codex/visualizations/2026/11/04/01a1a475-c70b-7342-89b1-f642577c991c/everflow-foundation
git show --no-patch demo-pagination-proposal-r1
npm --prefix frontend run build
EVERFLOW_DEMO_DB=.run/employer-checkpoint.sqlite3 .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8014 --workers 1
```

Open http://127.0.0.1:8014. **Reset demo** resets only this selected synthetic database. Stop with Ctrl+C; state survives restart. Fresh dependency setup, if needed: select Python3.10+ and run `EVERFLOW_PYTHON=/path/to/python3 ./scripts/setup.sh` before the commands above. Current dependency installation was already available; no new-machine install is claimed.

## Ten-minute walkthrough and expected owned outcomes

1. **BD + commercial review:** Harbor Partners → Draft outreach → Run policy & mock send → Payout FAQ → Process reply → Clear interest → Process reply. The reply cancels follow-up and leaves **Demo BD owner** accountable. Prepare the proposal using a note requesting USD50/Net-7; the body must retain approved fixture USD12.50/Net30. Record a commercial review note and evidence. Outcome: **reviewed draft**, owner/terms/evidence retained; no contract approval or dispatch.
2. **Recurring AM:** Activation & AM → select Harbor → create case → signed-only evidence stays pending → complete current readiness + recorded owner decision. Low activation → tracking failure assigns **Demo integration owner** → +24h/Tick → repair evidence → recorded outcome verification. Outcome: issues resolved and exactly one next review. +7d makes stale health **unknown**, with an owned refresh; fresh health + review closes that cycle. Cancellation prevents later tasks/resumption.
3. **Ops/finance:** Reconciliation → Paged source changes during fetch → compare. Changed row contents with identical totals must give **blocked**, unknown variance and no draft. Record correction request → +24h/Tick shows one due finance task → Complete corrected paged evidence → compare → record fresh finance review. Outcome: **Demo finance owner** resolves the case with both failed/current proofs retained. Identical page reads without upstream proof must remain blocked. This demonstrates A05 Ops follow-through; live A06 Traffic Guard control is conditional.

## Verified now / conditional

Verified synthetic local paths: BD/recovery; activation and recurring AM; exact reconciliation/DST and bounded page acquisition; proposal preparation/owner review; duplicates, cancellation, material-change invalidation and persistence. Relevant checks pass: **119 backend/API/export**, **54 browser**, **9 finance/page-process** and **11 AM/proposal-process** checks, plus build. Evidence and exact hashes: `evidence/tests/pagination-v1/manifest.json`. Reproduce checks with `.venv/bin/python scripts/check_backend.py`, `.venv/bin/python scripts/check_reconciliation_restart.py`, and `.venv/bin/python scripts/check_am_restart.py`; browser command/environment is in the manifest.

Conditional: actual tenant read/schema/snapshot consistency, channel identity/ingestion/idempotency, approved billing/legal/signature workflows, live campaign controls, paid inference quality/usage/budget and production authentication. No approved matching runtime account/budget was supplied; no paid model or live business call was made. Git synchronization uses the already authorized connection. Last-page completion/repeated stable reads cannot prove an upstream snapshot; uncertain evidence stays owned, not authoritative. Insurance is optional/omitted, and the complete factory is not a minimum commitment.

## Decisions requested at acceptance

| Employer decision | Proposed demo default — unconfirmed business rule |
|---|---|
| Outreach: approved sources/channel/sender/recipients; organization identity, opt-out scope/cooldown and handoff owner | Fixture recipients only; immediate contact opt-out; no inferred company/domain merge or sibling-send authority. 72 elapsed hours after accepted initial dispatch, UTC; cancel on reply/opt-out/handoff; two standard rounds. Confirm before any live acquisition. |
| Billing: billable event/status, accepted vs rejected/reversed outcomes, currency, authoritative reports/IDs, settlement and billing timezone | Synthetic USD12.50 per approved demonstration event; Net30 after approved reconciliation. Baseline UTC; separate New York DST example. Strict >5% review threshold, not a confirmed SLA or actual receivable. Finance owner must adopt real definitions/timezone. |
| Ownership/cadence and acceptance timing | Demo role owners; configurable 24h readiness/health freshness, first-outcome/issue and finance checks; 168h AM recurrence. Boss/business sponsor intended evaluator; exact checkpoint and working window **TBC**. Record pass/fail/conditional and material corrections. |
| Handover and external access | Existing written agreement governs; unspecified particulars unresolved. Supply permitted read-only tenant sample and model/data/prices/budget only for a scoped live validation. |

Next local priority: versioned integration configuration → sandbox evidence → owner release, with invalidation on configuration/test change. Remaining business decisions do not block independent reversible work.
