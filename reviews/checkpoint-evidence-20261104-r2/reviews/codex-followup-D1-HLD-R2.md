# Original focused Codex follow-up — D1-HLD-R2

Reviewer: the same independent Codex reviewer that produced `codex-original-D1-HLD-R1.md`, in its review context. Exact underlying model identifier is unavailable. Date: **2026-11-04**. Input: **D1-HLD-R2**, frozen at **2026-11-04T03:17:07.234536+00:00**.

## Scope and integrity

This is a focused check of the responses to **CR-01, CR-02 and CR-03**, including consequences in the adjacent workflow, authority, reporting and status text. It is not a repeated full architecture audit or an implementation review. I read only the frozen R2 packet and retained my own prior findings; no live working tree, other review, adjudication, application source, or external service was consulted. No implementation test, vendor call, installation or transmission was performed.

I checked all **18** manifest entries against their byte lengths and SHA-256 hashes: **18 matched, zero mismatches**. Relevant input hashes:

| Frozen file | SHA-256 |
|---|---|
| `manifest.json` | `14e0f0d2a54b78e42a0fd37030cd38e461f5a2eca179e241c5508f1545582e65` |
| `architecture.md` | `2578c729807eb3461462a737a323d21fd80cee99b5bd434222e47867fe756658` |
| `requirements.md` | `506cf1c1be0a77a348c45219a944e8ced9cfcbf98c5080737de3298bf56e8297` |
| `README.md` | `11421430a86d4e71d94323b0d758a7a326b31f90fdfcfb94abcbb5a29d7cbcdc` |
| `delivery.md` | `9d52114702a0ff276eda90fef096e64d24db07b9051841cc6b34c7bc877e40dc` |
| `review-prompt.txt` | `0141d5b727be962a6b4978c186a13a49555848868bfac7b340a2f06fe5e4c7a0` |

The original source extracts, retained originals, requirements and common prompt retain the hashes reviewed in R1. The focused changes do not redefine mandatory scope or introduce an insurance dependency.

## Finding dispositions

All three original findings are **resolved at the architecture-design level**. No new high- or medium-severity defect was identified in the affected contracts. The corresponding implementation and provider release checks remain **unverified**. This distinction is essential: adding the correct invariant to an HLD does not demonstrate its execution.

### CR-01 — Original severity High — Resolved in design

**Exact R2 locations:** `architecture.md:137`, read with `:74–80`, `:94–100`, `:132–135` and `:164–168`.

The new shared-target control record explicitly includes tenant/target, control epoch, observed-state version, incident hold and winning decision. Dispatch is serialized per target. Authorization binds the epoch and preconditions and is checked at claim and immediately before execution. Guard mitigation advances the epoch, places the hold, and supersedes incompatible AM intents and recovered leases. Clearing a hold requires an authorized Ops recovery owner, fresh readback and a new decision/epoch; a superseded intent cannot be revived. Manual/provider changes also invalidate stale commands. Late receipts remain attached to their original decisions and cause reconciliation instead of overwriting the newer decision.

That directly addresses the original failure: a previously authorized AM resume cannot simply become eligible after a newer Guard pause and undo it under the same unchanged authority. The paragraph also correctly limits the claim to designed-only future campaign controls; it adds no authority to the current mock BD path.

**Falsifiable release checks, not executed here:** Queue an authorized AM resume, then a newer Guard pause. After the pause is verified, tick/restart the old intent and recover its lease: it must remain superseded and no resume request may be sent. Race actors for the same canonical target, including account/campaign/route aliases that control the same provider resource. Inject a manual provider change and verify the stale epoch blocks execution. Reject unauthorized or stale-readback hold clearance, then allow a newly authorized recovery exactly once. Delay a provider receipt/effect from the older decision: it must not replace the winning decision or be reported as present success; observation/reconciliation must establish the actual provider state and retain an owned incident if it differs.

**Residual limit / tradeoff:** A local epoch cannot fence a provider that has already accepted a command. The existing unknown-outcome/quarantine and readback contracts remain necessary. A live adapter must establish acceptance, completion, ordering and recovery semantics; do not interpret the new local invariant as an external exactly-once or instantaneous-stop guarantee. Conservative supersession adds recovery work and may delay a legitimate resume. That is a deliberate tradeoff, not a remaining design defect in the stated boundary.

### CR-02 — Original severity Medium — Resolved in design

**Exact R2 locations:** `architecture.md:56–60`, read with `:66–70` and `:76–80`.

The revised A02 transition separates account creation pending activation, technical readiness, activation approval, active account, and first-outcome verification. Its acceptance scenario explicitly says duplicate/out-of-order signatures create one **pending** account, rather than an active one. The shared readiness predicate requires signed approved terms/checklist, a matching current integration release/test version or an owner-approved not-applicable gate, and activation-owner approval. Missing mapping/failed tests block activation. A material regression reopens readiness and an owned issue. First accepted outcome is a later AM milestone.

