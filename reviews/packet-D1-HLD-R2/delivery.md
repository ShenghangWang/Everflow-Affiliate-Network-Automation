# Delivery evidence and walkthrough

Delivery candidate · 2026-11-04 Asia/Shanghai · work instruction v1.3. This record distinguishes planned design, local implementation and test results from actual vendor access, independent review and employer acceptance. The adopted minimum scope baseline and proposed material business defaults/daily floors are in `README.md`; traceability is in `requirements.md`; the full six-role HLD is in `architecture.md`.

## 1. Minimum commitment and actual outcomes

Day 1 floor: complete M01–M06 / A01–A06 architecture, traceability, acquisition assessment, source/access register, original review or explicit pending packet, walkthrough and verified launch baseline. No dependency on live outreach, tenant mutations or paid inference. The original project had no application code. All three provided originals were readable; the different unsuffixed factory filename in the brief is not presumed identical. No repository instruction file was discovered in the searched project/workspace/ancestors.

Actual intake outcomes: source bytes/hashes/full paragraph/page extracts retained; original binary copies preserved; write restriction and network/dependency probes recorded; React and Python dependencies installed in the permitted session workspace. A connected React/FastAPI/SQLite BD path now passes 28 backend/API tests and 12 actual browser checks; the built UI was visually inspected at desktop/mobile sizes. The original project write failure did not change the local scope floor. Local work continued while employer integration access and a Gemini route remained absent. No automatic approval rejection was received.

Additional increments are brought forward after their relevant checks; reaching a floor is a checkpoint. Queue and current implementation/evidence are updated below. A known working revision is retained before subsequent improvements; planned or merely coded work does not count as verified additional delivery.

## 2. Early launch and dependency feasibility

| Check | Observation / evidence | Consequence and recovery |
|---|---|---|
| Original repository | `.git` only; `git status --short --branch` → `## No commits yet on master`; no tracked app/config/AGENTS | Start a modular local application; no inherited conventions invented. |
| Target write | Creating `.../Everflow Affiliate Network Automation/evidence` → `PermissionError: [Errno 1] Operation not permitted` | Work in permitted `everflow-foundation`; source archive enables transfer. Original directory remains untouched. |
| Dependency discovery | System Python lacked FastAPI/uvicorn; bundled Python 3.12 provided DOCX/PDF readers; Node/npm present | Use project virtual environment and pinned packages; document actual versions rather than assume host capability. |
| Initial registry | `npm view react version --fetch-timeout=15000 --fetch-retries=0` → `ENOTFOUND registry.npmjs.org` | Approved network rerun installed pinned React/build packages; failure retained in `evidence/intake/launch-probes.json`. |
| Python web dependencies | `uv pip install --python .venv/bin/python fastapi==0.115.12 uvicorn==0.34.3` → installed 12 packages | Exact transitive pins in `requirements.lock`; Node exact resolution in `frontend/package-lock.json`. |
| Cache boundary | `uv pip freeze` could not write default uv cache | `uv --cache-dir /private/tmp/everflow-uv-cache pip freeze ...` succeeded. Use a task-local writable cache in setup. |
| Tenant/channel/inference | No configured matching credential environment names detected; no approved account/recipient/model scope supplied | No secret values read or logged. Abstract adapters and generic synthetic fixtures remain usable. This probe does not assert no credentials exist elsewhere. |
| Review | Codex CLI 0.134.0 present; Gemini CLI absent; no approved Gemini service route supplied | Fresh Codex context on frozen packet; identical Gemini export prepared; Gemini stays pending until genuinely run. |

Exact source/access records: `evidence/intake/sources.json`, `launch-probes.json`, `dependency-results.json`. No source requirement or installed client establishes an external account capability.

## 3. Selected path and capability status

Two dimensions are reported per capability. “Tested” requires evidence; “mock adapter” describes the provider boundary, even when the local engine is tested. No live model, tenant integration or real message is implied.

