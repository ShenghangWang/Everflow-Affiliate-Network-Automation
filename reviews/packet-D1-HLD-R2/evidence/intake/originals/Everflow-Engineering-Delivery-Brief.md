# Everflow Affiliate Network Automation
## Engineering Delivery Brief — v1.3

**Updated:** 2026-11-04  
**Purpose:** Instructions for a three-day engineering engagement. The design choices and acceptance cases below are proposed defaults until adopted by the sponsor. This file is a work brief; it is not evidence that architecture review, implementation or testing has already occurred.

## 1. Delivery outcome and source baseline

Deliver a complete **high-level system architecture on Day 1**, covering BD, negotiation, outreach, onboarding/integration, recurring AM and Ops. Deliver a tested React + Python prototype of the agreed business path by Day 3, bringing implementation forward whenever dependencies allow. Full architectural coverage and implemented coverage are separate deliverables. Establish a credible daily minimum commitment, then continue delivering additional achievable increments; the minimum is not a ceiling. Do not promise production implementation of all six business roles without supporting evidence.

Work as an engineering collaborator: inspect sources and existing code, recommend defaults, execute reversible work, retain evidence and keep dependencies isolated. Escalate business authority, unavailable access and material scope changes. Resolve ordinary implementation choices directly.

### Assignment scope and illustrative use cases

**The target is the reusable automation foundation and BD/AM/Ops capabilities established by the three assignment documents and the employer's explicit instructions. Insurance lead generation and distribution is only one optional illustrative use case. It is not an assigned target or a confirmed description of the employer's operations.**

Keep the project title, main architecture, requirement coverage and acceptance criteria centered on the assignment. Reuse applies within that scope; it does not require building an unrestricted platform for every industry.

If an insurance example is included:

- Classify it as **ILLUSTRATIVE USE CASE**. Label its dataset, rules, screens and walkthrough: **“Illustrative insurance use case — synthetic data and assumed rules; not an assigned requirement.”** Do not infer the employer's products, customers, revenue model or operating process from the example.
- Keep industry fields, message templates, buyer criteria and sample terms in separate configuration/fixtures or a small optional module. Core workflow, authorization, audit and adapter interfaces remain reusable. A generic affiliate-network dataset must still exercise the core path without the insurance example.
- Distinguish a B2B partner prospect from a consumer insurance enquiry. Do not silently turn the BD prospect record or outreach workflow into a consumer-lead distribution system.
- Use insurance examples to illustrate existing capabilities. A consumer-lead routing sketch or mock is optional, after the agreed core works and within the same work budget; it adds no mandatory feature, production integration or live authority.
- Record scenario assumptions separately from source requirements. Trace each mandatory deliverable to the assignment or an explicit sponsor instruction; an example alone cannot create or replace a requirement.

An example may be removed or substituted without changing the required system capabilities. Completing an insurance scenario does not substitute for M01–M06 or A01–A06 coverage.

### Required inputs and precedence

Read all available originals before finalizing source traceability:

1. 网盟自动系统需求文档.docx — affiliate-network business requirements.
2. 数字王国开发-第三版.pdf — development-factory vision.
3. 青蓝绩效文档-2.pdf — six business roles, proposed KPIs and phased operating model.
4. Employer clarifications, existing repository instructions and approved integration documentation.

If available, the architecture kickoff brief is secondary context. Reconcile it against the originals; summaries do not substitute for original-source verification. Compare content or hashes before calling similarly named files duplicates. If an original is unavailable, mark its source coverage unverified, proceed with a provisional design, and request only the missing material needed for final confirmation. Never claim to have read inaccessible files.

Governing employer clarifications, as relayed:

- “我第一天会验收完整构架”: complete system-level architecture on Day 1.
- “我们不是要脱离人，是要做系统底座”: build an automation foundation with accountable human ownership.
- Existing affiliate platform: Everflow; tenant role, enabled products and permissions still require verification.
- Architecture is to be challenged by Codex and Gemini independently.
- Follow-on implementation stack: React + Python.

Classify each important statement as **SOURCE REQUIREMENT**, **SPONSOR DIRECTION**, **VERIFIED CAPABILITY**, **PROPOSED DESIGN**, **ILLUSTRATIVE USE CASE**, or **UNRESOLVED DEPENDENCY**. Employer clarifications govern current scope where documents conflict; they do not establish undocumented vendor features or execution authority. Record the exact conflict and resolution. Preserve short Chinese excerpts and stable page/section locators.

### Business mandate coverage

| ID | Required outcome | Architecture evidence |
|---|---|---|
| M01 | Complete Day 1 architecture | Context, components, data ownership, all workflows, authority, integrations, deployment, failure handling and staged delivery |
| M02 | BD intake and onboarding/integration handoff | Lead intake, qualification, account ownership, agreed-terms intake, onboarding and technical setup |
| M03 | Negotiation automation | Needs discovery, approved offer retrieval, bounded proposals/counteroffers, objection handling, terms versions and escalation |
| M04 | Prospecting and customer contact | Permitted sourcing, personalized English outreach, authorized dispatch, replies, follow-up and handoff |
| M05 | Automated Ops | Everflow synchronization, metrics, anomaly investigation, reconciliation, overdue-reminder drafts and recovery |
| M06 | Recurring AM | Activation, account health, opportunities, routine communication, issue ownership and outcome follow-through |

