import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const demoUrl = new URL(process.env.DEMO_URL || 'http://127.0.0.1:8020');
if (demoUrl.protocol !== 'http:' || !['127.0.0.1', '[::1]'].includes(demoUrl.hostname)
    || demoUrl.username || demoUrl.password || demoUrl.pathname !== '/' || demoUrl.search || demoUrl.hash) {
  throw new Error('DEMO_URL must be an HTTP loopback origin such as http://127.0.0.1:8020');
}
const base = demoUrl.origin;
const out = path.join(root, '.run', 'v2-evidence', 'followthrough-ui');
fs.mkdirSync(out, {recursive: true});
const git = (...args) => execFileSync('git', args, {cwd: root, encoding: 'utf8'}).trim();
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const sourceFiles = git('ls-files', '-z', 'frontend/src', 'frontend/package-lock.json',
  'backend/offer_v2.py', 'backend/offer_followthrough.py', 'backend/app.py',
  'backend/fixtures/offer_v2.json', 'scripts/check_v2_followthrough_ui.mjs').split('\0').filter(Boolean);
const results = {
  started_at_utc: new Date().toISOString(),
  git_revision: git('rev-parse', 'HEAD'),
  clean_checkout: !git('status', '--porcelain'),
  source_sha256: Object.fromEntries(sourceFiles.map(file => [file, sha256(fs.readFileSync(path.join(root, file)))])),
  assets_sha256: {},
  base,
  mode: 'Synthetic Offer, simulated effects',
  checks: [],
  page_errors: [],
  console_errors: [],
};

function check(name, pass) {
  results.checks.push({name, pass: Boolean(pass)});
  if (!pass) throw new Error(name);
}