The signature-to-active ambiguity identified in R1 is removed. A03's technical “activated” stage must satisfy the shared predicate before the business account becomes active; it does not supersede A02's activation-owner authority. A04's “Activation remains open until the first agreed outcome is checked” at line 76 is consistent when it refers to the activation follow-through case, while operational account status and the later first-outcome milestone remain separate as expressly defined at lines 56 and 60. Implement them as separate state fields rather than collapsing them into one boolean.

**Falsifiable release checks, not executed here:** Replay duplicate/out-of-order signature events with missing mapping or failed tests: one account may exist, but it must remain pending with a blocker/owner. A passing test for an old mapping version or an unauthorized not-applicable flag must not satisfy readiness. Complete the matching gates and owner approval: activate once and create one AM follow-through task. Do not mark first outcome verified without its own evidence. Change the mapping/test version or inject a material regression: reopen readiness/issue with an accountable owner, and invalidate any pending activation based on the old version.

**Tradeoff:** More explicit states and version checks add coordination. They preserve the distinction between a signed commercial record, technical readiness, operational activation and verified business outcome. Reopening a readiness issue does not itself grant an unauthorized emergency pause; mitigation still follows the Ops authority contract.

### CR-03 — Original severity Medium — Resolved in design

**Exact R2 locations:** `architecture.md:122`, read with `:84–90`, `:94–100`, `:112`, `:120` and `:176`.

The revision now expressly rejects final-page completion as sufficient evidence. Each fetch attempt records a fixed window/as-of point, ordering/cursor, available snapshot token, page boundaries, unique IDs, response versions and authoritative counts/totals. Tenant verification must establish mutation and snapshot behavior. Without an appropriate contract, bounded settling/re-fetch/reconciliation yields an honestly labeled observed-stable or uncertain result; it does not become a proven immutable snapshot. Unproven data cannot drive automatic mitigation or a final automatic financial conclusion. An owned data-health case and alert-only observations remain available. Corrections create a new revision, invalidate/reopen dependent results and reconcile decisions without double-counting.

This closes the original completeness gap and is consistent with the older watermark paragraph at line 120: committing all pages remains necessary for advancing the ingestion watermark, while line 122 separately governs whether the resulting report is fit for consequential use. Advancing ingestion progress must not implicitly upgrade `observed-stable` to `complete`.

**Falsifiable release checks, not executed here:** A fake paginated source inserts, removes, reorders and corrects records between pages, including changes with unchanged IDs/counts but altered values. The assembled result must match the authoritative snapshot/control contract or remain uncertain; reaching the last page must not trigger automatic mitigation or a final variance conclusion. Exercise corrections outside the initial overlap and verify dependent comparisons/incidents reopen with versions and no duplicate amounts/actions. Confirm that stale/unproven inputs retain an owned case and only labeled alert observations. The eventual selected tenant contract must establish its actual sorting, snapshot, row-value, total and lateness semantics.

**Tradeoff:** Some providers may never support the needed proof, keeping automation conservative and increasing calls or latency. Alert-only handling is a useful available outcome; the HLD no longer silently treats freshness as completeness.

## Consequence and evidence checks

The revised paragraphs preserve accountable authority, unknown-outcome quarantine and no-live-effects boundaries. They do not add a new provider, model loop, deployment dependency or insurance requirement. Resolving these design findings does not require blocking unrelated generic BD work or waiting for another calendar day.

R2's delivery narrative now reports local backend/browser results (`delivery.md:50–61`, `:113–117`). Those underlying test artifacts and application sources are outside this frozen review manifest, and I did not inspect or execute them. I therefore neither verify nor overturn those implementation claims here. Importantly, the packet continues to distinguish its local BD evidence from the designed-only target controls and broader workflows (`architecture.md:137`, `:288`; `delivery.md:37–40`). Fresh setup, real provider semantics, genuine runtime model evaluation and other stated prerequisites are not supplied by this focused review.

The common R2 packet being ready for Gemini is an export status, not a completed Gemini review. No approved Gemini route, Gemini result or sponsor acceptance was available to this reviewer. No inference of correctness is made from agreement or the author's acceptance of the prior findings.

**Recommended disposition:** close CR-01–CR-03 as **design-resolved, implementation/release verification pending**; retain their falsifiable checks in the release ledger for the affected capabilities. No additional repeat review loop is warranted solely because these paragraphs were amended. Continue useful tested delivery, and request another focused check only for a material change or new contrary evidence. Preserve the R1 original and this follow-up unchanged.