The six roles from document 3 must also appear explicitly. They are business capabilities, not a requirement for six LLMs, services or autonomous processes.

| Role | Minimum trigger-to-outcome design | Mandate |
|---|---|---|
| A01 Outbound Hunter | Permitted lead → dedupe/profile/qualify → outreach → reply → owned BD handoff | M02–M04 |
| A02 Onboarding AM | Approved commercial terms → intake checklist/IO drafts → approval/signature → business record and activation owner | M02, M03, M06 |
| A03 Integration Bot | Authorized partner docs/config → field mapping → proposed ping-post/postback setup → sandbox checks → human release | M02, M05 |
| A04 Customer AM | Identified partner request → approved facts/action policy → response or authorized action → verification/escalation | M03, M06 |
| A05 Reconciliation | Aligned reports → deterministic comparison → discrepancy evidence → draft dispute/reminder → human decision | M05, M06 |
| A06 Traffic Guard | Fresh, validated metrics → deterministic anomaly rule → evidence/alert → permitted mitigation or approval → outcome check | M05 |

Carry proposed volume, speed, automation-rate and delivery KPIs into an aspiration/measurement register. Define denominators, quality, data freshness and workload before adopting a numerical commitment. A 60–90-day V1 aspiration and a four-week sequence do not establish a three-day production scope.

Preserve the business specification's concrete behaviors: multiple permitted lead sources with provenance; personalized English outreach; standard payout/traffic/settlement conversations during the first 2–3 rounds; follow-up after three days without a reply; clear-interest and difficult-final-negotiation handoff; proposal/payout-strategy/contract drafts from meeting notes; funnel/channel metrics; click/conversion spike investigation; overdue reconciliation and collection-email drafts. Mark missing commercial terms rather than inventing them.

## 2. Primary architecture decision: rules first, bounded AI

Use deterministic workflows for known processes. Add a model call where language understanding or generation supplies useful capability. Add autonomous or multi-agent execution only after a simpler baseline fails a defined evaluation and the added value justifies cost, latency and operating risk.

This is an engineering recommendation for this workload, not a claim that all LLM agents are unreliable or that deterministic code is free of defects. See the primary-source references in Section 9.

### Task-to-mechanism decision table

| Task | Default mechanism | Bounded model contribution | Failure behavior |
|---|---|---|---|
| Normalize/dedupe contacts, validate fields | Code, stable IDs, database constraints | Optional extraction from unstructured text | Missing/ambiguous fields remain unknown |
| Lead eligibility and scoring | Versioned eligibility rules and transparent weights | Evidence-backed profile extraction | Explain score; do not invent lead facts |
| Follow-up, reply limits, ownership and escalation | Persisted state machine and scheduler | Optional reply intent classification | Unknown intent goes to review |
| Known FAQ and approved terms | Approved records and templates | Wording or interpretation of a free-text question | No unsupported answer or invented commercial term |
| Outreach/proposal drafts | Approved facts/templates plus schema checks | Personalized English generation | Labeled template fallback or review |
| Negotiation and commercial authority | Deterministic policy over verified structured terms | Extract requested terms, summarize objections, draft allowed proposals | Ambiguity/out-of-policy terms require a human |
| Reconciliation, payouts and reporting metrics | Decimal/integer arithmetic, explicit units/windows | Optional explanation of computed results | No model arithmetic or autonomous settlement |
| Traffic/account-health monitoring | Data-quality checks, thresholds, baselines and schedules | Summarize evidence and propose hypotheses | Alert; do not assert fraud or cause from a spike alone |
| Partner integration setup | Schemas, field checks and sandbox contract tests | Interpret authorized docs and propose mappings | No generated code/config executes without validation |
| External execution | Validated application commands and separately authorized adapters | No direct model access to execution credentials | Reject invalid/unauthorized commands and audit |

An LLM-produced confidence score is not a permission grant. Jev is a learned decision-provider candidate, not a deterministic rules engine; its typed output still needs task-specific validation. Do not use a universal 0.90 threshold as evidence of commercial safety.

### Recommended starting structure

Prefer the existing repository's sound conventions. Otherwise start with a **modular React + FastAPI application**, a durable database-backed job/outbox worker and small adapters for inference, messaging and Everflow. Use one shared inference interface, not conversations between six role-agents.

For a single-user local prototype, SQLite and one worker are acceptable. Design PostgreSQL for a deployed multi-user service. Record concurrency/backup limits; do not expose an unauthenticated local prototype as a production service. Bind a local-only demo to loopback by default. Keep financial and execution policy in ordinary application code.

Compare this choice with one credible alternative and record the change condition. Do not add a vector database, message broker, agent framework, multi-host cluster or multiple model providers without a concrete unmet need. Approved-fact lookup may start with SQL or a small curated document set.

Separate business execution from the broader development-factory vision. Map the factory's request → decomposition → isolated change → tests → independent review → release/rollback lifecycle in the HLD. Local/cloud routing, Jev, conversational software changes and hierarchical coding agents are architectural options. A complete factory is not part of the minimum prototype commitment; useful additional work within the assignment may advance when dependencies, validation and business value justify it.

