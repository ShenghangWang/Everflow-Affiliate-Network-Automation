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
const require=createRequire(import.meta.url);
const out = path.join(root, '.run', 'v2-evidence', 'ui');
fs.mkdirSync(out, {recursive: true});

const git = (...args) => execFileSync('git', args, {cwd: root, encoding: 'utf8'}).trim();
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const trackedUiInputs = git('ls-files', '-z', 'frontend/src', 'frontend/package-lock.json',
  'frontend/index.html', 'frontend/vite.config.js', 'scripts/check_v2_ui.mjs').split('\0').filter(Boolean);
const result = {
  started_at_utc: new Date().toISOString(),
  git_revision: git('rev-parse', 'HEAD'),
  clean_checkout: !git('status', '--porcelain'),
  source_sha256: Object.fromEntries(trackedUiInputs.map(file => [file, sha256(fs.readFileSync(path.join(root, file)))])),
  assets_sha256: {},
  base,
  checks: [],
  console_errors: [],
  page_errors: [],
  mode: 'Synthetic Offer, simulated effects',
};
let browser;
try{
 const pw = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright');
 browser = await pw.chromium.launch({
   headless: true,
   ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath: process.env.CHROMIUM_EXECUTABLE} : {}),
 });
 result.browser = browser.version();
 const page=await browser.newPage({viewport:{width:1440,height:1050},deviceScaleFactor:1});
 await page.route('**/*', route => new URL(route.request().url()).origin === base
   ? route.continue()
   : route.abort());
 const request = (method, endpoint, options = {}) => page.request[method](base + endpoint, {
   ...options, maxRedirects: 0,
 });
 const dist = path.join(root, 'frontend', 'dist');
 const builtFiles = ['index.html', ...fs.readdirSync(path.join(dist, 'assets'))
   .sort().map(file => 'assets/' + file)];
 for (const file of builtFiles) {
   const expectedHash = sha256(fs.readFileSync(path.join(dist, file)));
   const response = await request('get', file === 'index.html' ? '/' : '/' + file);
   if (!response.ok() || sha256(await response.body()) !== expectedHash) {
     throw new Error('The demo server must serve the current checkout build: ' + file);
   }
   result.assets_sha256[file] = expectedHash;
 }
 page.on('pageerror',e=>result.page_errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('409'))result.console_errors.push(m.text())});
 const state = async () => {
   const response = await request('get', '/api/v2/offers');
   if (!response.ok()) throw new Error('Offer state HTTP ' + response.status());
   return response.json();
 };
 const check=(name,pass,detail={})=>{result.checks.push({name,pass:!!pass,detail});if(!pass)throw Error(name+': '+JSON.stringify(detail))};
 const click=async(name)=>{const [r]=await Promise.all([page.waitForResponse(r=>r.url().includes('/api/')&&r.request().method()==='POST'),page.getByRole('button',{name,exact:true}).click()]);const data=await r.json();await page.getByRole(r.ok()?'status':'alert').waitFor();return{status:r.status(),data}};
 const initial = await state();
 if (initial.effects.external_effects !== false || initial.effects.live_platform_calls !== 0) {
   throw new Error('The verifier requires the simulated Offer server');
 }
 const reset = await request('post', '/api/reset');
 if (!reset.ok()) throw new Error('Synthetic reset HTTP ' + reset.status());
 await page.goto(base);await page.getByRole('heading',{name:'Operate one Offer',exact:true}).waitFor();
 check('V2 starts with advertiser–Offer–channel and six owned operating handoffs',await page.locator('.v2-cycle article').count()===6&&(await page.locator('body').innerText()).includes('ADV-SYN-1'));
 await page.screenshot({path:out+'/01-offer-cycle.png',fullPage:true});
 await page.getByRole('button',{name:'Launch readiness',exact:true}).click();
 await page.getByLabel('Platform mapping version',{exact:true}).fill('SYN-MAP-UI2');let r=await click('Save synthetic configuration'),s=r.data;
 check('Approved fixture terms and platform mapping produce a retained configuration version',s.offer.version===2&&s.config_versions.length===2&&!s.offer.active_release_id);
 await page.getByLabel('Mock verification scenario').selectOption('failed_verification');r=await click('Run mock platform test');
 await page.getByLabel('Launch owner verification note').fill('Synthetic release owner inspected exact terms and mapping evidence.');r=await click('Record owner release of this version');
 check('A failed verification cannot produce release from the UI',r.status===409&&(await state()).releases.length===0);
 await page.screenshot({path:out+'/02-failed-verification.png',fullPage:true});
 await page.getByLabel('Mock verification scenario').selectOption('healthy');await click('Run mock platform test');r=await click('Record owner release of this version');s=r.data;
 check('Owner releases only the exact tested configuration',s.offer.status==='released_simulated'&&s.releases.length===1&&s.releases[0].config_sha===s.offer.config_sha&&s.releases[0].test_id===s.offer.latest_test_id);
 const beforeReplay=await state();await click('Replay last request');check('Duplicate release request preserves one logical owner decision',JSON.stringify(beforeReplay)===JSON.stringify(await state()));
 await page.screenshot({path:out+'/03-exact-version-release.png',fullPage:true});
 await page.getByRole('button',{name:'Quality & feedback',exact:true}).click();r=await click('Run synthetic lead batch');s=r.data;const batch=s.batches.at(-1);
 check('Released placement qualifies and delivers only eligible synthetic leads',batch.payload.received===4&&batch.payload.qualified_delivered===2&&batch.payload.rejected===2&&batch.release_id===s.offer.active_release_id);
 check('Before buyer feedback, quality stays unknown and has an owned next action',s.quality_capacity.quality_known===false&&s.quality_capacity.counts.connected===null&&s.quality_capacity.counts.closed_won===null&&s.recommendations.every(x=>x.action.includes('unknown')));
 const beforeBatchReplay=await state();await click('Replay last request');check('Duplicate batch request cannot deliver or consume capacity twice',JSON.stringify(beforeBatchReplay)===JSON.stringify(await state()));
 r=await click('Record synthetic buyer feedback');s=r.data;
 check('Buyer outcomes create a visible quality/capacity pack for BD, AM and AdOps',s.quality_capacity.counts.connected===2&&s.quality_capacity.counts.closed_won===1&&s.quality_capacity.available_channel_capacity===28&&new Set(s.recommendations.map(x=>x.role)).size===3);
 await page.getByLabel('Finance review note',{exact:true}).fill('Finance checked exact synthetic batch, accepted buyer outcomes and bound fixture terms.');r=await click('Record reconciliation preview');s=r.data;
 check('Offer evidence reaches an owned provisional reconciliation outcome',s.reconciliations.at(-1).payload.status==='reviewed_fixture'&&s.reconciliations.at(-1).payload.provisional_receivable_usd==='80.00'&&!s.effects.payout_enabled);
 await page.screenshot({path:out+'/04-delivery-feedback-finance.png',fullPage:true});
 const viewedFeedbackId=s.feedback.at(-1).id;await page.getByLabel('Buyer feedback scenario').selectOption('return_dispute');await click('Record synthetic buyer feedback');const staleFinance=await request('post','/api/v2/offers/OFR-SYN-1/reconcile',{data:{batch_id:batch.id,expected_feedback_id:viewedFeedbackId,note:'Viewed earlier feedback, must not attach to newer facts',event_id:'UI-STALE-FINANCE'}});check('Finance cannot attach a viewed-version review to newer buyer feedback',staleFinance.status()===409);r=await click('Record reconciliation preview');s=r.data;
 check('Ambiguous return treatment stays Finance-owned and supersedes earlier feedback conclusions',s.reconciliations.at(-1).payload.status==='blocked_rules_decision'&&s.reconciliations.at(-1).payload.provisional_receivable_usd===null&&s.reconciliations[0].current_feedback===false);
 await page.screenshot({path:out+'/05-owned-return-decision.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});check('Mobile Offer workflow has no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:out+'/06-mobile-offer-outcomes.png',fullPage:true});await page.setViewportSize({width:1440,height:1050});
 await page.getByRole('button',{name:'Launch readiness',exact:true}).click();await page.getByLabel('Platform mapping version').fill('SYN-MAP-UI3');r=await click('Save synthetic configuration');s=r.data;
 check('Changing material mapping invalidates old evidence and owner release',s.offer.version===3&&s.offer.latest_test_id===null&&s.offer.active_release_id===null&&s.releases.length===1&&await page.getByRole('button',{name:'Record owner release of this version',exact:true}).isDisabled());
 await page.getByLabel('Channel payout per lead').fill('26.00');r=await click('Save synthetic configuration');s=r.data;
 check('Changing terms creates another version and old quality/capacity stays historical',s.offer.version===4&&s.offer.active_release_id===null&&!s.quality_capacity.quality_known&&s.quality_capacity.available_channel_capacity===null);
 await page.screenshot({path:out+'/07-material-change-invalidation.png',fullPage:true});
 await page.getByRole('button',{name:'Open decisions',exact:true}).click();check('Required return-clock, pricing predicate and cap-deduction decisions are visible',(await page.locator('tbody tr').count())===5);await page.screenshot({path:out+'/08-open-business-decisions.png',fullPage:true});
 await page.goto(base+'/?baseline=1');await page.getByRole('heading',{name:'From prospect to owned outcome'}).waitFor();check('Preserved generic baseline remains accessible alongside local v2',(await page.locator('body').innerText()).includes('offline template fallback'));
 check('No unexpected browser JavaScript or console errors',result.page_errors.length===0&&result.console_errors.length===0,{page_errors:result.page_errors,console_errors:result.console_errors});
 result.final_summary={offer:s.offer,records:{tests:s.tests.length,releases:s.releases.length,batches:s.batches.length,feedback:s.feedback.length,reconciliations:s.reconciliations.length},effects:s.effects};result.pass=true;
}catch(e){result.pass=false;result.error=e.stack;throw e}finally{result.finished_at_utc=new Date().toISOString();fs.writeFileSync(out+'/results.json',JSON.stringify(result,null,2)+'\n');await browser?.close();console.log(JSON.stringify(result,null,2))}
