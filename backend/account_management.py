"""Durable synthetic activation, recurring health review and owned follow-through.

Only allowlisted fixtures create evidence. Internal approval/outcome records are
not signatures, production identity, messages, tracker mutations or revenue.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "account_management.json"
TABLES = ("am_outcomes", "am_tasks", "am_issues", "am_events", "am_evidence", "am_accounts")


class StaleAccountAction(ValueError):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def instant(value):
    if not isinstance(value, str): raise ValueError("Timezone-qualified timestamp required")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None: raise ValueError("Timezone-qualified timestamp required")
    return parsed.astimezone(timezone.utc)


def settings():
    data = json.loads(FIXTURE.read_text())
    for key in ("readiness_max_age_hours", "health_max_age_hours", "first_outcome_check_hours", "health_review_hours", "issue_followup_hours"):
        if type(data.get(key)) is not int or not 1 <= data[key] <= 720:
            raise ValueError("AM fixture intervals must be integer hours within 1–720")
    return data


def ensure_schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS am_accounts(
      id TEXT PRIMARY KEY, lead_id TEXT NOT NULL UNIQUE REFERENCES leads(id), lead_version INTEGER NOT NULL,
      version INTEGER NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, next_owner TEXT NOT NULL,
      next_action TEXT NOT NULL, readiness_sha TEXT, health_sha TEXT, rules_sha TEXT NOT NULL,
      epoch INTEGER NOT NULL, activated_at TEXT, outcome_status TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS am_evidence(
      sha256 TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES am_accounts(id),
      kind TEXT NOT NULL, fixture_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS am_events(
      event_id TEXT PRIMARY KEY, request_sha TEXT NOT NULL, account_id TEXT NOT NULL REFERENCES am_accounts(id), created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS am_tasks(
      id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES am_accounts(id), epoch INTEGER NOT NULL,
      kind TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL, due_at TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, reason TEXT);
    CREATE TABLE IF NOT EXISTS am_issues(
      id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES am_accounts(id), epoch INTEGER NOT NULL,
      kind TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL,
      evidence_sha TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS am_outcomes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL REFERENCES am_accounts(id),
      account_version INTEGER NOT NULL, kind TEXT NOT NULL, evidence_sha TEXT, note TEXT NOT NULL,
      verification TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL,
      UNIQUE(account_id,account_version));
    """)