## 3. Authority, integration and reliable execution

### Automatic authority

The target product should automatically perform routine work within an explicitly approved policy. Keep humans responsible for policy ownership, important exceptions, difficult final negotiation and consequential commitments. The initial operating mode may require per-action approval; enable delegated automatic behavior only after the business owner approves the envelope.

Specify eligible accounts/offers/channels, permitted actions, currencies, exact terms or bounded concessions, frequency limits, reply-round limits, expiry and escalation ownership. Missing policy means no live execution authority. Prototype policies and terms must be labeled synthetic.

An authorization binds the target, recipient, content/terms version, policy version and expiry. Revalidate immediately before execution; material edits or expired/revoked policy invalidate authorization. Human approval and delegated-policy authorization are distinct audit events. Models cannot edit either.

Contracts/IOs, payouts, disputes, collections and routing/cap changes follow their approved authority. Prepare drafts where authority is absent. Emergency stops require a pre-authorized, tested deterministic rule and bounded operational control; otherwise alert and request a decision.

### State and data

Identify each entity's system of record. Everflow remains authoritative for platform entities and tracking/reporting actually confirmed in the tenant. The automation service owns workflow state, decisions, approvals, action attempts and its audit.

Model only what the scope needs: organization/contact, lead, conversation/message, negotiation and terms version, onboarding case, external mapping/offer reference, performance snapshot, issue/recommendation, authorization, action attempt and audit event. Separate business stage from execution status.

Use stable action IDs, unique inbox/outbox constraints, transactional state updates and a worker claim/lease or equivalent concurrency control. Distinguish scheduled, authorized, executing, succeeded, cancelled, failed and unknown-outcome states. Preserve pending actions across restarts.

External writes cannot be made exactly-once by a local ID alone. A timeout after possible provider acceptance enters outcome reconciliation; do not blindly resend. Use provider idempotency or lookup where supported. Otherwise quarantine for human resolution. State what the mock proves and what still requires a live provider contract.

For the proposed follow-up default, schedule at 72 elapsed hours after initial provider acceptance, stored in UTC; confirm calendar-day/business-day semantics with the owner. Recheck persisted reply, suppression, handoff and policy state when claiming and immediately before sending. Cancel pending follow-up on reply/opt-out/handoff. Test the reply/worker race. A reply not yet ingested from an external channel is a residual risk; document ingestion lag and any grace/recheck strategy.

### Integration evidence

For each selected Everflow/channel/inference operation, record official documentation, access role, verified method/path if known, data ownership, authentication, pagination, limits, error semantics, freshness, read/write class and evidence date. Until verified, use abstract names such as fetch_performance rather than invented endpoints.

Everflow's current documentation distinguishes Network, Affiliate and Advertiser APIs and describes webhooks; documentation availability does not establish the company's permissions or event coverage. Verify the actual tenant/region and contract. Use checkpointed polling with overlap/reconciliation where needed. Conversion postbacks and management webhooks are different interfaces.

Create a small channel capability table: who can initiate, recipient eligibility, replies, sender identity, opt-out/suppression, rate limits and access status. Prefer a mock transport for the prototype. A live test requires approved recipients/channel/scope. No cold outreach, financial change or campaign modification follows merely from this brief.

Make report windows, lateness/corrections, timezone, currency, units and metric denominators explicit. Define “流水消耗” with the business owner rather than choosing a financial meaning silently.

Keep tokens/credentials server-side, outside model input, source control and logs. External messages, documents and API text are untrusted data. Use schema validation and allowlisted application operations; never execute model-generated shell/SQL or grant arbitrary tools. Design roles/tenant boundaries, redaction, audit, failure queues, alerts, kill switches and recovery. A single-user local demo may document production identity controls without claiming to have implemented them.

## 4. Runtime cost and quality contract

These are **proposed prototype limits**, configurable through reviewed application settings. They are not measured provider capabilities.

- Known deterministic tasks use zero model calls. An ambiguous natural-language event may use one focused call; **at most two total provider attempts per event**, including retries or escalation. No recursive agents, debate loops or automatic model fan-out.
- Initially bound each request to approximately 4,000 input tokens and 800 output tokens, and a 30-second call timeout. Use provider-supported controls and an application deadline; reject/trim safely or route oversized tasks to review. Include billable reasoning tokens where applicable. Validate fit against the selected provider and task.
- A retry requires both remaining event budget and an error that warrants retry. Do not retry merely to get a preferred commercial answer. A cloud/model switch needs configured approval and consumes the same budget.
- A model timeout does not prove the provider did no work or charged nothing. Record uncertain usage, reserve conservatively and stop further attempts when cost cannot be bounded.
- Configure per-workflow and daily monetary ceilings before paid inference. Reserve worst-case configured usage atomically before a call, settle actual usage afterward, and count failed/retried calls. Missing price/budget information disables paid calls. Document the prototype's single-worker limit and the production concurrency control.
- Cache reusable non-sensitive results only with account/tenant isolation and keys that include normalized input, source/terms version, policy and prompt/model version. Cached wording never bypasses current authorization.
- Track provider/model, prompt version, input/output and other billable usage, attempts, latency, cache status, estimated/actual cost, validation failures, escalations and successful business outcomes. Redact sensitive text.
- Budget exhaustion, provider failure or invalid output preserves work for review. A template fallback is visibly labeled. Deterministic scheduling and calculation can continue where safe. Never label fixture/template output as live AI.
- Cost per successful outcome includes all attempts, integration/hosting costs and human review as separately reported components. Do not claim savings without a measured baseline. Local inference also consumes capacity and operating effort.