| Capability | Implementation status | Execution mode | Evidence / limit |
|---|---|---|---|
| Complete six-role architecture and original traceability | Designed-only | Deterministic workflows / bounded language design | HLD and source register; separate gate evaluation below |
| Generic sourced intake, scoring, BD draft/send/reply/handoff | Tested locally | Deterministic + template-fixture + mock adapter | 28 backend/API tests and browser checks; `evidence/tests/backend-tests.*`, `evidence/tests/ui/browser-results.json` |
| Durable outbox, 72-hour follow-up, suppression/recovery | Tested locally | Deterministic + mock adapter | Due/not-due/repeated tick, persisted reply race, opt-out/handoff, unknown outcome and restart checks. No external provider guarantee. |
| Replaceable inference boundary and conservative output validation | Tested locally | Template-fixture; live adapter fail-closed | Invalid output rejected to labeled fallback; unapproved adapter not called; paid inference disabled. Live task quality/token/deadline/atomic monetary reservation remain designed-only. |
| Six-role workflows beyond core | Designed-only, except tested internal issue follow-through | Mock/design by default | Internal case closure requires verification evidence and preserves handoff/suppression. This narrow increment is not a complete recurring AM implementation or all-six production claim. |
| Source/outcome cohort view | Tested locally | Deterministic synthetic observations | Two permitted fixture sources, normalization/dedupe/provenance, contacted-cohort reply denominator, unknown billable/economic data retained. Stress scenario is the next queue item. |
| Everflow reports, management actions, postbacks/webhooks | Blocked on tenant verification | No live external adapter | Official documentation is separate from employer permissions |
| Factory lifecycle and optional local/cloud/Jev routing | Designed-only | No production mutation engine | Complete factory/cluster not minimum commitment |
| Optional insurance example | Deferred / omitted | None | Generic baseline covers core without insurance-specific fields |

## 4. Observable acceptance and evidence ledger

T01–T12 come from v1.3 §6. Each result below is a local scoped result; an expected outcome or a unit test name alone is insufficient. Missing live-model/provider contracts remain explicit even if a fixture check passes.

| ID | Scope of check | Actual result at intake |
|---|---|---|
| T01 | Sourced lead → draft → authorized mock dispatch → reply → standard response/handoff; UI/persistence/owner | PASS local — backend connected path and browser draft/send/FAQ/handoff; persisted IDs, fact references and Demo BD owner recorded |
| T02 | Ten duplicate events and competing claims; one logical mock acceptance | PASS local — ten duplicate drafts/dispatch/events plus competing worker claims; one logical mock acceptance |
| T03 | Recipient/content/terms/policy edits/expiry/out-of-policy invalidation | PASS local — binding mutation/recipient/content/terms/policy expiry tests block prior authority; no unauthorized mock effect |
| T04 | Opt-out/human request/ambiguous and negated commercial language | PASS local — deterministic opt-out, requested human, negation/unknown/out-of-policy and round-cap cases; other language goes to owned review |
| T05 | Before/at due time, repeated ticks, reply/worker race | PASS local — 71h / 72h / repeated tick browser path; backend reply-between-claim-and-execution cancellation. External ingestion lag remains unmeasured |
| T06 | Known nonacceptance transient retry vs possible acceptance timeout | PASS local mock — known pre-acceptance retry cap and possible-acceptance timeout quarantine/reconciliation; no live provider contract verified |
| T07 | Pending and accepted action recovery across engine/process restart | PASS local domain — pending/accepted restart and expired-claim quarantine; separate fresh process restart being verified |
| T08 | Invalid/malformed model output, unsupported terms/facts, hostile inputs | PARTIAL — malformed/unsupported candidate output, invented terms and hostile inputs rejected or reviewed locally. No genuine model held-out evaluation run |
| T09 | Provider unavailable/attempt limit/token/deadline/budget exhaustion | PARTIAL — paid/live inference disabled and unapproved adapter never invoked. Actual provider token/deadline/attempt/atomic monetary-budget enforcement is designed-only |
| T10 | Attempt-inclusive usage/cost and cache/policy invalidation | PARTIAL — versioned template cache keys and current authority tested; zero provider calls/cost accurately shown, other costs unknown. Actual/uncertain model billing not exercised |
| T11 | Local-only mock configuration, no unintended effects/frontend secrets | PASS scoped local — loopback Host/browser mutation Origin restrictions, synthetic-only recipient/mock boundary and browser modes; production RBAC/tenant isolation not implemented |
| T12 | Fresh setup, backend tests, frontend build and exercised UI | PARTIAL — 28 backend/API tests, Vite build and 12 browser checks pass; fresh independent setup/restart verification in progress |

