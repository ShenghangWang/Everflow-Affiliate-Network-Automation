from pathlib import Path
import urllib.request,json,datetime,hashlib,sqlite3,sys,traceback
p=Path('/private/tmp/everflow-fresh-state.json');s=json.loads(p.read_text());root=Path(s['fresh_directory']);base='http://127.0.0.1:8001';phase=sys.argv[1];observations=[]
def request(method,path,payload=None):
 data=None if payload is None else json.dumps(payload).encode();req=urllib.request.Request(base+path,data=data,method=method,headers={'Content-Type':'application/json'} if data else {})
 with urllib.request.urlopen(req,timeout=10) as r:
  raw=r.read();ctype=r.headers.get('Content-Type','');value=json.loads(raw) if 'application/json' in ctype else raw.decode();observations.append({'method':method,'url':base+path,'request_json':payload,'status':r.status,'content_type':ctype,'body':value,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});return value
try:
 page=request('GET','/');assert '<div id="root"></div>' in page
 health=request('GET','/api/health');assert health=={'status':'ok','mode':'synthetic-mock','live_effects':False}
 if phase=='before':
  request('POST','/api/reset',{});request('POST','/api/leads/L001/draft',{});request('POST','/api/leads/L001/dispatch',{})
 state=request('GET','/api/state');outreach=[a for a in state['actions'] if a['lead_id']=='L001' and a['kind']=='outreach'];followup=[a for a in state['actions'] if a['lead_id']=='L001' and a['kind']=='followup'];assert len(outreach)==len(followup)==1;assert outreach[0]['status']=='succeeded';assert followup[0]['status']=='scheduled';assert outreach[0]['attempts']==1
 with sqlite3.connect(root/'data/demo.sqlite3') as c: receipts=c.execute('select count(*) from receipts').fetchone()[0]
 assert receipts==1
 summary={'followup':followup[0],'outreach':outreach[0],'receipts':receipts,'state_sha256':hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()}
 if phase=='after':
  assert summary==s['before_restart'],'State changed across restart'
  s['restart_persistence']='PASS: exact action/state digest preserved, one accepted outreach and one scheduled followup'
  due=request('POST','/api/tick',{'advance_hours':72});action=next(a for a in due['actions'] if a['id']==followup[0]['id']);assert action['status']=='succeeded' and action['attempts']==1
  repeated=request('POST','/api/tick',{'advance_hours':0});action2=next(a for a in repeated['actions'] if a['id']==followup[0]['id']);assert action2['attempts']==1
  with sqlite3.connect(root/'data/demo.sqlite3') as c: assert c.execute('select count(*) from receipts').fetchone()[0]==2
  s['pending_continuation']='PASS: 72h tick after restart sent followup once; repeated tick retained two total receipts'
 s[phase+'_restart']=summary;s.setdefault('http_probes',[]).append({'phase':phase,'command':[sys.executable,__file__,phase],'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':0,'observations':observations});p.write_text(json.dumps(s,indent=2));print(json.dumps({'phase':phase,'result':'PASS','summary':summary},indent=2))
except Exception:
 error=traceback.format_exc();s.setdefault('http_probes',[]).append({'phase':phase,'command':[sys.executable,__file__,phase],'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':1,'observations':observations,'stderr':error});p.write_text(json.dumps(s,indent=2));sys.stderr.write(error);sys.exit(1)