Schema validity is only one quality check. Test unsupported facts, invented terms, negation/ambiguity, opt-outs, escalation and hostile instructions. For live inference, use a small held-out set (suggested 12–20 labeled cases) and repeat selected risky cases within the approved evaluation budget. Score both task completion and unsafe/incorrect automatic decisions, with sample counts and actual usage. Finite demo tests do not establish production reliability or an automation percentage.

Independent Codex/Gemini architecture reviews are development-time checks; they are not a two-model runtime loop on every customer action.

## 5. Day 1 package and adaptive daily delivery

Consolidate documentation. Prefer these four core files plus actual review records; use existing repository conventions if equivalent. Do not create a separate document for every concept.

| Artifact | Contents |
|---|---|
| README.md | Business objective, daily minimum commitments and additional outcomes, acceptance card, artifact index, environment/access status, launch/test commands when available |
| requirements.md | Source inventory/locators, M01–M06 and A01–A06 coverage, concrete behaviors, S01–S08 disposition, assumptions, proposed KPI definitions and a separately labeled optional-use-case register |
| architecture.md | Context/component/deployment views; six workflow contracts; conceptual data ownership; integration/authority tables; rule/LLM decisions; cost/reliability/security; acquisition-resilience risks from Section 11; concise ADRs and annotated screen sketches |
| delivery.md | Day plan, selected slice, acceptance cases, capability status, evidence index, demo/runbook, risks and production prerequisites |
| reviews/ | Frozen packet manifest/prompt, genuine original reviews and adjudication with revision identifiers |

For each of the six workflow contracts, include actor, trigger, input, authoritative facts, state transitions, rule/LLM boundary, permitted effects, human exception, output, owner, recovery and acceptance scenario. Include an action sequence and at least one concrete AM cycle and Ops exception. Choose diagrams that explain decisions; avoid decorative diagrams.

Prepare a one-page proposed **acceptance card** at intake: Day 1 scope, minimum prototype outcome, daily minimum commitments and further delivery opportunities, mock/live boundaries, required access, hard checks, evaluator/checkpoint and agreed handover format. Ask the sponsor to confirm or correct material scope assumptions early through normal project communication. An internal score cannot substitute for sponsor acceptance.

**Minimum delivery commitment, not a fixed daily workload:** estimate the day's minimum after inspecting the actual repository, access, available working window and dependencies. Record acceptance evidence and assumptions. Commit to the achievable floor; do not describe access-dependent or unverified outcomes as unconditional guarantees. If an unexpected issue threatens that floor, report the concrete impact promptly, work on recovery and continue independent tasks. Never silently lower the target or fabricate completion.

| Day | Minimum delivery target, refined from intake evidence | Continue further whenever feasible |
|---|---|---|
| Day 1 | Complete M01–M06/A01–A06 HLD and traceability, source/access status, acquisition-resilience assessment, genuine review results or explicitly pending review packet, walkthrough and a verified environment/launch baseline | Start or complete the runnable core path, fixtures, schemas, worker and focused checks as soon as architectural dependencies clear |
| Day 2 | A connected React + Python business path with durable state, deterministic policy, labeled mock/live boundaries, reply/follow-up/handoff behavior and evidence of its principal checks | Resolve more failure cases, exercise approved runtime inference, add source/outcome reporting or another useful AM/Ops increment |
| Day 3 | Reproducible setup/demo, relevant T01–T12 results, material defect resolution, actual capability/mode status, operations instructions and agreed handover | Integrate further coherent, tested increments, improve operating evidence and complete additional assignment workflows |

The calendar is not an execution barrier. Completing Day 1's minimum early permits Day 2/3 work to start the same day. Reaching any day's floor is a checkpoint, not a stop signal. Maintain a ranked queue and pull the next valuable, dependency-ready increment without asking to stop after each routine reversible task. Prioritize complete business outcomes, evidence and recoverability.

Suggested further work: read-only Everflow reporting when authorized access exists; account-health/issue follow-through; fixture-based reconciliation or integration assistance; source/outcome cohorts; a channel-shift scenario; and optional use-case fixtures. Record additional completed outcomes separately from planned work. Extra tasks need not wait for a new calendar day. There is no fixed limit on the number of useful increments or capabilities delivered.

Preserve a known working demo revision while improving it. Additional work, including on Day 3, can proceed on an isolated change and join the handover after relevant verification. Use a stable candidate to protect reproducibility instead of a blanket feature freeze.

