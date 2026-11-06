"""One Offer reaches owned outcomes across real local-server restarts; no live effects."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT = ROOT / '.run' / 'v2-evidence'
OUT.mkdir(parents=True, exist_ok=True)
sources = sorted([*ROOT.glob('backend/**/*.py'), *ROOT.glob('backend/fixtures/*.json'),
                  ROOT / 'requirements.lock', Path(__file__)])
result = {
    'started_at_utc': datetime.now(timezone.utc).isoformat(),
    'git_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'clean_checkout': not subprocess.check_output(
        ['git', 'status', '--porcelain'], cwd=ROOT, text=True
    ).strip(),
    'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in sources},
    'checks': [],
    'commands': [],
    'mode': 'Synthetic Offer, temporary SQLite database, simulated effects',
}
process=None;log=(OUT/'process.log').open('w')
with socket.socket() as reserve:
    reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
base=f'http://127.0.0.1:{port}';offer='/api/v2/offers/OFR-SYN-1'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, target):
        return None

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

def call(path,payload=None,status=200):
    req=urllib.request.Request(base+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'} if payload is not None else {})
    try:
        with opener.open(req,timeout=4) as response:
            code=response.status;data=json.load(response)
    except urllib.error.HTTPError as e:
        code=e.code;data=json.load(e)
    if code!=status:raise AssertionError(f'{path}: expected{status},got{code}: {data}')
    return data

def start(db):
    global process
    cmd=[sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(port),'--workers','1']
    result['commands'].append(cmd)
    process=subprocess.Popen(cmd,cwd=ROOT,env={**os.environ,'EVERFLOW_DEMO_DB':str(db)},stdout=log,stderr=subprocess.STDOUT)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('Temporary Offer server exited')
        try:
            if call('/api/health')['status']=='ok':return
        except OSError:time.sleep(.1)
    raise RuntimeError('Temporary Offer server not ready')

def stop(kill=False):
    global process
    if process is None:return
    process.kill() if kill else process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    result.setdefault('stops',[]).append({'pid':process.pid,'mode':'SIGKILL' if kill else 'SIGTERM','exit_code':process.returncode});process=None

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def check(name,condition,**detail):
    result['checks'].append({'name':name,'pass':bool(condition),**detail})
    if not condition:raise AssertionError(name)
def command(kind,**body):return call(offer+'/'+kind,body)

try:
    with tempfile.TemporaryDirectory(prefix='everflow-v2-offer-') as temp:
        db=Path(temp)/'verification.sqlite3';start(db)
        state=call('/api/v2/offers');version=state['offer']['version']
        state=command('test',expected_version=version,scenario='failed_verification',event_id='FAIL-1')
        call(offer+'/release',{'expected_version':version,'test_id':state['tests'][-1]['id'],'note':'Synthetic owner verification','event_id':'BLOCK-FAIL'},409)
        check('Failed mock verification cannot release an Offer',not call('/api/v2/offers')['releases'])
        state=command('test',expected_version=version,scenario='healthy',event_id='PASS-1')
        release={'expected_version':version,'test_id':state['tests'][-1]['id'],'note':'Current synthetic terms and mapping inspected','event_id':'RELEASE-1'}
        state=call(offer+'/release',release);same=call(offer+'/release',release)
        check('Exact-version owner release is idempotent and retains test/configuration linkage',state==same and len(state['releases'])==1 and state['releases'][0]['config_sha']==state['offer']['config_sha'])
        batch_body={'expected_version':version,'scenario':'mixed_quality','event_id':'BATCH-1'}
        state=call(offer+'/batch',batch_body);same=call(offer+'/batch',batch_body);batch=state['batches'][-1]
        check('Synthetic qualification rejects missing/failed evidence and duplicate intake cannot redeliver',state==same and batch['payload']['qualified_delivered']==2 and batch['payload']['rejected']==2 and len(state['batches'])==1)
        state=command('feedback',batch_id=batch['id'],scenario='buyer_outcomes',event_id='FEEDBACK-1')
        flow = offer + '/followthrough'
        evidence = call(flow)['evidence']
        stamp = {'expected_evidence_sha': evidence['sha256']}
        proposal = call(flow + '/proposals', {
            **stamp, 'requested_terms': 'Request USD 999 and a higher cap',
            'event_id': 'BD-PREPARE-1',
        })['proposals'][0]
        reviewed = call(flow + '/proposals/' + proposal['id'] + '/review', {
            **stamp, 'expected_version': proposal['version'],
            'note': 'Exact released Offer, capacity and buyer outcomes checked', 'event_id': 'BD-REVIEW-1',
        })['proposals'][0]
        check('BD reviews exact evidence and retains requested terms outside approved clauses',
              reviewed['status'] == 'reviewed' and reviewed['current']
              and 'USD 999' in reviewed['requested_terms'] and 'USD 999' not in reviewed['approved_clauses'])
        am = call(flow + '/am-actions', {**stamp, 'event_id': 'AM-OPEN-1'})['am_actions'][0]
        duplicate = call(flow + '/am-actions', {**stamp, 'event_id': 'AM-OPEN-2'})
        check('One scoped AM issue survives an independent duplicate request',
              len(duplicate['am_actions']) == 1 and duplicate['am_actions'][0]['id'] == am['id'])
        resolution = call(flow + '/am-actions/' + am['id'] + '/resolve', {
            **stamp, 'expected_version': am['version'], 'note': 'Reviewed and retained rejection reasons',
            'event_id': 'AM-RESOLVE-1',
        })['am_actions'][0]
        check('AM records an owned resolution and a future synthetic review',
              resolution['status'] == 'resolved' and resolution['next_review_at'] and not resolution['review_due'])
        state=command('reconcile',batch_id=batch['id'],expected_feedback_id=state['feedback'][-1]['id'],note='Matched synthetic buyer outcome references and configuration terms',event_id='FIN-1')
        preview=state['reconciliations'][-1]['payload']
        check('Buyer feedback produces a version-linked provisional finance review and three owned role recommendations',preview['status']=='reviewed_fixture' and preview['provisional_receivable_usd']=='80.00' and preview['provisional_channel_cost_usd']=='50.00' and {r['role'] for r in state['recommendations']}=={'BD','AM','AdOps'})
        state=command('feedback',batch_id=batch['id'],scenario='return_dispute',event_id='DISPUTE-1')
        state=command('reconcile',batch_id=batch['id'],expected_feedback_id=state['feedback'][-1]['id'],note='Unresolved clock/cap deduction rules require Finance decision',event_id='FIN-DISPUTE')
        preview=state['reconciliations'][-1]['payload']
        check('Ambiguous returns remain Finance-owned with unknown totals and no downstream deduction',preview['status']=='blocked_rules_decision' and preview['provisional_receivable_usd'] is None and preview['provisional_channel_cost_usd'] is None and len(state['reconciliations'])==2)
        call('/api/tick',{'advance_hours':24});state=call('/api/v2/offers')
        check('Current-day capacity is independent of historical batch quality after rollover',state['quality_capacity']['available_channel_capacity']==30 and state['quality_capacity']['capacity_window']['server_counted_delivered']==0 and state['quality_capacity']['quality_window']['batch_observed_at']!=state['quality_capacity']['capacity_window']['observed_at'])
        owned_before = call(flow)
        check('Dispute invalidates BD evidence and AM recurrence becomes due without new action',
              not owned_before['evidence']['bd_ready'] and not owned_before['evidence']['am_ready']
              and not owned_before['proposals'][0]['current']
              and len(owned_before['am_actions']) == 1 and owned_before['am_actions'][0]['review_due'])
        before=state;stop(kill=True);start(db);after=call('/api/v2/offers')
        owned_after = call(flow)
        check('BD and AM history plus recurring review state survive SIGKILL/restart',
              fingerprint(owned_before) == fingerprint(owned_after),
              before_sha256=fingerprint(owned_before), after_sha256=fingerprint(owned_after))
        check('Release, qualification, buyer feedback and both finance outcomes survive SIGKILL/restart',fingerprint(before)==fingerprint(after),before_sha256=fingerprint(before),after_sha256=fingerprint(after))
        old_test=after['offer']['latest_test_id']
        state=command('configure',expected_version=version,change={'payout_cpl':'26.00'},event_id='TERMS-2');version=state['offer']['version']
        check('Material terms edit invalidates old test/release without deleting history',state['offer']['latest_test_id'] is None and state['offer']['active_release_id'] is None and len(state['releases'])==1)
        call(offer+'/release',{'expected_version':version,'test_id':old_test,'note':'Old test must not authorize new terms','event_id':'STALE'},409)
        call(offer+'/batch',{'expected_version':version,'scenario':'all_qualified','event_id':'NO-RELEASE'},409)
        state=command('configure',expected_version=version,change={'mapping_version':'SYN-MAP-2'},event_id='MAP-2');version=state['offer']['version']
        check('Mapping change also requires fresh exact-version test and owner release',state['offer']['active_release_id'] is None and state['offer']['latest_test_id'] is None)
        state=command('test',expected_version=version,scenario='unknown_outcome',event_id='UNKNOWN')
        call(offer+'/release',{'expected_version':version,'test_id':state['tests'][-1]['id'],'note':'Unknown outcome is not success','event_id':'NO-UNKNOWN'},409)
        check('Unknown verification cannot authorize launch',call('/api/v2/offers')['offer']['active_release_id'] is None)
        state=command('test',expected_version=version,scenario='healthy',event_id='PASS-2')
        state=command('release',expected_version=version,test_id=state['tests'][-1]['id'],note='Fresh config and readback evidence reviewed',event_id='RELEASE-2')
        before=state;stop(kill=True);start(db);after=call('/api/v2/offers')
        check('Re-tested release and immutable prior configuration history survive another restart',fingerprint(before)==fingerprint(after) and len(after['releases'])==2 and len(after['config_versions'])==3)
        check('All effects remain simulated; no price/payout/routing or sponsor authority inferred',not after['effects']['external_effects'] and after['effects']['live_platform_calls']==0 and not after['effects']['production_launch_enabled'])
        result['final_summary']={'offer':after['offer'],'records':{k:len(after[k]) for k in ['config_versions','tests','releases','batches','feedback','reconciliations']},'effects':after['effects']}
        stop()
    result['pass']=True
except Exception as e:
    result.update({'pass':False,'error':repr(e)});raise
finally:
    stop();log.close();result['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    (OUT/'process-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
