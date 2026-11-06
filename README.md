# Everflow affiliate network automation

Operate one synthetic Offer from advertiser intake and channel placement through configuration, release, delivery, buyer feedback, BD proposal review, AM resolution and an owned Finance decision. The React and FastAPI demo shows which version was released, what the buyer reported and which role owns the next decision.

## Run the Offer demo

From the repository root, with Python 3.10+ and a Node.js version supported by the frontend dependencies:

```sh
EVERFLOW_UV_CACHE="${TMPDIR:-/tmp}/everflow-uv-cache" \
EVERFLOW_NPM_CACHE="${TMPDIR:-/tmp}/everflow-npm-cache" \
./scripts/setup.sh
./scripts/run_v2.sh
```

Open [Offer operations](http://127.0.0.1:8020). The server uses one worker, a local SQLite database under `.run/` and synthetic records. All platform effects are simulated.

1. In **Launch readiness**, save a mapping change and run the mock platform test. Release the exact passing configuration with an owner note. A failed test blocks release, and editing terms or mappings requires fresh evidence.
2. In **Quality & feedback**, run a mixed batch. The demo delivers two eligible synthetic leads and rejects two with missing or failed qualification evidence. Record the buyer outcomes.
3. In **BD & AM follow-through**, prepare and review a proposal against the current Offer evidence. Requested terms stay separate from the approved clauses. Open and resolve an AM action for the channel, with a recorded next review.
4. Record the Finance preview against the feedback reviewed. The normal fixture produces a provisional receivable and channel cost. A disputed return stays with Finance and holds both amounts pending a rule decision.

The [demo guide](docs/offer-demo.md) covers the walkthrough, disposable databases and the backend, browser, restart and build checks. The [architecture overview](architecture.md) maps responsibilities, evidence and release authority across the Offer cycle.

## Business decisions

The employer needs to confirm the start of the 72-hour return window, whether Tier 1 requires volume **and** quality or either condition, and whether an above-cap upstream return can trigger a supplier deduction. Fixture pricing, qualification, capacity and approvals are synthetic. Trial scope, timing and sponsor acceptance are open.

## Historical Day 1 checkpoint

The [Day 1 foundation at `033795f`](https://github.com/ShenghangWang/Everflow-Affiliate-Network-Automation/tree/033795f9be852c46ed34f87f3504d21dfa759bee) contains the original BD, onboarding, recurring AM and reconciliation walkthrough, architecture, reviews and evidence. Its verification results apply to that revision. Open the earlier UI at [`/?baseline=1`](http://127.0.0.1:8020/?baseline=1).
