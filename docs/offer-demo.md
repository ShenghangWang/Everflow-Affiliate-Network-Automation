# Run and verify the Offer demo

Run commands from the repository root. Setup requires Python 3.10+, npm and a Node.js version supported by the frontend dependencies. Use `EVERFLOW_PYTHON` to select a compatible interpreter if needed.

```sh
EVERFLOW_UV_CACHE="${TMPDIR:-/tmp}/everflow-uv-cache" \
EVERFLOW_NPM_CACHE="${TMPDIR:-/tmp}/everflow-npm-cache" \
./scripts/setup.sh
./scripts/run_v2.sh
```

Open [Offer operations](http://127.0.0.1:8020). The server uses `.venv/bin/python` by default and persists synthetic state in `.run/v2-offer-cycle.sqlite3`. Stop it with Ctrl+C. Set `EVERFLOW_DEMO_DB` to a fresh path under `.run/` to begin a new walkthrough. Set `EVERFLOW_PORT` for a separate server. The earlier demo is available on the same server at [`/?baseline=1`](http://127.0.0.1:8020/?baseline=1).

## One Offer walkthrough

1. **Offer cycle.** Inspect advertiser `ADV-SYN-1`, Offer `OFR-SYN-1` and channel `CH-SYN-1`. The fixture uses USD 40 revenue and USD 25 base payout per qualified lead, a 20-lead daily Offer cap and 30-lead channel capacity.
2. **Launch readiness.** Change the mapping version to `SYN-MAP-WALKTHROUGH` and save the configuration. Run **Failed verification** and try to release with an owner note. Release is blocked. Run **Healthy**, enter a note and record release. The retained release links to the exact configuration and test. **Replay last request** preserves one release.
3. **Quality & feedback.** Run the **Mixed quality** batch. Two synthetic leads are delivered and two are rejected for a missing certificate or failed phone check. The buyer outcomes initially show unknown values. Replay the batch request and confirm it consumes capacity once.
4. Select **Buyer outcomes** and record feedback. The exact batch shows two connections, one appointment and one sale. The day's remaining channel capacity is 28. Inspect the evidence behind the BD, AM and AdOps recommendations.
5. Enter a Finance review note and record the reconciliation preview. The fixture shows a provisional USD 80 advertiser receivable and USD 50 channel cost. Then record **Return dispute** and review that feedback version. Finance owns the hold, the previous conclusion becomes historical and both provisional amounts are unknown pending a rule decision.
6. Return to **Launch readiness** and change a material term or mapping. The previous test and release remain in history. A fresh passing test and owner release are required for the changed configuration.

Every delivery, buyer response and platform check in this walkthrough is simulated. Prices, qualification evidence, roles and capacity belong to the synthetic fixture. The 72-hour return window start, Tier 1 AND/OR condition and above-cap supplier deduction policy are open employer decisions.

## Verify a checkout

```sh
git rev-parse HEAD
.venv/bin/python scripts/check_v2.py
.venv/bin/python scripts/check_v2_restart.py
npm --prefix frontend run build
```

The restart check uses a temporary database and separate loopback server processes. For browser verification, start a server on a **disposable database** in a separate terminal:

```sh
EVERFLOW_DEMO_DB=.run/offer-browser-check.sqlite3 EVERFLOW_PORT=8021 ./scripts/run_v2.sh
```

Install Playwright and compatible Chromium if needed. The following commands keep the test dependency under the ignored runtime directory:

```sh
npm --prefix .run/browser install --no-audit --no-fund playwright
.run/browser/node_modules/.bin/playwright install chromium
PLAYWRIGHT_PACKAGE="$PWD/.run/browser/node_modules/playwright" \
DEMO_URL=http://127.0.0.1:8021 node scripts/check_v2_ui.mjs
```

A Node-resolvable Playwright installation can be used directly. `CHROMIUM_EXECUTABLE` selects an existing compatible Chromium executable. The browser verifier resets the configured server's demo database. Use the disposable server to preserve walkthrough records.

The verifiers write reports under the ignored `.run/v2-evidence/` directory. Record the checked Git revision with results. Historical Day 1 results apply to their original revision.
