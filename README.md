# Everflow affiliate-network automation foundation

Local prototype and Day 1 architecture · updated 2026-11-04 · adopted work instruction: Engineering Delivery Brief v1.3. This engagement builds reusable BD, negotiation, onboarding, recurring AM and Ops capabilities. Insurance is an optional illustration, not the project target or a confirmed employer business model. The baseline uses synthetic B2B affiliate prospects; no consumer insurance workflow is required or included.

**Current verification:** 68 backend/API tests, 27 browser checks and six separate process-restart checks pass. The frontend build passes. Normal commits/pushes synchronize this existing working copy to the intended public [GitHub repository](https://github.com/ShenghangWang/Everflow-Affiliate-Network-Automation). The user superseded earlier isolation/cloud/broker requirements; execution continues locally under current permissions.

## Proposed acceptance card

**Minimum scope baseline adopted by the user on 2026-11-04; deliverable acceptance is pending.** Internal checks, independent review and boss/business-sponsor acceptance are separate records. The user’s written clarification is retained in `evidence/intake/sponsor-clarification-2026-11-04.md`.

| Item | Proposed agreement |
|---|---|
| Day 1 scope | Complete system HLD and original-source traceability for M01–M06 / A01–A06; source/access register; acquisition-resilience decisions; independent review records or explicit pending packet; launch baseline and walkthrough |
| Minimum prototype outcome | React + Python local B2B BD path: sourced synthetic leads → explainable qualification → English draft with replaceable inference adapter and output validation → deterministic authorization → durable mock send → approved standard reply or owned handoff; 72-hour follow-up, suppression, recovery and audit |
| Daily floors | D1 architecture/evidence/launch baseline; D2 connected durable business path and principal checks; D3 reproducible setup/demo, relevant T01–T12 results, defect disposition and handover. Pull later work forward as dependencies clear. |
| Effects and authority | Current local mode: mock transport and labeled offline template fallback. Include a replaceable inference adapter and output validation; demonstrate genuine model calls when approved runtime credentials and budget are available. Synthetic terms/policies cannot authorize real messages, contracts, payments or campaign changes. Paid inference and live adapters need their applicable approved scope and budgets. |
| Hard checks | All 12 mandates/roles have substantive design; no inferred original content; invalid/expired authorization blocks effects; duplicate/race/restart behavior evidenced; unknown provider outcome never blindly resent; mode/cost labels visible; no fabricated live AI or integration evidence |
| Access needed | Actual Everflow role/region/enabled products and read-only sandbox docs/access; permitted channel/sender/recipients; current commercial terms and authority owner; approved model/evaluation budget; approved Gemini review route |
| Evaluation/checkpoint | Intended evaluator: boss/business sponsor. Exact checkpoint time: TBC. Plan readiness by the end of Day 1’s working window; this is a planning target, not a confirmed meeting. Exact working window is unresolved. Record PASS / FAIL / CONDITIONAL per gate; no deliverable acceptance is claimed. |
| Handover | Follow the existing written engagement agreement. That agreement has not been supplied/read in this workspace; final destination, transfer mechanism, ownership/retention and other unspecified handover items remain unresolved. The local review package contains source, core documents, evidence, review records and reproducibility instructions; this describes current contents, not additional contractual commitments. |
| Material defaults to confirm | No-response follow-up = configurable 72 elapsed hours after initial dispatch acceptance (UTC), an unconfirmed business rule shown with a simulated clock and reply/opt-out/handoff cancellation. This interval is separate from the engagement’s three working days. Two standard response rounds, named role owners and commercial definitions including “流水消耗” remain unresolved/defaults. |

## Daily minimum commitments and ranked continuation

At initial intake the original repository contained only `.git`; its accessible original sources were retained and hashed. The existing history is now preserved through the verified demo tags and normal public Git synchronization. The 44 backend/API +14 browser baseline was reproduced before the reconciliation increments. Current source/test manifests are in `evidence/tests/reconciliation-v2/`. Exact working window and sponsor checkpoint time remain TBC; local results do not promise unverified tenant delivery.

| Day | Evidence-based minimum floor | Dependencies and extension |
|---|---|---|
| 1 | Complete compact M01–M06/A01–A06 HLD, traceability, source dispositions, risks, review packet/status, walkthrough and environment/launch result | All source texts accessible. Tenant/Gemini gaps stay explicit. Start core implementation immediately. |
| 2 | Connected React/Python fixture path with persisted state, deterministic authorization, reply/follow-up/handoff and tested failure handling | Local dependency installation/loopback launch must pass. Live credentials are not required for the mock path. Resolve principal checks before adding depth. |
| 3 | Reproducible setup, relevant T01–T12 actual evidence, material defect resolution or explicit failure, capability/mode matrix and operating handover | Real provider contract/usage tests conditional on approved access. Shared production deployment is not promised by a local demo. |

Verified additional work: durable BD core/recovery, two-source cohorts and hypothetical economics, internal issue follow-through, source-event replay integrity, exact fixture reconciliation and the complete owned correction-to-resolution cycle. Ranked remaining queue: (1) fuller activation/recurring AM health cycle; (2) contract-tested integration mapping; (3) authorized read-only Everflow snapshot; (4) genuine approved runtime language evaluation. Pull dependency-ready work forward without waiting for another calendar day. Live effects and spending still need their applicable authority; optional insurance examples add no mandatory scope.

## Package index

- [requirements.md](requirements.md): source inventory, source locators, all mandates/roles, source issues, proposed KPI definitions and scope boundaries.
- [architecture.md](architecture.md): workflow contracts, diagrams, data/authority/integrations, reliability, bounded AI, acquisition resilience and decisions.
- [delivery.md](delivery.md): actual outcomes, launch/test evidence, Day 1 gates, walkthrough, capability/mode status and unresolved dependencies.
- [reviews/](reviews/): frozen input manifest/prompt, genuine original review and adjudication; Gemini status is explicit.
- [evidence/intake/sources.json](evidence/intake/sources.json): exact original paths, hashes and access evidence. Full original text extracts have paragraph/page locators; DOCX page numbering is not guessed.

## Working location

The existing working copy is `/Users/shenghangwang/.codex/visualizations/2026/11/04/01a1a475-c70b-7342-89b1-f642577c991c/everflow-foundation`. The original Documents directory rejected writes during intake; no replacement clone or destructive reset was used. The current user authorizes local execution/current permissions, existing Git authentication and routine non-forced commits/pushes to this repository. Earlier isolation/cloud/scope-receipt/custom-broker requirements are superseded. An approval-service interruption during a server launch was retained and later cleared through the normal approval route; it is not a remaining blocker. Contractual handover items remain governed by the supplied directions and the existing written agreement; unspecified obligations are unresolved.

## Run and verify

Verified on Python 3.12.14 (bundled), Node 26.0.0/npm 11.12.1 (build), and Chromium 149.0.7827.55 (browser check via bundled Node 24.22.1). Exact installed versions are in evidence. Choose an installed Python 3.10+ interpreter; this machine’s system Python 3.9 is insufficient for the setup script.

```sh
# On this inspected machine; on another machine select its Python 3.10+ interpreter.
EVERFLOW_PYTHON=/Users/shenghangwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ./scripts/setup.sh
./scripts/run.sh
```

Open [local demo](http://127.0.0.1:8000). Use **Reset demo** to reimport the generic synthetic fixtures and reset the simulated clock. Draft → Run policy & mock send → +71h / +1h, or inject a payout FAQ, clear interest, opt-out or ambiguous reply. **Source & outcomes** shows provenance/cohorts and owned cases. **Reconciliation** compares fixture reports and records version-bound finance decisions; **Six-role coverage** separates full design from implemented depth. Stop the server with **Ctrl+C** in its terminal. State persists in `data/demo.sqlite3` across restart; reset is an explicit destructive operation on synthetic demo data only.

```sh
.venv/bin/python scripts/check_backend.py
npm --prefix frontend run build
# Separate loopback test: temporary database, three server starts, two restarts.
.venv/bin/python scripts/check_reconciliation_restart.py
```

Optional browser check uses a Playwright installation plus its compatible Chromium (`PLAYWRIGHT_PACKAGE` and `CHROMIUM_EXECUTABLE` can select them): `node scripts/check_ui.mjs`. It resets synthetic demo data and requires the server on port 8000. Actual commands and results, including initial failures and recovered prerequisites, are in `delivery.md` and `evidence/tests/`.

Keep the demo on `127.0.0.1` with one worker. Do not publish this local unauthenticated prototype as a shared service. Paid inference is disabled: the replacement interface and output validation are present, template output is explicitly offline fallback, and genuine model/usage evaluation awaits approved credentials/data/prices/budget. Full HLD coverage does not imply all-six-role production implementation.

## Current checkpoint

Complete M01–M06 / A01–A06 architecture and traceability remain delivered. The local generic BD and reconciliation paths are verified; this does not claim all-six-role production implementation. Current checks: **68 backend/API**, **27 browser**, frontend build and **six process-restart checks**. Evidence and exact source hashes: `evidence/tests/reconciliation-v2/`. The earlier fresh-environment installation evidence remains historical at its own source manifest; the new restart test uses a temporary database and separate processes, not a new environment installation.

Independent Codex architecture R1 and focused R2 records remain genuine and unchanged; three findings are design-resolved, with future affected release tests recorded. Gemini remains **pending** with the common blind packet ready. No model/channel/Everflow runtime access is inferred from fixture success. T08–T10 genuine model quality/token/deadline/billing checks, tenant contracts, sponsor completed-package acceptance, checkpoint time and unspecified written-agreement handover items remain conditional/pending.

Preserved tags: `demo-core-verified-r1`, `demo-verified-r2`, `demo-reconciliation-r1` and `demo-reconciliation-r2`. The first reconciliation checkpoint is commit `bb5c424`; the latter tag identifies the improved tested cycle. Routine synchronization is authorized; no force-push or history rewrite is part of this workflow.

## Fixture reconciliation and owned correction follow-through

The **Reconciliation** workbench implements aligned immutable synthetic reports → exact event/amount/status evidence → unsent discrepancy and overdue-reminder drafts → version-bound finance review. The default fixture reports USD 50.00 internally and USD 37.50 from the counterparty; event DEMO-E004 explains the USD 12.50 difference. These are assumed demonstration values, not company accounts or debt.

Incomplete/misaligned inputs retain unknown amounts and cannot receive a final conclusion. Duplicate comparisons preserve one logical case/run; corrected reports retain old bytes/decisions and reopen review. Stale run, terms, facts or rule versions reject a finance decision. A zero net difference does not hide offsetting row discrepancies. Hashes resolve to retained report/terms/rule payloads in SQLite.

Requesting a correction creates a durable task for **Demo finance owner**. The default **24 elapsed hours** is a separately configurable, assumed fixture rule—not the B2B 72-hour follow-up rule or an employer SLA. **+24h** and **Tick** demonstrate due-time handling. Repeated ticks create one in-app alert. A complete corrected snapshot completes the prior task, reopens finance review, and requires new verification evidence to resolve. Both task and final decision survive real server restarts.

Review never dispatches drafts, settles balances, records payment or changes payouts. Production finance identity, actual collection authority and mutable live-provider consistency remain prerequisites. The runtime is loopback-only with one worker; the demo is not a shared production service.
