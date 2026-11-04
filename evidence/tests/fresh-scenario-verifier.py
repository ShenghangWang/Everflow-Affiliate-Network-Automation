from pathlib import Path
import urllib.request,urllib.error,json,datetime,hashlib,sys,traceback
p=Path('/private/tmp/everflow-fresh-state.json');s=json.loads(p.read_text());base='http://127.0.0.1:8001';observations=[]
def request(method,path,payload=None,expected=200):
 data=None if payload is None else json.dumps(payload).encode();req=urllib.request.Request(base+path,data=data,method=method,headers={'Content-Type':'application/json'} if data else {})
 try:r=urllib.request.urlopen(req,timeout=10)
 except urllib.error.HTTPError as e:r=e
 with r:
  raw=r.read();ctype=r.headers.get('Content-Type','');value=json.loads(raw) if 'application/json' in ctype else raw.decode();observations.append({'method':method,'url':base+path,'request_json':payload,'status':r.status,'content_type':ctype,'body':value,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});assert r.status==expected,(r.status,value);return value
try:
 before=request('GET','/api/state');default=request('GET','/api/scenario')
 assert len(default['baseline']['cohorts'])==2
 assert default['effects']=={'external_effects':False,'model_calls':0,'workflow_mutations':False}
 source=default['inputs']['affected_source'];shock=request('POST','/api/scenario',{'affected_source':source,'volume_shock_pct':-50,'acquisition_cost_change_pct':25})
 assert shock['inputs']['volume_shock_pct']=='-50' and shock['inputs']['acquisition_cost_change_pct']=='25'
 assert shock['effects']==default['effects']
 from decimal import Decimal
 for b,x in zip(shock['baseline']['cohorts'],shock['stressed']['cohorts']):
  if b['source_id']==source:assert Decimal(x['expected_opportunities'])==Decimal(b['expected_opportunities'])/2
  else:assert b==x
 for invalid in [{'volume_shock_pct':-101},{'acquisition_cost_change_pct':201},{'affected_source':'unapproved-source'},{'volume_shock_pct':'NaN'},{'workflow_mutations':True}]:request('POST','/api/scenario',invalid,400)
 after=request('GET','/api/state');assert before==after,'Scenario mutated workflow records'
 record={'phase':'final candidate scenario API','command':[sys.executable,__file__],'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':0,'observations':observations,'assertions':['two synthetic sources','bounded shock accepted and affected source volume halved','unaffected cohort unchanged','out-of-bounds/unknown source/NaN/extra field rejected400','workflow state before and after exactly equal','external effects false, model calls0, workflow mutations false']};s['scenario_http_probe']=record;p.write_text(json.dumps(s,indent=2));print(json.dumps({'result':'PASS','assertions':record['assertions']},indent=2))
except Exception:
 error=traceback.format_exc();s['scenario_http_probe']={'phase':'final candidate scenario API','command':[sys.executable,__file__],'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':1,'observations':observations,'stderr':error};p.write_text(json.dumps(s,indent=2));sys.stderr.write(error);sys.exit(1)