Do not wait idle for integration access or a routine technical choice. Continue provisional local work that does not depend on the missing decision and report assumptions. Runtime cost, authorization and quality controls still apply; output ambition does not authorize new spending or external effects. Obtain business decisions only for material changes beyond the assignment or delegated authority.

### Day 1 gate

For each item record PASS, FAIL or CONDITIONAL with an artifact reference:

1. All M01–M06 and A01–A06 have substantive workflow/design coverage.
2. Every material source requirement has a disposition; missing originals are explicit. Optional use cases and their assumptions are separate from assignment requirements.
3. Negotiation, automatic dispatch, recurring AM and Ops have specific authority and failure paths.
4. Integration facts are sourced; tenant-specific unknowns have adapters, fallbacks, owners and verification steps.
5. Deterministic responsibilities, model budget and quality checks are explicit.
6. Critical review findings are resolved or clearly escalated; actual Codex/Gemini review status is recorded.
7. The Day 3 path, test cases, dependencies and out-of-scope items fit the work budget.
8. Acquisition resilience distinguishes dated research from forecasts and employer facts, with a practical design response, owner and validation step. Completing this minimum leaves the next useful increment ready to pull.

Report **design coverage**, **verified integrations**, **independent-review completion** and **sponsor acceptance** separately. Do not turn an internal score into a claim of approval. Missing Gemini access means its review is pending. A core unknown or unresolved critical finding makes the relevant gate conditional/failed, even if unrelated work can continue.

## 6. Minimum prototype outcome and further implementation

**Proposed default:** a local BD conversation workflow, driven by fixtures where credentials are absent. Show useful automatic behavior inside a synthetic policy and human handling of exceptions.

**Use-case packaging:** retain the generic affiliate-network path as the baseline. Insurance buyers/publishers may supply an optional sample context for that same path. Label the example visibly and keep its configuration separate. Insurance consumer acquisition, distribution, bidding or billing is not added to the required prototype by selecting this sample context.

Core completion criteria:

