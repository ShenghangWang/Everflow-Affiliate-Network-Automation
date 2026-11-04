# Everflow affiliate-network automation foundation

Day 1 delivery candidate · 2026-11-04 · adopted work instruction: Engineering Delivery Brief v1.3. This engagement builds reusable BD, negotiation, onboarding, recurring AM and Ops capabilities. Insurance is an optional illustration, not the project target or a confirmed employer business model. The baseline uses synthetic B2B affiliate prospects; no consumer insurance workflow is required or included.

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

The original repository contains only `.git` and no commits/code/instructions. All three supplied originals are readable and hashed. React and Python dependencies are installed. The local application launches, the frontend builds, 44 backend/API tests pass and 14 browser checks pass. Genuinely fresh setup/build and process-restart evidence is retained separately. No employer working window has been supplied: these floors are based on the inspected local environment, not a promise about unverified tenant delivery.

| Day | Evidence-based minimum floor | Dependencies and extension |
|---|---|---|
| 1 | Complete compact M01–M06/A01–A06 HLD, traceability, source dispositions, risks, review packet/status, walkthrough and environment/launch result | All source texts accessible. Tenant/Gemini gaps stay explicit. Start core implementation immediately. |
| 2 | Connected React/Python fixture path with persisted state, deterministic authorization, reply/follow-up/handoff and tested failure handling | Local dependency installation/loopback launch must pass. Live credentials are not required for the mock path. Resolve principal checks before adding depth. |
| 3 | Reproducible setup, relevant T01–T12 actual evidence, material defect resolution or explicit failure, capability/mode matrix and operating handover | Real provider contract/usage tests conditional on approved access. Shared production deployment is not promised by a local demo. |

Verified additional work: generic BD path/recovery, source/outcome cohorts, synthetic channel/economics stress, owned internal case follow-through and source-event replay integrity. Ranked remaining queue (pull whenever ready): (1) fixture reconciliation discrepancy → owned finance issue → closure; (2) recurring AM activation/health follow-through; (3) validated integration configuration assistance; (4) authorized read-only Everflow snapshot; (5) genuine approved runtime language evaluation. Missing credentials do not block independent items. Optional example configuration is lower priority and adds no mandatory scope. Preserve the last verified revision while each additional increment is checked.

## Package index

- [requirements.md](requirements.md): source inventory, source locators, all mandates/roles, source issues, proposed KPI definitions and scope boundaries.
- [architecture.md](architecture.md): workflow contracts, diagrams, data/authority/integrations, reliability, bounded AI, acquisition resilience and decisions.
- [delivery.md](delivery.md): actual outcomes, launch/test evidence, Day 1 gates, walkthrough, capability/mode status and unresolved dependencies.
- [reviews/](reviews/): frozen input manifest/prompt, genuine original review and adjudication; Gemini status is explicit.
- [evidence/intake/sources.json](evidence/intake/sources.json): exact original paths, hashes and access evidence. Full original text extracts have paragraph/page locators; DOCX page numbering is not guessed.

## Working location

The supplied project at `/Users/shenghangwang/Documents/ChatGPT/Everflow Affiliate Network Automation` is readable but a write probe failed with `PermissionError: [Errno 1] Operation not permitted`. This complete candidate is built in this session's permitted `everflow-foundation` directory; no files were changed in the original project. Final transfer/destination follows the written engagement agreement once its relevant terms and access are available. This access failure is distinct from an automatic approval rejection; no such rejection has been received.

## Run and verify

Verified on Python 3.12.14 (bundled), Node 26.0.0/npm 11.12.1 (build), and Chromium 149.0.7827.55 (browser check via bundled Node 24.22.1). Exact installed versions are in evidence. Choose an installed Python 3.10+ interpreter; this machine’s system Python 3.9 is insufficient for the setup script.

```sh
# On this inspected machine; on another machine select its Python 3.10+ interpreter.
EVERFLOW_PYTHON=/Users/shenghangwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 ./scripts/setup.sh
./scripts/run.sh
```

Open [local demo](http://127.0.0.1:8000). Use **Reset demo** to reimport the generic synthetic fixtures and reset the simulated clock. Draft → Run policy & mock send → +71h / +1h, or inject a payout FAQ, clear interest, opt-out or ambiguous reply. **Source & outcomes** shows provenance/cohorts and owned cases; **Six-role coverage** separates full design from implemented depth. Stop the server with **Ctrl+C** in its terminal. State persists in `data/demo.sqlite3` across restart; reset is an explicit destructive operation on synthetic demo data only.

```sh
.venv/bin/python scripts/check_backend.py
npm --prefix frontend run build
```

Optional browser check uses a Playwright installation plus its compatible Chromium (`PLAYWRIGHT_PACKAGE` and `CHROMIUM_EXECUTABLE` can select them): `node scripts/check_ui.mjs`. It resets synthetic demo data and requires the server on port 8000. Actual commands and results, including initial failures and recovered prerequisites, are in `delivery.md` and `evidence/tests/`.

Keep the demo on `127.0.0.1` with one worker. Do not publish this local unauthenticated prototype as a shared service. Paid inference is disabled: the replacement interface and output validation are present, template output is explicitly offline fallback, and genuine model/usage evaluation awaits approved credentials/data/prices/budget. Full HLD coverage does not imply all-six-role production implementation.

## Current checkpoint

Complete M01–M06 / A01–A06 HLD and traceability are delivered. Current evidence: **44 backend/API tests**, **14 browser checks**, build and independent fresh setup/restart pass locally. The replaceable inference boundary is validated in template mode; genuine runtime quality, deadlines/token budgets and provider billing remain unverified. No live business effects or paid model calls occurred.

Independent Codex R1 found three architecture gaps; all were accepted and resolved in design, with a genuine focused R2 follow-up. Gemini is **pending**, with an initial blind export matching Codex’s original R1 inputs. After Gemini’s first independent verdict, R2 is available for the corresponding update check. Overall Day 1 review/integration gate is **CONDITIONAL**; completed-package acceptance by the boss/business sponsor is pending, exact checkpoint time TBC.

The first verified demo is preserved at `f101944` / `demo-core-verified-r1`; the improved verified candidate is retained at `demo-verified-r2`. Frozen review packets are historical inputs and accurately preserve earlier implementation statuses; current results are in delivery.md. Next task: fixture reconciliation with exact evidence and owned resolution, as the ranked queue records. Existing written-agreement handover details remain unresolved; local archives are review conveniences, not additional contractual commitments or a completed external transfer.
