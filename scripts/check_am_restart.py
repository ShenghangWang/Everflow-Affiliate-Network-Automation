"""Real server-restart evidence for synthetic activation and recurring AM."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import socket,subprocess,sys,tempfile,time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/tests';OUT.mkdir(exist_ok=True)
result={'started_at':datetime.now(timezone.utc).isoformat(),'checks':[],'live_effects':False,'model_calls':0}
process=None;log=(OUT/'am-process.log').open('w')
with socket.socket() as reserve:
    reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
base=f'http://127.0.0.1:{port}'

def call(path,body=None):
    request=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'} if body is not None else {})
    with urllib.request.urlopen(request,timeout=3) as r:return json.load(r)

def start(db):
    global process
    command=[sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(port),'--workers','1']
    result.setdefault('commands',[]).append(command)
    process=subprocess.Popen(command,cwd=ROOT,env={**os.environ,'EVERFLOW_DEMO_DB':str(db)},stdout=log,stderr=subprocess.STDOUT)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('AM verification server exited')
        try:
            if call('/api/health')['status']=='ok':return
        except (OSError,ValueError):time.sleep(.1)
    raise RuntimeError('AM server not ready')

def stop():
    global process
    if process is None:return
    process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    result.setdefault('server_exit_codes',[]).append(process.returncode);process=None

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def check(name,condition,**detail):
    result['checks'].append({'name':name,'pass':bool(condition),**detail})
    if not condition:raise AssertionError(name)

def apply(account,fixture,event):return call(f"/api/am/accounts/{account['id']}/fixture",{'fixture_id':fixture,'event_id':event})
def decide(account,decision):return call(f"/api/am/accounts/{account['id']}/decision",{'expected_version':account['version'],'decision':decision,'note':'Synthetic owner reviewed current facts','evidence':'Current immutable fixture evidence, mapping/test and outcome checks'})

try:
    with tempfile.TemporaryDirectory(prefix='everflow-am-restart-') as temp:
        db=Path(temp)/'verify.sqlite3';start(db)
        call('/api/leads/L001/reply',{'text':'I am interested','event_id':'BD-AM-HANDOFF'})
        proposal=call('/api/leads/L001/proposal',{'meeting_note':'Requested USD50 Net-7; unapproved','event_id':'AM-PROPOSAL'})['drafts'][0]
        call(f"/api/proposals/{proposal['id']}/review",{'expected_version':proposal['version'],'note':'Current clauses verified','evidence':'Approved structured terms only, requested changes excluded'})
        am=call('/api/am/start',{'lead_id':'L001'});account=am['accounts'][0]
        am=apply(account,'signed_only','SIGNATURE-1')
        check('Signed intake remains pending and no AM check is scheduled',am['accounts'][0]['status']=='pending_activation' and not am['tasks'])
        before=call('/api/state');stop();start(db);after=call('/api/state')
        check('Pending activation and exact evidence survive restart',fingerprint(before)==fingerprint(after),state_sha256=fingerprint(after))
        am=apply(am['accounts'][0],'ready','READY-1');am=decide(am['accounts'][0],'approve_activation')
        check('Owner activation approval creates first/recurring tasks without an outcome claim',len(am['tasks'])==2 and am['accounts'][0]['outcome_status']=='unverified')
        am=apply(am['accounts'][0],'tracking_fault','FAULT-1');before=call('/api/state');stop();start(db);after=call('/api/state')
        check('Active issue, current integration owner and scheduled tasks survive restart',fingerprint(before)==fingerprint(after) and after['account_management']['accounts'][0]['next_owner']=='Demo integration owner')
        call('/api/tick',{'advance_hours':24});state=call('/api/tick',{'advance_hours':0})
        alerts=[e for e in state['audit'] if e['event']=='am_followthrough_due']
        check('First-outcome and issue checks become due once each',len(alerts)==2 and len([t for t in state['account_management']['tasks'] if t['status']=='due'])==2)
        am=apply(state['account_management']['accounts'][0],'tracking_fixed','FIX-1');am=decide(am['accounts'][0],'verify_outcome')
        check('Repair plus fresh accepted outcome resolves issues and preserves one next review',am['accounts'][0]['outcome_status']=='verified' and all(i['status']=='resolved' for i in am['issues']) and len([t for t in am['tasks'] if t['status']=='scheduled'])==1)
        before=call('/api/state');stop();start(db);after=call('/api/state')
        check('Outcome history and next recurring review survive a third restart',fingerprint(before)==fingerprint(after))
        call('/api/tick',{'advance_hours':168});state=call('/api/tick',{'advance_hours':0});am=state['account_management']
        check('Recurring stale health becomes unknown and has an owned refresh action',am['accounts'][0]['health']['accepted_outcomes'] is None and am['accounts'][0]['next_owner']=='Demo integration owner' and am['accounts'][0]['draft'] is None)
        am=decide(am['accounts'][0],'cancel');before=len([e for e in call('/api/state')['audit'] if e['event']=='am_followthrough_due'])
        state=call('/api/tick',{'advance_hours':168})
        check('Cancellation prevents future due alerts and preserves history',state['account_management']['accounts'][0]['status']=='cancelled' and len([e for e in state['audit'] if e['event']=='am_followthrough_due'])==before and all(t['status'] not in ('scheduled','due') for t in state['account_management']['tasks']))
        check('Owned proposal review and excluded meeting note survive the AM restarts',state['commercial']['drafts'][0]['status']=='reviewed_draft' and len(state['commercial']['decisions'])==1 and 'USD50' not in state['commercial']['drafts'][0]['content'] and state['commercial']['drafts'][0]['note'].startswith('Requested USD50'))
        check('Full cycle grants no outbound or campaign authority',not state['actions'] and len(state['messages'])==1 and state['messages'][0]['direction']=='inbound' and not am['effects']['campaign_controls_enabled'] and state['cost']['provider_attempts']==0)
        stop()
    result['pass']=True
except Exception as exc:
    result['pass']=False;result['error']=repr(exc);raise
finally:
    stop();log.close();result['finished_at']=datetime.now(timezone.utc).isoformat()
    result['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('backend','tests') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts}
    (OUT/'am-restart.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