- Import a small synthetic lead set; preserve provenance, normalize/dedupe and produce an explainable qualification result.
- Create a personalized English outreach draft from approved facts. Implement a replaceable inference adapter and a labeled template/fixture mode. If runtime access is supplied, demonstrate and record a genuine model call and its validation/usage.
- Run the eligible workflow through deterministic policy to a durable **mock dispatch**, then display action result and audit. A permitted action can run automatically; an exception enters the approval/handoff queue.
- Inject an inbound reply, use approved offer/terms data for a standard response or bounded proposal, and route ambiguous/out-of-policy terms or clear interest to an owned human case. Configure the standard-reply limit (proposed default two, within the source's two-to-three-round range). Final commercial commitment remains under the approved authority.
- Schedule a three-day follow-up, demonstrate due/not-due with a fake clock, cancel on reply/opt-out/handoff, and retain pending state across a worker restart.
- Show one connected React view with lead/conversation, policy outcome, next action/owner, audit and cost/mode information. Reset/reseed and run the demo without waiting three real days.

The schema and policy control commercial values. For any message containing binding or numeric terms, render from approved structured values or require human review of free text; do not assume JSON schema validation proves the prose is commercially correct. LLM extraction of a number is not an authoritative offer value.

The core path is the minimum implementation outcome. Continue into additional end-to-end increments as dependencies clear, including a read-only Everflow snapshot, account-health/reconciliation, integration assistance or acquisition-resilience checks. Independent improvements can proceed while an unrelated integration is blocked. Label source, freshness and implemented depth; protect completion of the core.

Not minimum commitments: all-six-role production implementation; autonomous contract/signature/payment/routing; live prospect scraping/outreach; production SSO/multi-tenancy; complete integration automation; local model cluster; development factory; new infrastructure purchases. This list is not a blanket ban on achievable additional delivery. Advance useful portions that fit the actual assignment, available evidence and authorized environment; live effects and purchases still require their applicable authority. Required HLD coverage remains.

### Observable acceptance cases

| ID | Check | Evidence required |
|---|---|---|
| T01 | Lead → draft → authorized mock send → reply → response/handoff | UI plus persisted states, fact references, action ID and named owner |
| T02 | Ten duplicate events and competing worker claims | One logical action and one mock transport acceptance |
| T03 | Recipient/content/terms edits, expired policy, out-of-policy request | Prior authorization invalidated; no unauthorized effect |
| T04 | Opt-out, human request and ambiguous/negated commercial language | Appropriate suppression/review; no guessed consent or authority |
| T05 | Just before/at due time, repeated scheduler ticks, reply and worker race | One due follow-up; cancelled actions stay cancelled; documented external-ingestion limitation |
| T06 | Known transient failure versus timeout after possible acceptance | Finite retries only when appropriate; unknown outcome reconciled/quarantined without blind resend |
| T07 | Worker/process restart with pending and accepted actions | Durable recovery and no repeated logical mock send |
| T08 | Malformed model JSON, invented fact/term and hostile source text | Rejection/review or safe fallback; no arbitrary tool/credential access |
| T09 | Model unavailable, attempt cap, token/deadline limit and exhausted budget | Limits enforced; visible safe degraded mode; no automatic paid escalation |
| T10 | Usage/cost tracking and changed source/policy versus cached output | Attempt-inclusive accounting and cache invalidation/current authorization check |
| T11 | Mock configuration and local operating boundary | No unintended external effects or frontend/log secrets; unimplemented production access controls explicitly listed |
| T12 | Fresh setup, backend checks, frontend build and exercised UI | Actual commands/results, environment/revision and reproducible demo |

Implement meaningful tests for the selected behavior. A documented expected result is not a test run. If a test exposes a defect, fix it and rerun affected checks. Record any remaining failed or unexecuted case. Production role/tenant isolation must be designed and becomes a tested release prerequisite before shared deployment; do not claim that a local-only mock demo verifies it.

If an insurance example is included, also exercise the core path with generic affiliate fixtures and record which settings differ. This checks reuse without expanding the prototype into another production workflow.

Use two status dimensions for each capability: **implementation** = tested / implemented-unverified / designed-only / blocked / deferred; **execution mode** = deterministic / live model / template-fixture / mock adapter / live external adapter. For example, a tested scheduling engine with mock dispatch is tested locally and mocked at the provider boundary. Keep both facts visible.

## 7. Independent review and stage reporting

Freeze the same requirements, architecture, source dispositions, acceptance cases and revision manifest for Codex and Gemini. A fresh Codex context is a separate review context, not a different model family. Do not pass the other review or the author's verdict to either reviewer first. Use approved access only; do not install agents or transfer company files to an unapproved service.

Use this prompt with both:

~~~text
Independently review the attached frozen architecture and original sources. Check M01–M06 and A01–A06 coverage, including negotiation, dispatch, recurring AM, integration assistance, reconciliation and Traffic Guard. Trace one BD action, one AM cycle and one Ops failure to an owned outcome.

Check that the three assignment documents and explicit employer instructions define mandatory scope. Insurance must remain a labeled optional example, with assumptions and configuration separated from core requirements. Flag any inferred employer business fact, insurance-only core dependency, or example that displaces required scope.

Evaluate the daily minimums as floors, identify additional achievable work and flag artificial calendar barriers. Review acquisition-channel concentration, AI-mediated discovery, attribution gaps, provider dependence and platform bypass. Separate verified evidence, industry-specific observations, hypotheses and proposed design responses. Test whether the system adapts its inputs and measures accepted business outcomes without claiming that architecture guarantees business survival.

Challenge source interpretations, API/tenant assumptions, rule-versus-model boundaries, financial/terms authority, inbox/outbox concurrency, approval edits, duplicate sends, reply/follow-up races, unknown external-write outcomes, stale data, model outages, prompt injection, token/cost limits and three-day feasibility.

Return ranked findings: ID, severity, exact artifact/source location, concrete failure scenario, evidence or explicit uncertainty, minimal remedy, tradeoff and falsifiable verification. Identify important strengths and a credible simpler alternative. Distinguish a defect from a preference. Do not infer correctness from model agreement. Do not claim a test or vendor action was executed without evidence.
~~~

Preserve genuine originals with provider/model if known, date and input revision. Adjudicate accept/reject/defer/unresolved with evidence and resulting changes. Run focused follow-up reviews when material changes or unresolved findings justify them; once the gate is evidenced, advance useful delivery. Avoid consensus-until-perfect loops and repeated checks without a new reason. If Gemini is unavailable, export the packet, mark the required review pending and continue independent work; another Codex answer is not a Gemini review.

At meaningful milestones and each day's end, report the minimum commitment, actual completed outcomes, additional verified increments, revision/artifact links, checks actually run, capability/mode status, blocker/owner/impact and next task. Explain any forecast change. Keep the record sufficient to resume after a chat or usage interruption; count usable outcomes rather than generated lines or unsupported feature claims.

Day 1 walkthrough: business mandate and six-role coverage; end-to-end flow; rules/LLM allocation; authority/data/recovery; acquisition-resilience evidence and decisions; review findings; minimum delivered and additional progress.

Day 3 walkthrough: run the business path and additional verified capabilities, show an exception and recovery, show mode/cost/evidence and the response to changing acquisition channels, and state remaining production prerequisites. Deliver agreed artifacts in the approved project location with setup, reset, run, test and stop instructions. Preserve provenance and company records; transfer source and other materials according to the agreed engagement scope.

## 8. Source assessment register to verify against originals

The imported source locators below come from the preceding brief and kickoff context. The three originals were not re-audited as part of this instruction-file revision. Confirm exact quotations/page/section locations during intake; adjust or retire findings when evidence warrants it. Vendor documentation checks below were performed on 2026-11-02; tenant execution was not.

| ID | Imported source issue | Engineering disposition |
|---|---|---|
| S01 | Business Modules 1–2: Skype and Telegram contact/conversation assumptions | Consumer Skype retired on 2025-05-05. Standard Telegram bots require user initiation/group addition; separately scoped Business features do not establish arbitrary cold outreach. Validate the chosen channel's actual permissions; do not assume Teams is a drop-in API replacement. |
| S02 | Factory PDF pp. 1, 3–5: zero-cost/unlimited local inference, savings and host/population claims | Capacity, quality and total cost require workload measurement on actual hardware. No launch requirement for 5–10 hosts or an unmeasured savings guarantee. |
| S03 | Factory PDF pp. 1–3: review until models find no flaws; defect-elimination percentage | Use independent challenge plus tests, severity and bounded review. No documented basis here for a numerical defect-elimination guarantee. |
| S04 | Factory PDF pp. 3, 5: Jev/Choice/Score/Noul and universal 0.90 routing | Official docs confirm the primitives. Noul answers a yes/no proposition; Choice/Score confidence summarizes their output distributions. Neither automatically certifies arbitrary task completion. Validate calibration, target labels, access, data boundary and cost for the actual use case. |
| S05 | Factory PDF pp. 3–4: perfect database recovery/private-interface access from HAR/API observations | Authorized observations inform interface hypotheses. They do not reveal a unique internal schema or create supported/unlimited API rights. Design and validate the service's own data model. |
| S06 | Factory PDF pp. 2–5: configuration-only reuse and instant generated production changes | Reuse suitable components after fit/license checks. Preserve necessary code, migrations, tests, isolated changes and rollback. Treat lead-time claims as measurement goals. |
| S07 | Business objective/Module 3: automation percentage, recurring AM, real-time and expenditure metrics | Define eligible tasks, successful outcome, correction/escalation, labor saved, cadence, freshness and currency/denominators. No target is validated by a task-count claim alone. |
| S08 | Business Modules 2–4 plus sponsor negotiation direction: standard replies, final handoff, proposals, collection wording and spike diagnosis | Reconcile useful bounded automation with approved terms and human final authority. Keep missing terms explicit, reminders as drafts absent dispatch authority, and diagnostic hypotheses distinct from proven cause. |

Put each item's source verification, design impact, resolution, owner and status inside requirements.md. Also capture document-3 proposals about KPIs, Coda/Dify/AnythingLLM/Ringba/Voluum/BigQuery and timing. Named tools are candidates until installation/access is confirmed.

## 9. Primary technical references

Checked 2026-11-02. These support vendor facts and design reasoning, not a guarantee of this project's feasibility or approval.

- [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents) — start with the simplest suitable mechanism; distinguish predefined workflows from dynamic model control. Its historical framework list is not a current tool-selection requirement.
- [Anthropic: Multi-agent research system](https://www.anthropic.com/research/multi-agent-research-system) — reports about 15 times chat token use for its multi-agent research workload, alongside gains on suitable research tasks. This is a workload-specific observation, not a universal multiplier or a comparison against every single-agent design.
- [Everflow API documentation](https://developers.everflow.io/) and [authentication](https://developers.everflow.io/user-guide/authentication), [webhooks overview](https://developers.everflow.io/webhooks/overview) — confirm applicable API family and tenant access before implementing.
- [Microsoft Skype retirement notice](https://support.microsoft.com/en-us/skype/skype-is-retiring-in-may-2025-what-you-need-to-know).
- [Telegram bots introduction](https://core.telegram.org/bots) and [tutorial](https://core.telegram.org/bots/tutorial).
- TypeSafe [introduction](https://docs.typesafe.ai/introduction), [Noul](https://docs.typesafe.ai/primitives/noul), [confidence](https://docs.typesafe.ai/confidence).

## 10. Start instruction

~~~text
Read this delivery brief, all available original requirements and repository instructions. Establish source/access status without inventing missing content. Propose the acceptance card and produce the compact, complete Day 1 HLD/review package with M01–M06 and A01–A06 traceability.

Follow the three assignment documents and explicit employer instructions as the business scope. Build the reusable affiliate-network foundation. Insurance lead generation/distribution may appear only as one labeled optional illustrative use case, using synthetic data and assumed rules. Do not make it the project target, infer employer operations, or add insurance-specific mandatory features. Keep a generic baseline and separate example configuration.

Use deterministic rules and durable workflows for authority, arithmetic, scheduling and execution. Add bounded model calls for demonstrated language needs. Recommend the minimum local BD slice and document its mock/live boundaries. Map the development-factory vision architecturally without making a complete factory a minimum implementation commitment.

Set an evidence-based minimum delivery commitment for each day and a ranked queue of further work. These are floors, not daily task caps. Continue to the next useful reversible increment as dependencies clear, bring later work forward and preserve a verified demo revision while improving it.

Integrate Section 11's research into a concise acquisition-resilience assessment and architecture decisions. Separate facts, limitations, hypotheses and implementation status. Verify material vendor facts from official sources, keep research actionable and expand it when a material uncertainty warrants it. Continue independent reversible work when access or routine decisions are missing. Present actual minimum and additional outcomes. Enable external effects only within an explicitly approved scope.
~~~

## 11. Acquisition resilience under AI-mediated discovery

**Research checked:** 2026-11-04. **Status:** external evidence and proposed architectural responses, not an assertion about this employer's acquisition mix. This applies to the affiliate foundation generally; insurance remains an optional example.

### Evidence and its limits

| Evidence | What it establishes and what it does not |
|---|---|
| [Alphabet Q3 2026 release, 2026-10-28](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000080/googexhibit991q32026.htm) | Google advertising revenue was $82.012B versus $74.182B a year earlier, approximately +10.6%; Search & other grew 12%. A claim that Google's advertising revenue has broadly collapsed is not supported by this quarter. These totals do not measure an individual publisher's traffic. |
| [Alphabet Q3 2026 call](https://abc.xyz/investor/events/event-details/2026/2026-Q3-Earnings-Call-2026-Ujou16CTw9/default.aspx) | Management said lower AI Mode monetization contributed to slower Search growth, alongside other factors. Slower growth is different from an absolute revenue decline; this is management commentary, not a measurement of our funnel. |
| [Pew browsing study, 2025-07-22](https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/) | In a March 2025 U.S. panel of 900 adults, traditional-result clicks occurred on 8% of visits with AI summaries versus 15% without. Observational query differences and the collection period limit inference; this is not a forecast for all industries or this employer. |
| [Wang et al., 2026-08-18 preprint](https://arxiv.org/abs/2608.18352) | A preregistered field experiment with 1,100 participants reports higher publisher click-through when AI search features are removed. Treat it as a preprint and a bounded experiment, not a universal lead-volume or pricing estimate. |
| [Google Ads guidance](https://support.google.com/google-ads/answer/18826097?hl=en) and [2026-05-20 product announcement](https://blog.google/products/ads-commerce/google-marketing-live-search-ads/) | Google documents ads in AI search experiences and announced in-ad Business Agent for Leads. Demand capture can move into the platform. Availability, permissions and integration/export interfaces require verification; standard reporting aggregates AI-placement metrics, so a precise AI-only breakdown cannot be assumed. |
| [Adobe retail analysis, 2026-10-29](https://business.adobe.com/blog/ai-traffic-higher-revenue-per-visit-retail-holiday) | Adobe reports September 2026 AI-referred U.S. retail visits had a 90% higher conversion rate than non-AI visits, a relative difference. This is evidence that referral quality may differ, not proof that insurance or affiliate leads will see the same uplift or that AI caused it. |

### Assessment and architectural response

**Inference:** AI can change discovery, reduce some website referrals and let platforms connect buyers and sellers more directly. It can also create qualified referrals and new interfaces. An automation foundation can adapt technically, but business viability still depends on demand, permissions, buyer relationships, useful data/service and contribution economics. If a business depends only on reselling commodity traffic, better orchestration alone may not preserve its margin.

Both B2B prospect acquisition and any downstream consumer enquiry need this assessment; keep those entities distinct. Obtain the company's real channel mix when authorized rather than assuming SEO, paid search, calls or insurance.

| Risk hypothesis | Observe | Proposed response and owner |
|---|---|---|
| Traditional referral volume or quality declines | Source concentration, qualified/accepted outcomes and cohort freshness | Replaceable source adapters feeding a common intake contract; BD/Ops validates another permitted source before changing allocation |
| Discovery moves inside an assistant/platform | Verified interface availability, export terms, usable enquiry volume | Document an adapter extension point and a versioned, permissioned business-data contract; integration owner verifies access before implementation |
| Attribution becomes incomplete | Unknown-source share, missing IDs and reconciliation discrepancies | Preserve supplied source/campaign evidence, observation time and attribution method; explicitly retain unknown/aggregate categories instead of inventing AI attribution |
| Traffic continues but economics weaken or buyers bypass intermediaries | Billable outcomes, revenue, rejections/refunds, partner/media/inference costs and account retention | Compare cohort contribution and identify the service's distinct value; business owner decides experiments and commercial changes |
| Machine-originated requests contain stale facts or exceed authority | Source/terms age, identity evidence, policy violations | Reuse deterministic validation, current approved facts, authorization and handoff; an asserted assistant identity grants no extra access |

Normalize permitted inputs from forms, email, partner feeds or future authorized assistant channels into the same workflow. Capture source provenance and outcomes without tying the core to a particular search engine, cookie or website visit. Treat unknown costs/attribution as unavailable, not zero or a guessed channel.

Measure the funnel from source to qualification, buyer acceptance and the actual contract's billable event. Revenue recognition, partner payout, advertising spend, inference/serving costs and refunds need explicit, non-overlapping definitions. The billable event is not automatically an insurance sale. Source-level volume, acceptance rate, cost per accepted/billable outcome and cohort contribution are more useful than clicks alone; label observational attribution and incomplete cost data.

**Day 1 minimum:** include this evidence/limitations, the material risk register, source-adapter/data-ownership decision and an owner/verification step in the existing HLD. These are architect-proposed risk controls, not retroactively attributed source requirements. Do not create another large platform or delay the required architecture for exhaustive market research.

**Additional achievable implementation:** replay two synthetic sources through the same intake/policy/audit path; add a source/outcome cohort view and a scenario reducing traditional-source volume or increasing acquisition cost. Mark all shock inputs as hypothetical stress assumptions, not forecasts or estimates copied from the studies. Reconcile statuses/costs and show that changing source does not bypass policy or duplicate effects. This can be completed beyond the daily minimum as progress allows.

Future live adapters, AI-visibility work and commercial tests require verified contracts and the appropriate business authority. Machine-readable approved information and good service quality are design options, not guarantees of AI recommendations or demand. Review the risk when observed funnel economics or relevant vendor contracts materially change.