let browser;
try {
  const require = createRequire(import.meta.url);
  const {chromium} = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright');
  browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath: process.env.CHROMIUM_EXECUTABLE} : {}),
  });
  results.browser = browser.version();
  const page = await browser.newPage({viewport: {width: 1440, height: 1050}, deviceScaleFactor: 1});
  await page.route('**/*', route => new URL(route.request().url()).origin === base
    ? route.continue() : route.abort());
  page.on('pageerror', error => results.page_errors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'error' && !message.text().includes('409')) results.console_errors.push(message.text());
  });
  const get = endpoint => page.request.get(base + endpoint, {maxRedirects: 0});
  const post = (endpoint, data) => page.request.post(base + endpoint, {data, maxRedirects: 0});
  const clickTab = name => page.getByRole('button', {name, exact: true}).click();
  const screenshot = filename => page.screenshot({path: path.join(out, filename), fullPage: true});
  const command = async (name, expectedStatus = 200) => {
    const [response] = await Promise.all([
      page.waitForResponse(response => response.url().startsWith(base + '/api/')
        && response.request().method() === 'POST'),
      page.getByRole('button', {name, exact: true}).click(),
    ]);
    if (response.status() !== expectedStatus) {
      throw new Error(name + ' returned HTTP ' + response.status() + ' ' + await response.text());
    }
    await page.getByRole(expectedStatus === 200 ? 'status' : 'alert').waitFor();
    return {state: await response.json(), request: response.request().postDataJSON()};
  };

  const dist = path.join(root, 'frontend', 'dist');
  const builtFiles = ['index.html', ...fs.readdirSync(path.join(dist, 'assets'))
    .sort().map(file => 'assets/' + file)];
  for (const file of builtFiles) {
    const expectedHash = sha256(fs.readFileSync(path.join(dist, file)));
    const response = await get(file === 'index.html' ? '/' : '/' + file);
    if (!response.ok() || sha256(await response.body()) !== expectedHash) {
      throw new Error('The demo server must serve the current checkout build: ' + file);
    }
    results.assets_sha256[file] = expectedHash;
  }
  const initial = await (await get('/api/v2/offers')).json();
  if (initial.effects.external_effects !== false || initial.effects.live_platform_calls !== 0) {
    throw new Error('The verifier requires the simulated Offer server');
  }
  if (!(await post('/api/reset')).ok()) throw new Error('Synthetic reset failed');
  await page.goto(base);
  await page.getByRole('heading', {name: 'Operate one Offer', exact: true}).waitFor();

  await clickTab('Launch readiness');
  await page.getByLabel('Platform mapping version', {exact: true}).fill('SYN-MAP-FOLLOWTHROUGH');
  const {state: configured} = await command('Save synthetic configuration');
  const {state: tested} = await command('Run mock platform test');
  await page.getByLabel('Launch owner verification note').fill('Reviewed the exact synthetic configuration and test.');
  const {state: released} = await command('Record owner release of this version');
  check('Mock test and owner release refer to the exact configuration version',
    configured.offer.version === 2 && released.offer.release_current
      && released.releases.at(-1).config_sha === configured.offer.config_sha
      && released.releases.at(-1).test_id === tested.offer.latest_test_id);
  const offer = '/api/v2/offers/' + released.offer.id;
  const followthrough = offer + '/followthrough';

  await clickTab('Quality & feedback');
  const {state: delivered} = await command('Run synthetic lead batch');
  const batch = delivered.batches.at(-1);
  check('The current release delivers the mixed batch and records rejected intake',
    batch.release_id === released.offer.active_release_id
      && batch.payload.qualified_delivered === 2 && batch.payload.rejected === 2);
  await clickTab('BD & AM follow-through');
  await page.getByText('Delivery evidence only', {exact: true}).waitFor();
  const requestedTerms = 'Request USD 99.00 and a 99-slot increase for discussion.';
  await page.getByLabel('Requested commercial terms', {exact: true}).fill(requestedTerms);
  check('Missing buyer feedback blocks BD while AM can investigate a delivery issue',
    await page.getByRole('button', {name: 'Prepare synthetic proposal', exact: true}).isDisabled()
      && await page.getByRole('button', {name: 'Open channel action', exact: true}).isEnabled());
  const {state: opened} = await command('Open channel action');
  const action = opened.am_actions.at(-1);
  check('AM action has an owner, next step and exact advertiser, Offer and channel evidence',
    action.status === 'open' && Boolean(action.owner && action.next_action)
      && action.evidence_sha256 === opened.evidence.sha256
      && opened.evidence.scope.advertiser_id === released.advertiser.id
      && opened.evidence.scope.offer_id === released.offer.id
      && opened.evidence.scope.channel_id === released.channel.id
      && opened.evidence.batch_id === batch.id);

  await clickTab('Quality & feedback');
  const {state: withFeedback} = await command('Record synthetic buyer feedback');
  const feedback = withFeedback.feedback.at(-1);
  await clickTab('BD & AM follow-through');
  await page.getByText('Buyer evidence ready', {exact: true}).waitFor();
  const staleResolution = await post(followthrough + '/am-actions/' + action.id + '/resolve', {
    expected_evidence_sha: action.evidence_sha256, expected_version: action.version,
    note: 'This observation precedes buyer feedback.', event_id: 'FOLLOW-UI-STALE-AM',
  });
  check('Buyer feedback blocks an AM resolution submitted against the earlier delivery evidence',
    staleResolution.status() === 409);
  const {state: refreshed, request: openRequest} = await command('Open channel action');
  const updatedAction = refreshed.am_actions.at(-1);
  const duplicate = await post(followthrough + '/am-actions', openRequest);
  const duplicateState = await duplicate.json();
  const equivalent = await post(followthrough + '/am-actions', {...openRequest, event_id: 'FOLLOW-UI-REOPEN'});
  const equivalentState = await equivalent.json();
  check('AM refresh keeps one action and duplicate opens retain its current version',
    refreshed.am_actions.length === 1 && updatedAction.id === action.id && updatedAction.version > action.version
      && updatedAction.evidence_sha256 === refreshed.evidence.sha256 && refreshed.evidence.feedback_id === feedback.id
      && duplicate.ok() && JSON.stringify(duplicateState.am_actions) === JSON.stringify(refreshed.am_actions)
      && equivalent.ok() && JSON.stringify(equivalentState.am_actions) === JSON.stringify(refreshed.am_actions));

  await page.getByLabel('Requested commercial terms', {exact: true}).fill(requestedTerms);
  const pricing = page.getByRole('region', {name: 'Read-only pricing preview', exact: true});
  const price = pricing.getByLabel('Hypothetical advertiser price per lead', {exact: true});
  const offerBeforePricing = await (await get('/api/v2/offers')).json();
  const bdBeforePricing = await (await get(followthrough)).json();
  for (const scenario of [
    {price: '50.00', margin: 50, clears: true, label: 'Clears margin floor'},
    {price: '30.00', margin: 100 / 6, clears: false, label: 'Below margin floor'},
  ]) {
    await price.fill(scenario.price);
    const [response] = await Promise.all([
      page.waitForResponse(response => response.url().startsWith(base + offer + '/pricing-preview?')
        && response.request().method() === 'GET'),
      pricing.getByRole('button', {name: 'Preview margin', exact: true}).click(),
    ]);
    if (!response.ok()) throw new Error('Pricing preview HTTP ' + response.status());
    const preview = await response.json();
    await pricing.getByText(scenario.label, {exact: true}).waitFor();
    const displayed = await pricing.innerText();
    check('Synthetic price ' + scenario.price + ' shows the expected margin and floor decision on the released version',
      preview.config_version === released.offer.version && preview.currency === 'USD'
        && preview.channel_payout === '25.00' && preview.margin_floor_pct === '20.00'
        && Math.abs(Number(preview.margin_pct) - scenario.margin) < 0.005
        && preview.clears_floor === scenario.clears
        && displayed.includes('25.00') && displayed.includes('20.00')
        && displayed.includes(scenario.margin.toFixed(2) + '%')
        && new RegExp('version\\s+' + released.offer.version + '\\b', 'i').test(displayed));
  }
  check('Pricing previews preserve the Offer, its release, BD evidence and requested terms',
    JSON.stringify(await (await get('/api/v2/offers')).json()) === JSON.stringify(offerBeforePricing)
      && JSON.stringify(await (await get(followthrough)).json()) === JSON.stringify(bdBeforePricing)
      && await page.getByLabel('Requested commercial terms', {exact: true}).inputValue() === requestedTerms);
  await screenshot('03-read-only-pricing-preview.png');
  const {state: prepared} = await command('Prepare synthetic proposal');
  const proposal = prepared.proposals.at(-1);
  const proposalCard = page.getByRole('article', {name: 'Proposal ' + proposal.id});
  check('Approved clauses come from configuration and requested terms stay separate',
    proposal.approved_clauses.includes('40.00') && !proposal.approved_clauses.includes('99.00')
      && proposal.requested_terms === requestedTerms && proposal.evidence_sha256 === refreshed.evidence.sha256
      && (await proposalCard.locator('.v2-requested-terms').innerText()).includes(requestedTerms));
  await page.getByLabel('BD review note', {exact: true}).fill('Checked approved clauses and current buyer evidence.');
  const {state: reviewed} = await command('Record BD review');
  check('BD owner review is recorded against the current Offer evidence',
    reviewed.proposals.at(-1).status === 'reviewed' && reviewed.proposals.at(-1).current
      && reviewed.proposals.at(-1).review.evidence_sha256 === reviewed.evidence.sha256);
  await page.getByLabel('AM resolution note', {exact: true}).fill('Reviewed both rejected fixture rows with the channel owner.');
  const {state: resolved, request: resolutionRequest} = await command('Record AM resolution');
  const resolution = resolved.am_actions.at(-1);
  const repeatedResolution = await post(followthrough + '/am-actions/' + resolution.id + '/resolve', resolutionRequest);
  check('AM resolution retains its evidence and schedules the next review once',
    resolution.status === 'resolved' && resolution.resolution.evidence_sha256 === resolved.evidence.sha256
      && new Date(resolution.next_review_at) - new Date(resolution.resolution.created_at) === 24 * 3600 * 1000
      && repeatedResolution.ok()
      && JSON.stringify((await repeatedResolution.json()).am_actions) === JSON.stringify(resolved.am_actions));
  await screenshot('01-reviewed-proposal-and-resolved-channel-action.png');

  await page.getByLabel('Requested commercial terms', {exact: true}).fill('Request a later payment date.');
  await command('Prepare synthetic proposal');
  await page.getByLabel('BD review note', {exact: true}).fill('This review belongs to the old buyer evidence.');
  const correction = await post(offer + '/feedback', {
    batch_id: batch.id, scenario: 'buyer_outcomes', event_id: 'FOLLOW-UI-CORRECTED-FEEDBACK',
  });
  if (!correction.ok()) throw new Error('Replacement buyer feedback failed');
  const corrected = await correction.json();
  await command('Record BD review', 409);
  await proposalCard.getByText('Historical evidence', {exact: true}).waitFor();
  const correctedProjection = await (await get(followthrough)).json();
  check('Replacement buyer evidence makes prior reviews historical and blocks a stale browser review',
    correctedProjection.evidence.feedback_id === corrected.feedback.at(-1).id
      && correctedProjection.evidence.sha256 !== reviewed.evidence.sha256
      && correctedProjection.proposals.every(record => !record.current)
      && correctedProjection.proposals.filter(record => record.review).length === 1);

  const mismatched = await post(followthrough + '/proposals', {
    expected_evidence_sha: '0'.repeat(64), requested_terms: 'Mismatched evidence.',
    event_id: 'FOLLOW-UI-WRONG-EVIDENCE',
  });
  const afterMismatch = await (await get(followthrough)).json();
  check('A mismatched evidence fingerprint cannot create a proposal',
    mismatched.status() === 409 && afterMismatch.proposals.length === correctedProjection.proposals.length);

  await page.getByLabel('Requested commercial terms', {exact: true}).fill(requestedTerms);
  const {state: freshDraft} = await command('Prepare synthetic proposal');
  await page.getByLabel('BD review note', {exact: true}).fill('Reviewed the replacement buyer evidence and unchanged approved clauses.');
  const {state: freshReview} = await command('Record BD review');
  check('A fresh draft and review bind the replacement buyer evidence',
    freshDraft.proposals.at(-1).id !== proposal.id && freshReview.proposals.at(-1).current
      && freshReview.proposals.at(-1).review.evidence_sha256 === correctedProjection.evidence.sha256);

  const tick = await post('/api/tick', {advance_hours: 24});
  if (!tick.ok()) throw new Error('Synthetic clock advance failed');
  await page.getByRole('button', {name: 'Refresh Offer evidence', exact: true}).click();
  await page.getByText('Review due', {exact: true}).waitFor();
  const dueProjection = await (await get(followthrough)).json();
  check('Recurring review becomes due while the prior AM resolution is retained',
    dueProjection.am_actions.length === 1 && dueProjection.am_actions[0].status === 'resolved'
      && dueProjection.am_actions[0].review_due);

  await clickTab('Quality & feedback');
  await page.getByLabel('Buyer feedback scenario', {exact: true}).selectOption('return_dispute');
  const {state: disputed} = await command('Record synthetic buyer feedback');
  const disputedFeedback = disputed.feedback.at(-1);
  await clickTab('BD & AM follow-through');
  await page.getByText('Finance owns the return decision', {exact: true}).waitFor();
  await page.getByLabel('Requested commercial terms', {exact: true}).fill(requestedTerms);
  check('The Finance hold blocks new BD and AM decisions',
    await page.getByRole('button', {name: 'Prepare synthetic proposal', exact: true}).isDisabled()
      && await page.getByRole('button', {name: 'Open channel action', exact: true}).isDisabled());
  await page.setViewportSize({width: 390, height: 844});
  check('Offer follow-through fits a mobile viewport',
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await screenshot('02-finance-hold-and-historical-follow-through.png');
  await clickTab('Open Finance review');
  const financeBatch = page.getByLabel('Finance review batch', {exact: true});
  check('The Finance hold opens the exact disputed batch',
    await financeBatch.inputValue() === batch.id);
  const {state: nextDelivery} = await command('Run synthetic lead batch');
  await financeBatch.selectOption('');
  check('A later delivery leaves the prior disputed batch available for Finance review',
    nextDelivery.batches.at(-1).id !== batch.id
      && await financeBatch.locator('option', {hasText: batch.id + ' · Finance hold'}).count() === 1);
  await financeBatch.selectOption(batch.id);
  await page.getByLabel('Finance review note', {exact: true}).fill('Disputed return held for Finance under unresolved return rules.');
  const {state: held, request: financeRequest} = await command('Record reconciliation preview');
  const financeReview = held.reconciliations.at(-1);
  const finance = financeReview.payload;
  check('Finance retains the original disputed batch and feedback with unknown totals and no payout',
    financeRequest.batch_id === batch.id && financeRequest.expected_feedback_id === disputedFeedback.id
      && financeReview.batch_id === batch.id && financeReview.feedback_id === disputedFeedback.id
      && finance.status === 'blocked_rules_decision' && finance.provisional_receivable_usd === null
      && finance.provisional_channel_cost_usd === null && !held.effects.payout_enabled
      && !held.effects.external_effects);
  check('No unexpected browser errors', !results.page_errors.length && !results.console_errors.length);
  results.pass = true;
} catch (error) {
  results.pass = false;
  results.error = error.stack;
  throw error;
} finally {
  results.finished_at_utc = new Date().toISOString();
  fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2) + '\n');
  await browser?.close();
  console.log(JSON.stringify(results, null, 2));
}