Residual production checks cannot be demonstrated by fixtures: provider idempotency/lookup and acceptance semantics; reply ingestion latency; tenant permissions and rate limits; real inference quality/usage/cost; production identity/tenant isolation; multi-user concurrency; backup/restore at operational scale. Preserve unknown outcomes and missing costs as unknown.

## 5. Day 1 gates and separate acceptance states

| Gate | Result at intake | Evidence / open item |
|---|---|---|
| G1 All M/A workflows substantive | PASS design coverage | `requirements.md` traceability + `architecture.md` contracts |
| G2 Source disposition / example separation | PASS for provided sources | Original extracts/hashes and S01–S08; generic baseline; alternate F version identity explicit |
| G3 Negotiation/dispatch/AM/Ops authority/failure paths | PASS design coverage | Live policy missing; synthetic policy does not grant external authority |
| G4 Verified integration facts / isolated unknowns | CONDITIONAL | Official docs can be checked; tenant-specific operations await employer access |
| G5 Rules/AI cost/quality boundary | PASS design coverage; runtime inference checks partial | No inference budget/provider supplied; deterministic core proceeds |
| G6 Critical findings/reviews | CONDITIONAL | Genuine Codex record and Gemini original required; export pending alone is not Gemini completion |
| G7 Three-day path feasible with evidence | CONDITIONAL until launch/tests complete | Local prototype floor; live integration and all-six production not promised |
| G8 Acquisition evidence/decisions/validation | PASS design/research | Dated research distinguished from employer facts and hypotheses |

Separate dimensions: **design coverage** all M01–M06 / A01–A06 substantively covered; **verified employer integrations** zero; **independent reviews** fresh Codex in progress / Gemini pending; **scope baseline** adopted by user; **deliverable acceptance** pending. Do not report an aggregate percentage as approval.

## 6. Day 1 walkthrough

Proposed 20-minute evaluation by the boss/business sponsor. Exact checkpoint time is TBC. Readiness by the end of Day 1’s working window is a planning target, not a confirmed meeting. The working window itself is still unspecified:

1. **Scope and evidence (3 minutes).** Show exact three readable originals, source hashes/locators, work brief v1.3, six mandates and six roles. Show optional insurance is absent and no employer operating model inferred.
2. **Architecture (5 minutes).** Trace a B2B lead through permission evidence, qualification, approved facts, deterministic authority, outbox and owned handoff. Trace one ongoing AM health/issue cycle and an Ops discrepancy/unknown-action recovery. Show factory lifecycle as a separate delivery capability map.
3. **Decisions (3 minutes).** Explain rules versus bounded language use, commercial authority, data ownership, integration unknowns, runtime budget and local/production deployment boundary.
4. **Acquisition resilience (3 minutes).** Present dated observations and limits, source concentration/unknown attribution/non-overlapping costs, platform bypass hypothesis, owners and falsifiable validation steps. Architecture does not guarantee revenue or survival.
5. **Runnable evidence (4 minutes when verified).** Reset generic fixtures, draft English outreach, run synthetic policy and mock send, advance fake time, inject reply/opt-out/handoff, show audit/owner/mode and restart persistence. Never label template output as a live model.
6. **Review and decision (2 minutes).** Show frozen input revision, original Codex finding/status, pending or genuine Gemini record and adjudication. Evaluate eight gates; capture explicit sponsor corrections/deliverable acceptance. Report minimum outcomes, additional verified increments, blockers/owners and next queue item.

Day 3 handover adds fresh setup, relevant T01–T12 evidence, exception/recovery, any additional verified workflows, actual mode/cost status and remaining production prerequisites. Do not fabricate production soak, vendor contract tests or sponsor acceptance.