class AccountManagement:
    def __init__(self, workflow): self.w = workflow

    def account(self, c, account_id):
        row=c.execute("SELECT * FROM am_accounts WHERE id=?", (account_id,)).fetchone()
        if row is None: raise ValueError("Unknown activation/account case")
        return dict(row)

    def now(self,c): return self.w._get(c,"now")

    def rules(self,data): return {k:v for k,v in data.items() if k not in ("fixtures", "label")}

    def evidence(self,c,reference):
        if not reference: return None
        row=c.execute("SELECT payload FROM am_evidence WHERE sha256=?",(reference,)).fetchone()
        return json.loads(row[0]) if row else None

    def current(self,c,account):
        lead=self.w._lead(c,account["lead_id"])
        if lead["suppressed"]: return "source contact was suppressed"
        if lead["version"]!=account["lead_version"]: return "source business record changed"
        if account["rules_sha"]!=sha(self.rules(settings())): return "AM rule configuration changed"
        return None

    def readiness_problems(self,c,account,*,check_age=True):
        snapshot=self.evidence(c,account["readiness_sha"])
        if snapshot is None: return ["readiness evidence missing"]
        facts=snapshot["facts"];problems=[]
        if facts.get("terms_version")!=self.w._get(c,"terms")["version"]: problems.append("approved terms version changed")
        if not facts.get("signature_verified"): problems.append("signature verification missing")
        if not facts.get("checklist_complete"): problems.append("intake checklist incomplete")
        if not facts.get("mapping_version") or facts.get("tested_mapping_version")!=facts.get("mapping_version"): problems.append("matching sandbox mapping test missing")
        if not facts.get("release_approved"): problems.append("integration release approval missing")
        if check_age:
            age=(instant(self.now(c))-instant(snapshot["observed_at"])).total_seconds()/3600
            if age<0 or age>settings()["readiness_max_age_hours"]: problems.append("readiness evidence stale or future-dated")
        return problems

    def health_result(self,c,account):
        snapshot=self.evidence(c,account["health_sha"])
        if snapshot is None: return None,"account health evidence missing"
        age=(instant(self.now(c))-instant(snapshot["observed_at"])).total_seconds()/3600
        facts=snapshot["facts"]
        if age<0 or age>settings()["health_max_age_hours"]: return None,"account health evidence stale or future-dated"
        if not facts.get("complete") or type(facts.get("accepted_outcomes")) is not int or facts["accepted_outcomes"]<0:
            return None,"account health evidence incomplete"
        if facts.get("terms_version")!=self.w._get(c,"terms")["version"]: return None,"health evidence uses superseded terms"
        ready=self.evidence(c,account["readiness_sha"])
        if not ready or facts.get("mapping_version")!=ready["facts"].get("mapping_version"): return None,"health evidence uses a different mapping"
        if account["activated_at"] and instant(snapshot["observed_at"])<instant(account["activated_at"]): return None,"health evidence predates this activation"
        if facts.get("activation_epoch")!=account["epoch"] or facts.get("window_start")!=account["activated_at"] or facts.get("window_end")!=snapshot["observed_at"]:
            return None,"health evidence belongs to a different activation epoch or observation window"
        return facts,None

    def issue(self,c,account,kind,owner,summary):
        key="AMI-"+sha([account["id"],account["epoch"],kind])[:16]
        prior=c.execute("SELECT * FROM am_issues WHERE id=?",(key,)).fetchone()
        c.execute("INSERT INTO am_issues VALUES(?,?,?,?,?,'open',?,?,?,?) ON CONFLICT(id) DO UPDATE SET status='open',summary=excluded.summary,evidence_sha=excluded.evidence_sha,updated_at=excluded.updated_at",
                  (key,account["id"],account["epoch"],kind,owner,summary,account["health_sha"],self.now(c),self.now(c)))
        if not prior or prior["status"]!="open" or prior["summary"]!=summary:
            self.w._audit(c,"am_owned_issue_opened",account["lead_id"],account_id=account["id"],issue_id=key,kind=kind,owner=owner,summary=summary,external_effect=False)

    def task(self,c,account,kind,hours,owner):
        existing=c.execute("SELECT * FROM am_tasks WHERE account_id=? AND epoch=? AND kind=? AND status IN ('scheduled','due')",(account["id"],account["epoch"],kind)).fetchone()
        if existing:
            if existing["owner"]!=owner:
                c.execute("UPDATE am_tasks SET owner=?,updated_at=? WHERE id=?",(owner,self.now(c),existing["id"]))
                self.w._audit(c,"am_followthrough_reassigned",account["lead_id"],account_id=account["id"],task_id=existing["id"],owner=owner,external_effect=False)
            return
        due=(instant(self.now(c))+timedelta(hours=hours)).isoformat()
        key="AMT-"+sha([account["id"],account["epoch"],account["version"],kind,due])[:16]
        c.execute("INSERT INTO am_tasks VALUES(?,?,?,?,?,'scheduled',?,?,?,NULL)",(key,account["id"],account["epoch"],kind,owner,due,self.now(c),self.now(c)))

    def cancel_tasks(self,c,account,reason,status="cancelled"):
        c.execute("UPDATE am_tasks SET status=?,updated_at=?,reason=? WHERE account_id=? AND status IN ('scheduled','due')",(status,self.now(c),reason,account["id"]))

    def invalidate(self,c,account,reason,cancel=False):
        status="cancelled" if cancel else "readiness_review"
        if account["status"]=="cancelled":return
        if account["status"]==status and account["next_action"]==reason:return
        self.cancel_tasks(c,account,reason)
        c.execute("UPDATE am_accounts SET status=?,version=version+1,epoch=epoch+1,next_owner=?,next_action=?,updated_at=? WHERE id=?",(status,settings()["activation_owner"],reason,self.now(c),account["id"]))
        self.w._audit(c,"am_cancelled" if cancel else "am_readiness_reopened",account["lead_id"],account_id=account["id"],reason=reason,external_account_modified=False,pending_tasks_cancelled=True)

    def sync(self,c,lead_id=None):
        rows=c.execute("SELECT * FROM am_accounts WHERE status!='cancelled'"+(" AND lead_id=?" if lead_id else ""),(lead_id,) if lead_id else ()).fetchall()
        for row in rows:
            account=dict(row);lead=self.w._lead(c,account["lead_id"])
            reason=self.current(c,account)
            if lead["suppressed"]: self.invalidate(c,account,"Suppressed source contact; AM tasks cancelled",cancel=True)
            elif reason:self.invalidate(c,account,reason)
            elif account["status"]=="active":
                problems=self.readiness_problems(c,account,check_age=False)
                if problems:self.invalidate(c,account,"; ".join(problems))

    def start(self,lead_id):
        data=settings()
        with self.w.tx() as c:
            lead=self.w._lead(c,lead_id)
            existing=c.execute("SELECT id FROM am_accounts WHERE lead_id=?",(lead_id,)).fetchone()
            if existing:return self.state(c)
            if lead["suppressed"] or lead["stage"]!="handoff" or lead["score"]<80:
                raise ValueError("Activation intake requires an eligible, unsuppressed BD handoff")
            aid="ACC-"+sha(["single-local-demo",lead_id])[:16];now=self.now(c)
            c.execute("INSERT INTO am_accounts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,lead_id,lead["version"],1,"pending_activation",data["account_owner"],data["activation_owner"],"Collect signed intake, checklist and matching released sandbox evidence",None,None,sha(self.rules(data)),0,None,"unverified",now,now))
            self.w._audit(c,"am_activation_intake_created",lead_id,account_id=aid,owner=data["activation_owner"],next_owner=data["account_owner"],source_terms_version=self.w._get(c,"terms")["version"],synthetic=True)
            return self.state(c)

    def apply_fixture(self,account_id,fixture_id,event_id):
        data=settings();fixture=next((f for f in data["fixtures"] if f["id"]==fixture_id),None)
        if fixture is None:raise ValueError("Unknown allowlisted AM fixture")
        if not isinstance(event_id,str) or not 1<=len(event_id)<=200:raise ValueError("Stable AM event ID required")
        request=sha([account_id,fixture_id])
        with self.w.tx() as c:
            account=self.account(c,account_id)
            prior=c.execute("SELECT request_sha FROM am_events WHERE event_id=?",(event_id,)).fetchone()
            if prior:
                if prior[0]!=request:raise StaleAccountAction("AM event identity conflicts with its original payload")
                return self.state(c)
            if account["status"]=="cancelled":raise ValueError("Cancelled account cannot ingest new AM work")
            if self.w._lead(c,account["lead_id"])["suppressed"]:raise ValueError("Suppressed contact cannot ingest new AM work")
            facts={k:v for k,v in fixture.items() if k not in ("id","label","kind","age_hours")}
            facts["terms_version"]=self.w._get(c,"terms")["version"]
            if fixture["kind"]=="health":
                ready=self.evidence(c,account["readiness_sha"])
                facts["mapping_version"]=ready["facts"].get("mapping_version") if ready else None
                facts["activation_epoch"]=account["epoch"]
                facts["window_start"]=account["activated_at"]
                facts["window_end"]=(instant(self.now(c))-timedelta(hours=fixture["age_hours"])).isoformat()
                facts["window_semantics"]="Synthetic accepted observations in this activation epoch, through observed_at"
            payload={"account_id":account_id,"kind":fixture["kind"],"facts":facts,"observed_at":(instant(self.now(c))-timedelta(hours=fixture["age_hours"])).isoformat(),"label":"Synthetic fixture evidence; no external verification"}
            reference=sha(payload);column="readiness_sha" if fixture["kind"]=="readiness" else "health_sha"
            c.execute("INSERT INTO am_events VALUES(?,?,?,?)",(event_id,request,account_id,self.now(c)))
            if account[column]==reference:return self.state(c)
            c.execute("INSERT OR IGNORE INTO am_evidence VALUES(?,?,?,?,?,?)",(reference,account_id,fixture["kind"],fixture_id,encode(payload),self.now(c)))
            c.execute(f"UPDATE am_accounts SET {column}=?,version=version+1,updated_at=? WHERE id=?",(reference,self.now(c),account_id))
            account=self.account(c,account_id)
            self.w._audit(c,"am_fixture_evidence_received",account["lead_id"],account_id=account_id,fixture_id=fixture_id,evidence_sha256=reference,kind=fixture["kind"],trusted_as_instruction=False)
            if fixture["kind"]=="readiness":
                problems=self.readiness_problems(c,account)
                if account["status"]=="active":self.invalidate(c,account,"; ".join(problems) if problems else "Activation readiness evidence changed; owner reapproval required")
                elif account["status"]!="active":
                    c.execute("UPDATE am_accounts SET next_owner=?,next_action=?,rules_sha=?,lead_version=? WHERE id=?",(data["activation_owner"],"; ".join(problems) if problems else "Approve activation against current complete readiness",sha(self.rules(data)),self.w._lead(c,account["lead_id"])["version"],account_id))
            elif account["status"]=="active":self.evaluate(c,account)
            return self.state(c)

    def evaluate(self,c,account):
        data=settings();facts,problem=self.health_result(c,account)
        if problem:kind,owner,action="data_quality",data["integration_owner"],"Refresh evidence: "+problem
        elif facts["tracking_ok"] is False:kind,owner,action="tracking_issue",data["integration_owner"],"Investigate observed tracking check failure; return sandbox/readback evidence"
        elif facts["accepted_outcomes"]==0:kind,owner,action="low_activation",data["account_owner"],"Review activation with partner; no accepted outcome verified"
        else:kind,owner,action=None,data["account_owner"],"Verify accepted outcome and resolve owned issues using current evidence"
        if not kind and c.execute("SELECT 1 FROM am_issues WHERE account_id=? AND status='open'",(account["id"],)).fetchone():
            self.task(c,account,"issue_followthrough",data["issue_followup_hours"],owner)
        if kind:
            self.issue(c,account,kind,owner,action)
            self.task(c,account,"issue_followthrough",data["issue_followup_hours"],owner)
        c.execute("UPDATE am_accounts SET next_owner=?,next_action=?,updated_at=? WHERE id=?",(owner,action,self.now(c),account["id"]))

    def decide(self,account_id,expected_version,decision,note,evidence):
        if type(expected_version) is not int or expected_version<1:raise ValueError("Positive account version required")
        if decision not in ("approve_activation","verify_outcome","cancel"):raise ValueError("Unknown internal AM decision")
        if not all(isinstance(v,str) and 1<=len(v.strip())<=2000 for v in (note,evidence)):raise ValueError("Decision note and verification reference required")
        with self.w.tx() as c:
            account=self.account(c,account_id);data=settings()
            if account["version"]!=expected_version:raise StaleAccountAction("Account evidence/state changed; refresh before deciding")
            if account["status"]=="cancelled":raise StaleAccountAction("Account was cancelled; no automatic resumption")
            if decision=="cancel":
                reference=account["health_sha"] or account["readiness_sha"]
                self.invalidate(c,account,"Internal AM work cancelled by synthetic owner",cancel=True)
            else:
                reason=self.current(c,account)
                if reason:raise StaleAccountAction(reason)
                if decision=="approve_activation":
                    if account["status"]=="active":raise ValueError("Already activated; use the outcome review")
                    problems=self.readiness_problems(c,account)
                    if problems:raise ValueError("Activation blocked: "+"; ".join(problems))
                    reference=account["readiness_sha"]
                    self.cancel_tasks(c,account,"New activation epoch")
                    c.execute("UPDATE am_accounts SET status='active',epoch=epoch+1,version=version+1,activated_at=?,outcome_status='unverified',next_owner=?,next_action=?,updated_at=? WHERE id=?",(self.now(c),data["account_owner"],"Verify first accepted outcome; await fresh complete health evidence",self.now(c),account_id))
                    active=self.account(c,account_id)
                    self.task(c,active,"activation_followthrough",data["first_outcome_check_hours"],data["account_owner"])
                    self.task(c,active,"health_review",data["health_review_hours"],data["account_owner"])
                else:
                    if account["status"]!="active":raise ValueError("Outcome verification requires an activated account")
                    if self.readiness_problems(c,account,check_age=False):raise StaleAccountAction("Readiness changed; revalidation required")
                    facts,problem=self.health_result(c,account)
                    if problem or facts["accepted_outcomes"]<=0 or facts["tracking_ok"] is not True:raise ValueError(problem or "No healthy accepted outcome has been verified")
                    open_tracking=c.execute("SELECT 1 FROM am_issues WHERE account_id=? AND status='open' AND kind='tracking_issue'",(account_id,)).fetchone()
                    if open_tracking and not facts.get("repair_verified"):raise ValueError("Tracking issue needs current sandbox/readback repair evidence")
                    reference=account["health_sha"]
                    if c.execute("SELECT 1 FROM am_outcomes WHERE account_id=? AND kind='verify_outcome' AND evidence_sha=?",(account_id,reference)).fetchone():
                        return self.state(c)  # Same proof cannot postpone the next review or duplicate history.
                    self.cancel_tasks(c,account,"Outcome verified; next recurring review scheduled",status="completed")
                    c.execute("UPDATE am_issues SET status='resolved',updated_at=? WHERE account_id=? AND status='open'",(self.now(c),account_id))
                    c.execute("UPDATE am_accounts SET outcome_status='verified',version=version+1,next_owner=?,next_action='Await next recurring health review',updated_at=? WHERE id=?",(data["account_owner"],self.now(c),account_id))
                    self.task(c,self.account(c,account_id),"health_review",data["health_review_hours"],data["account_owner"])
            c.execute("INSERT INTO am_outcomes(account_id,account_version,kind,evidence_sha,note,verification,actor,created_at) VALUES(?,?,?,?,?,?,?,?)",(account_id,expected_version,decision,reference,note.strip(),evidence.strip(),"Synthetic local AM/onboarding reviewer",self.now(c)))
            self.w._audit(c,"am_owned_decision_recorded",account["lead_id"],account_id=account_id,decision=decision,bound_version=expected_version,evidence_sha256=reference,external_effect=False,automatic_dispatch_authority=False)
            return self.state(c)

    def check_due(self,c):
        self.sync(c)
        for row in c.execute("SELECT * FROM am_tasks WHERE status='scheduled'").fetchall():
            task=dict(row);account=self.account(c,task["account_id"])
            if account["status"]!="active" or task["epoch"]!=account["epoch"]:
                c.execute("UPDATE am_tasks SET status='cancelled',reason='Superseded activation or account',updated_at=? WHERE id=?",(self.now(c),task["id"]))
            elif instant(self.now(c))>=instant(task["due_at"]):
                c.execute("UPDATE am_tasks SET status='due',updated_at=? WHERE id=?",(self.now(c),task["id"]))
                c.execute("UPDATE am_accounts SET version=version+1 WHERE id=?",(account["id"],))
                self.evaluate(c,self.account(c,account["id"]))
                self.w._audit(c,"am_followthrough_due",account["lead_id"],account_id=account["id"],task_id=task["id"],kind=task["kind"],owner=task["owner"],external_effect=False)

    def state(self,c=None):
        if c is None:
            with self.w.db() as opened:return self.state(opened)
        data=settings();accounts=[dict(r) for r in c.execute("SELECT * FROM am_accounts ORDER BY created_at,id")]
        for account in accounts:
            account["readiness_problems"]=self.readiness_problems(c,account,check_age=account["status"]!="active")
            facts,problem=self.health_result(c,account)
            account["health"]={"status":"unknown" if problem else "observed", "reason":problem, "accepted_outcomes":None if problem else facts["accepted_outcomes"], "observed_at":(self.evidence(c,account["health_sha"]) or {}).get("observed_at")}
            outcome_problems=[]
            current_problem=self.current(c,account)
            if current_problem:outcome_problems.append(current_problem)
            if account["status"]!="active":outcome_problems.append("Account is not activated")
            if problem:outcome_problems.append(problem)
            elif facts["accepted_outcomes"]<=0 or facts["tracking_ok"] is not True:outcome_problems.append("Healthy accepted outcome is not verified")
            elif c.execute("SELECT 1 FROM am_issues WHERE account_id=? AND kind='tracking_issue' AND status='open'",(account["id"],)).fetchone() and not facts.get("repair_verified"):
                outcome_problems.append("Tracking issue needs sandbox/readback repair evidence")
            account["outcome_blockers"]=outcome_problems
            account["draft"]=None
            if account["status"]=="active" and not problem:
                account["draft"]={"mode":"deterministic template draft","dispatch_enabled":False,
                  "evidence_sha256":account["health_sha"],
                  "content":f"Hello, our synthetic account snapshot at {account['health']['observed_at']} records {facts['accepted_outcomes']} accepted demonstration outcomes. "
                    +( "A tracking check was reported unsuccessful; our integration owner is reviewing the evidence. " if facts["tracking_ok"] is False else "Could you confirm the next activation step or any issue needing our account manager? ")
                    +"These are synthetic fixture facts; this is an unsent demonstration check-in."}
            account["next_check_at"]=min((r[0] for r in c.execute("SELECT due_at FROM am_tasks WHERE account_id=? AND status IN ('scheduled','due')",(account["id"],))),default=None)
        evidence=[]
        for row in c.execute("SELECT * FROM am_evidence ORDER BY rowid"):
            item=dict(row);item["payload"]=json.loads(item["payload"]);evidence.append(item)
        return {"label":data["label"],"rules":self.rules(data),"fixtures":[{"id":f["id"],"label":f["label"],"kind":f["kind"]} for f in data["fixtures"]],"accounts":accounts,"evidence":evidence,
                "tasks":[dict(r) for r in c.execute("SELECT * FROM am_tasks ORDER BY created_at,id")],"issues":[dict(r) for r in c.execute("SELECT * FROM am_issues ORDER BY created_at,id")],"outcomes":[dict(r) for r in c.execute("SELECT * FROM am_outcomes ORDER BY id")],
                "effects":{"external_effects":False,"model_calls":0,"dispatch_enabled":False,"campaign_controls_enabled":False},
                "limitations":["Synthetic local reviewers are not production identity or signatory authority","Fixture signatures, tests and accepted counts are not real partner/provider evidence","Internal readiness review/cancellation changes no live platform account or traffic"]}