## 7. Dependencies, risks and production release prerequisites

| Dependency / risk | Owner | Impact and independent work |
|---|---|---|
| Checkpoint time, working window and written-agreement handover details | Sponsor | Boss/business sponsor is intended evaluator; exact meeting and working window TBC. Existing written engagement agreement governs handover; it is not available here and unspecified items stay unresolved. Local package/evidence continue |
| Names behind BD/AM/Ops/Finance/Integration role owners | Sponsor/business lead | Demo uses explicit role owners, not real personnel assignment |
| Approved offers, terms and commercial policy | Commercial owner | Live binding language/actions blocked; exact synthetic values illustrate controls |
| Source/channel eligibility, sender/recipients/suppression scope | BD/channel owner | Live outreach blocked; permitted-source fixtures/mock transport continue |
| Everflow tenant role/region/API/features/report semantics | Integration owner | Live report and mutation verification blocked; abstract interfaces, fixtures, schemas continue |
| Runtime provider prices/data boundary/evaluation budget | Inference owner/sponsor | Paid inference disabled; adapter/templates/held-out evaluation plan continue |
| Approved Gemini route | Sponsor/reviewer | Required Gemini review pending; same frozen packet ready; no substitution by Codex |
| Reply not ingested before external dispatch | Channel/integration owner | Local reply race test cannot eliminate external ingestion lag; use freshness/grace/recheck and alert |
| Shared production operation | Engineering/security/Ops | Implement and test identity/tenant roles, CSRF/origins, secret store/redaction, concurrency, migration/backup/restore, monitoring/kill-switch/recovery, provider contracts before release |

All material gaps have an owner and validation step in the HLD/source register. Normal reversible changes proceed inside the assignment. Real messages, signatures, payouts, disputes, collection dispatch and routing/cap changes require the corresponding approved envelope and immediate pre-execution revalidation.

User clarification (2026-11-04): the minimum baseline is adopted; architecture covers every assigned workflow; inference adapter/validation are required with template fallback and genuine calls conditional on approved access/budget; daily floors do not cap work; handover follows the existing written agreement, unavailable here. The configurable 72-hour no-response demonstration is a proposed business rule, separate from the engagement’s three working days.

## 8 Actual verification and preserved evidence

- Backend/API: `.venv/bin/python scripts/check_backend.py` → exit 0, **28 tests**, 1.470 seconds, genuine log and code hashes in `evidence/tests/backend-tests.{log,json}`. An earlier missing-httpx failure is preserved under `backend-before-httpx-install.*`; dependency installed and affected suite rerun.
- Frontend: `npm --prefix frontend run build` → exit 0, Vite 7.2.2, 23 modules. An initial root-directory invocation failed because package.json is in frontend; the documented command includes the correct location.
- Browser: bundled Node + `scripts/check_ui.mjs` → **12 checks pass**, Chromium **149.0.7827.55**, zero browser JS/page errors. Exact results and screenshots in `evidence/tests/ui/`. Desktop and mobile screenshots were visually inspected; no clipped panels or page overflow observed. Installed Playwright expected absent cache revision 1234; existing browser revision 1228 was explicitly selected. Restricted browser launch then failed with `bootstrap_check_in ... Permission denied (1100)`; approved local browser execution passed. These are prerequisite recoveries, not a claim the initial environment worked without changes.
- Browser demonstrated accepted mock outreach, before/due 72-hour follow-up, idempotent repeated tick, approved USD 12.50 synthetic FAQ, reply cancellation, owned clear-interest handoff, evidence-backed synthetic case closure that preserves human authority, two-source unknown economics, role-depth labels and responsive layout. Model calls: **0**. Real dispatches: **0**.
- Fresh installation/process restart is an independent check in progress. Do not call it passed until its exact result is recorded.

Additional verified outcomes beyond the Day 1 architecture floor: connected BD core with durable mock execution, two-source cohort view and internal AM issue follow-through. No additional outcome is counted merely because its code exists. Next dependency-ready increment: hypothetical channel-shift calculation, while preserving the verified core revision; live tenant/inference work remains dependent on approved access.
