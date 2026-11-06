"""Deterministic local workflow with a durable outbox and a SQLite mock transport.

Mock receipts participate in the local database transaction. That proves local
logical deduplication, not exactly-once delivery to an external provider. A live
adapter must separately implement provider idempotency/outcome reconciliation.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from .inference import TemplateInference
from .reconciliation import ReconciliationService, TABLES as RECON_TABLES, ensure_schema as ensure_recon_schema
from .account_management import AccountManagement, TABLES as AM_TABLES, ensure_schema as ensure_am_schema

from .commercial import CommercialService, TABLES as COMMERCIAL_TABLES, ensure_schema as ensure_commercial_schema

from .offer_v2 import OfferService, TABLES as OFFER_V2_TABLES, ensure_schema as ensure_offer_schema, ensure_seed as seed_offer

FIXTURE = Path(__file__).parent / "fixtures" / "generic.json"
PENDING = ("scheduled", "authorized", "executing")


def stamp(value):
    return value.astimezone(timezone.utc).isoformat()


def parse(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Timezone is required")
    return dt.astimezone(timezone.utc)


class Workflow:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.inference = TemplateInference()
        with self.db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS leads(
              id TEXT PRIMARY KEY, organization TEXT, contact TEXT, recipient TEXT UNIQUE,
              profile TEXT, source TEXT, score INTEGER, score_reasons TEXT,
              stage TEXT, owner TEXT, version INTEGER DEFAULT 1, replied INTEGER DEFAULT 0,
              suppressed INTEGER DEFAULT 0, rounds INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS provenance(
              source TEXT, external_id TEXT, lead_id TEXT, observed_at TEXT,
              attribution_method TEXT, PRIMARY KEY(source,external_id));
            CREATE TABLE IF NOT EXISTS inbox(event_id TEXT PRIMARY KEY, lead_id TEXT, received_at TEXT);
            CREATE TABLE IF NOT EXISTS actions(
              id TEXT PRIMARY KEY, logical_key TEXT UNIQUE, lead_id TEXT, kind TEXT,
              content TEXT, status TEXT, due_at TEXT, created_at TEXT, accepted_at TEXT,
              owner TEXT, mode TEXT, terms_version TEXT, policy_version TEXT,
              recipient TEXT, lead_version INTEGER, fact_refs TEXT,
              auth_binding TEXT, auth_expires_at TEXT, lease_owner TEXT, lease_until TEXT,
              attempts INTEGER DEFAULT 0, last_error TEXT);
            CREATE TABLE IF NOT EXISTS authorizations(
              id TEXT PRIMARY KEY, action_id TEXT, kind TEXT, binding TEXT, policy_version TEXT,
              expires_at TEXT, created_at TEXT, actor TEXT);
            CREATE TABLE IF NOT EXISTS attempts(
              id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT, attempt_number INTEGER,
              outcome TEXT, at TEXT, UNIQUE(action_id,attempt_number));
            CREATE TABLE IF NOT EXISTS receipts(action_id TEXT PRIMARY KEY, provider_id TEXT, accepted_at TEXT);
            CREATE TABLE IF NOT EXISTS messages(
              id TEXT PRIMARY KEY, lead_id TEXT, direction TEXT, text TEXT, at TEXT,
              action_id TEXT UNIQUE, mode TEXT);
            CREATE TABLE IF NOT EXISTS audit(
              id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, event TEXT,
              lead_id TEXT, action_id TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS issues(
              id TEXT PRIMARY KEY, lead_id TEXT, kind TEXT, summary TEXT,
              owner TEXT, status TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS draft_usage(
              cache_key TEXT PRIMARY KEY, lead_id TEXT, prompt_version TEXT,
              mode TEXT, content TEXT, created_at TEXT);
            """)
            ensure_recon_schema(c)
            ensure_am_schema(c)
            ensure_commercial_schema(c)
            ensure_offer_schema(c)
        if not self.setting("now"):
            self.reset()
        with self.tx() as c:
            seed_offer(c)

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=15000")
        try:
            yield c
        finally:
            c.close()

    @contextmanager
    def tx(self):
        with self.db() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
            except BaseException:
                c.rollback()
                raise
            else:
                c.commit()

    def _get(self, c, key):
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _set(self, c, key, value):
        c.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def setting(self, key):
        with self.db() as c:
            return self._get(c, key)

    def _audit(self, c, event, lead_id=None, action_id=None, **detail):
        c.execute("INSERT INTO audit(at,event,lead_id,action_id,detail) VALUES(?,?,?,?,?)", (
            self._get(c, "now"), event, lead_id, action_id, json.dumps(detail, sort_keys=True)))

    def _lead(self, c, lead_id):
        row = c.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            raise ValueError("Unknown lead")
        return dict(row)

    def reset(self):
        fixture = json.loads(FIXTURE.read_text())
        with self.tx() as c:
            for table in (*OFFER_V2_TABLES, *COMMERCIAL_TABLES, *AM_TABLES, *RECON_TABLES, "leads", "provenance", "inbox", "actions", "authorizations", "attempts", "receipts", "messages", "audit", "issues", "draft_usage", "settings"):
                c.execute(f"DELETE FROM {table}")  # table is a code-owned allowlist
            for key in ("now", "policy", "terms", "sources", "label"):
                self._set(c, key, fixture[key])
            self._set(c, "kill_switch", False)
            self._audit(c, "demo_reset", label=fixture["label"], live_effects=False)
            self._import(c, fixture["leads"])
            seed_offer(c)
        return self.state()

    def _import(self, c, rows):
        for source in rows:
            recipient = source["recipient"].strip().lower()
            if "@" not in recipient or not recipient.endswith(".example"):
                raise ValueError("Only synthetic .example recipients are accepted")
            if not all(isinstance(source.get(name, False), bool) for name in ("permitted", "fit_verified")):
                raise ValueError("Source permission and verified-fit flags must be boolean")
            normalized_payload = {
                "recipient": recipient,
                "organization": " ".join(source["organization"].split()).casefold(),
                "contact": " ".join(source["contact"].split()).casefold(),
                "profile": " ".join(source["profile"].split()).casefold(),
                "permitted": source.get("permitted", False),
                "fit_verified": source.get("fit_verified", False)
            }
            payload_hash = hashlib.sha256(json.dumps(normalized_payload, sort_keys=True).encode()).hexdigest()
            receipt_key = json.dumps([source["source"], source["external_id"]])
            receipts = self._get(c, "source_receipts") or {}
            original = c.execute("SELECT lead_id FROM provenance WHERE source=? AND external_id=?", (source["source"], source["external_id"])).fetchone()
            if original:
                original_lead = self._lead(c, original["lead_id"])
                receipt = receipts.get(receipt_key)
                if receipt and receipt["payload_hash"] == payload_hash and receipt["lead_id"] == original["lead_id"]:
                    self._audit(c, "source_event_replayed", original["lead_id"], source=source["source"],
                                external_id=source["external_id"], normalized_payload_sha256=payload_hash,
                                new_lead_created=False, canonical_record_changed=False)
                else:
                    # Source event identity is resolved before lead creation.
                    # Changed recipients/facts cannot silently reassign an
                    # immutable receipt or create an orphan lead. A legacy
                    # receipt lacking a digest is also an explicit review case.
                    self._cancel_pending(c, original["lead_id"], "source_event_conflict")
                    self._issue(c, original_lead, "source_event_conflict",
                                f"Source event {source['source']}/{source['external_id']} changed or has no verifiable payload receipt; preserve the original record and review source correction")
                    self._audit(c, "source_event_conflict", original["lead_id"], source=source["source"],
                                external_id=source["external_id"], normalized_payload_sha256=payload_hash,
                                original_payload_sha256=receipt["payload_hash"] if receipt else None,
                                legacy_receipt_unverified=receipt is None, new_lead_created=False,
                                original_mapping_preserved=True)
                continue
            existing = c.execute("SELECT id FROM leads WHERE recipient=?", (recipient,)).fetchone()
            lead_id = existing[0] if existing else source["id"]
            if not existing:
                reasons = {"permitted_source": 40 if source.get("permitted") else 0,
                           "complete_business_contact": 30,
                           "fixture_fit_verified": 30 if source.get("fit_verified") else 0}
                score = sum(reasons.values())
                c.execute("""INSERT INTO leads(id,organization,contact,recipient,profile,source,score,score_reasons,stage,owner)
                          VALUES(?,?,?,?,?,?,?,?,?,?)""", (lead_id, source["organization"], source["contact"], recipient,
                          source["profile"], source["source"], score, json.dumps(reasons),
                          "qualified" if score >= 80 else "needs_qualification", "Demo BD owner"))
            c.execute("INSERT INTO provenance VALUES(?,?,?,?,?)", (source["source"], source["external_id"], lead_id, self._get(c, "now"), "supplied source ID"))
            receipts[receipt_key] = {"lead_id": lead_id, "payload_hash": payload_hash}
            self._set(c, "source_receipts", receipts)
            self._audit(c, "lead_deduplicated" if existing else "lead_imported", lead_id, source=source["source"], external_id=source["external_id"], normalized_payload_sha256=payload_hash)

    def import_leads(self, rows):
        with self.tx() as c:
            self._import(c, rows)
        return self.state()

    def _new_action(self, c, lead, kind, content, logical_key, due_at=None, fact_refs=None):
        terms, policy = self._get(c, "terms"), self._get(c, "policy")
        action_id = "ACT-" + hashlib.sha256(logical_key.encode()).hexdigest()[:16]
        c.execute("""INSERT OR IGNORE INTO actions(id,logical_key,lead_id,kind,content,status,due_at,created_at,owner,
          mode,terms_version,policy_version,recipient,lead_version,fact_refs)
          VALUES(?,?,?,?,?,'scheduled',?,?,?,?,?,?,?,?,?)""", (
            action_id, logical_key, lead["id"], kind, content, due_at or self._get(c, "now"), self._get(c, "now"),
            lead["owner"], "mock adapter", terms["version"], policy["version"], lead["recipient"], lead["version"],
            json.dumps(fact_refs or [terms["version"]])))
        return action_id

    def draft(self, lead_id):
        with self.tx() as c:
            lead = self._lead(c, lead_id)
            if lead["suppressed"] or lead["stage"] in ("handoff", "review") or lead["replied"]:
                raise ValueError("Lead is suppressed, replied, or owned by a human; no new outreach")
            if lead["score"] < 80:
                self._issue(c, lead, "qualification", "Qualification evidence is incomplete; confirm fit before contact")
            else:
                terms, policy = self._get(c, "terms"), self._get(c, "policy")
                baseline = TemplateInference().draft(lead, terms, policy)
                try:
                    if getattr(self.inference, "mode", None) != "template-fixture":
                        raise PermissionError("Live adapter disabled until approved budget, usage accounting and task evaluation exist")
                    result = self.inference.draft(lead, terms, policy)
                    valid = (isinstance(result, dict) and result == baseline)
                except (TypeError, ValueError, TimeoutError, PermissionError):
                    result, valid = None, False
                if not valid:
                    # No live inference implementation exists. A future adapter
                    # cannot bypass this conservative approved-content boundary.
                    result = baseline
                    self._audit(c, "inference_output_rejected_template_fallback", lead_id,
                                mode="template-fixture", live_model=False)
                cached = c.execute("SELECT 1 FROM draft_usage WHERE cache_key=?", (result["cache_key"],)).fetchone() is not None
                c.execute("INSERT OR IGNORE INTO draft_usage VALUES(?,?,?,?,?,?)", (result["cache_key"], lead_id, TemplateInference.prompt_version, result["mode"], result["content"], self._get(c, "now")))
                aid = self._new_action(c, lead, "outreach", result["content"],
                                       f"outreach:{lead_id}:{lead['version']}:{terms['version']}:{policy['version']}",
                                       fact_refs=result["fact_refs"])
                c.execute("UPDATE leads SET stage='drafted' WHERE id=? AND stage IN ('qualified','drafted')", (lead_id,))
                self._audit(c, "draft_created", lead_id, aid, mode=result["mode"], cache_hit=cached, cache_key=result["cache_key"], provider_attempts=0, cost_usd="0.00")
        return self.state()

    def _binding(self, action, lead, policy, terms):
        return hashlib.sha256(json.dumps({
            "target": lead["id"], "recipient": lead["recipient"], "content": action["content"],
            "terms": terms["version"], "policy": policy["version"], "policy_expiry": policy["expires_at"],
            "lead_version": lead["version"], "offer": terms["offer_id"], "kind": action["kind"],
            "action_id": action["id"]}, sort_keys=True).encode()).hexdigest()

    def _check(self, c, action, check_binding=False):
        lead = self._lead(c, action["lead_id"])
        policy, terms, now = self._get(c, "policy"), self._get(c, "terms"), self._get(c, "now")
        if self._get(c, "kill_switch"):
            return "kill_switch"
        if not policy["enabled"] or parse(now) >= parse(policy["expires_at"]):
            return "policy_disabled_or_expired"
        if policy["scope"] != "mock-only" or lead["id"] not in policy["eligible_leads"] or action["kind"] not in policy["allowed_actions"]:
            return "outside_policy_scope"
        if lead["suppressed"] or lead["stage"] in ("handoff", "review") or lead["score"] < 80:
            return "suppressed_handoff_or_unqualified"
        if action["recipient"] != lead["recipient"] or action["lead_version"] != lead["version"]:
            return "lead_or_recipient_changed"
        if action["terms_version"] != terms["version"] or action["policy_version"] != policy["version"]:
            return "terms_or_policy_changed"
        if action["kind"] in ("outreach", "followup") and lead["replied"]:
            return "reply_already_persisted"
        if action["kind"] == "outreach" and c.execute("SELECT 1 FROM receipts r JOIN actions a ON r.action_id=a.id WHERE a.lead_id=? AND a.kind='outreach' AND a.id!=?", (lead["id"], action["id"])).fetchone():
            return "outreach_frequency_limit"
        if action["kind"] == "standard_response" and lead["rounds"] >= policy["max_standard_rounds"]:
            return "reply_round_limit"
        if check_binding and (action["auth_binding"] != self._binding(action, lead, policy, terms)
                              or not action["auth_expires_at"] or parse(now) >= parse(action["auth_expires_at"])):
            return "authorization_invalidated"
        return None

    def _authorize(self, c, aid):
        action = dict(c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone())
        reason = self._check(c, action)
        if reason:
            self._cancel(c, action, reason)
            return False
        if action["status"] not in ("scheduled", "authorized"):
            return False
        lead, policy, terms = self._lead(c, action["lead_id"]), self._get(c, "policy"), self._get(c, "terms")
        binding = self._binding(action, lead, policy, terms)
        expiry = min(parse(policy["expires_at"]), parse(self._get(c, "now")) + timedelta(hours=24))
        c.execute("UPDATE actions SET status='authorized',auth_binding=?,auth_expires_at=? WHERE id=?", (binding, stamp(expiry), aid))
        c.execute("INSERT INTO authorizations VALUES(?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), aid, "delegated_policy", binding,
                    policy["version"], stamp(expiry), self._get(c, "now"), policy["owner"]))
        self._audit(c, "delegated_policy_authorized", lead["id"], aid, binding=binding, policy=policy["version"], expiry=stamp(expiry), synthetic=True)
        return True

    def _cancel(self, c, action, reason):
        c.execute("UPDATE actions SET status='cancelled',last_error=? WHERE id=? AND status IN ('scheduled','authorized','executing')", (reason, action["id"]))
        self._audit(c, "action_cancelled", action["lead_id"], action["id"], reason=reason)

    def dispatch(self, lead_id, transport_result="accepted"):
        with self.tx() as c:
            self._lead(c, lead_id)
            row = c.execute("SELECT * FROM actions WHERE lead_id=? AND kind='outreach' ORDER BY created_at DESC, rowid DESC LIMIT 1", (lead_id,)).fetchone()
            if not row:
                raise ValueError("Create an outreach draft first")
            aid = row["id"]
            if row["status"] in ("succeeded", "cancelled", "unknown_outcome", "failed", "executing"):
                return self._state(c)
            self._authorize(c, aid)
        self.run_action(aid, transport_result=transport_result)
        return self.state()

    def run_action(self, aid, *, transport_result="accepted", before_execute=None):
        if transport_result not in ("accepted", "transient_before_accept", "timeout_after_accept"):
            raise ValueError("Unknown mock fault")
        worker_id = str(uuid.uuid4())
        with self.tx() as c:
            row = c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone()
            if not row or row["status"] != "authorized" or parse(row["due_at"]) > parse(self._get(c, "now")):
                return False
            action = dict(row)
            reason = self._check(c, action, check_binding=True)
            if reason:
                self._cancel(c, action, reason)
                return False
            c.execute("UPDATE actions SET status='executing',lease_owner=?,lease_until=? WHERE id=? AND status='authorized'", (
                worker_id, stamp(parse(self._get(c, "now")) + timedelta(minutes=1)), aid))
            self._audit(c, "worker_claimed", action["lead_id"], aid, worker=worker_id)
        if before_execute:
            before_execute()
        with self.tx() as c:
            action = dict(c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone())
            if action["status"] != "executing" or action["lease_owner"] != worker_id:
                return False
            reason = self._check(c, action, check_binding=True)
            if reason:
                self._cancel(c, action, reason)
                return False
            attempt = action["attempts"] + 1
            limit = self._get(c, "policy")["max_transport_attempts"]
            if attempt > limit:
                c.execute("UPDATE actions SET status='failed',last_error='attempt_cap' WHERE id=?", (aid,))
                return False
            c.execute("UPDATE actions SET attempts=? WHERE id=?", (attempt, aid))
            c.execute("INSERT INTO attempts(action_id,attempt_number,outcome,at) VALUES(?,?,?,?)", (aid, attempt, transport_result, self._get(c, "now")))
            if transport_result == "transient_before_accept":
                final = attempt >= limit
                c.execute("UPDATE actions SET status=?,last_error='known_pre_accept_failure',due_at=? WHERE id=?", (
                    "failed" if final else "scheduled", stamp(parse(self._get(c, "now")) + timedelta(hours=1)), aid))
                self._audit(c, "transport_failed_before_acceptance", action["lead_id"], aid, attempt=attempt, retry_allowed=not final)
                if final:
                    self._issue(c, self._lead(c, action["lead_id"]), "transport_failure", "Finite mock transport retries exhausted")
                return False
            c.execute("INSERT OR IGNORE INTO receipts VALUES(?,?,?)", (aid, "MOCK-" + aid, self._get(c, "now")))
            if transport_result == "timeout_after_accept":
                c.execute("UPDATE actions SET status='unknown_outcome',last_error='possible_provider_acceptance' WHERE id=?", (aid,))
                self._audit(c, "outcome_unknown_quarantined", action["lead_id"], aid, blind_retry=False)
                self._issue(c, self._lead(c, action["lead_id"]), "unknown_outcome", "Mock accepted before timeout; reconcile receipt before any retry", change_stage=False)
                return False
            self._succeed(c, action)
            return True

    def _succeed(self, c, action):
        receipt = c.execute("SELECT * FROM receipts WHERE action_id=?", (action["id"],)).fetchone()
        c.execute("UPDATE actions SET status='succeeded',accepted_at=?,last_error=NULL WHERE id=?", (receipt["accepted_at"], action["id"]))
        c.execute("INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?)", ("MSG-" + action["id"], action["lead_id"], "outbound", action["content"], receipt["accepted_at"], action["id"], "template-fixture / mock adapter"))
        if action["kind"] == "standard_response":
            c.execute("UPDATE leads SET stage='conversation',rounds=rounds+1 WHERE id=?", (action["lead_id"],))
        elif action["kind"] == "outreach":
            # Acceptance may be reconciled after an inbound reply was committed.
            # Preserve the newer conversation/owner state as well as skipping follow-up.
            c.execute("UPDATE leads SET stage='contacted' WHERE id=? AND replied=0 AND stage NOT IN ('handoff','review','suppressed')", (action["lead_id"],))
            lead = self._lead(c, action["lead_id"])
            if not lead["replied"] and not lead["suppressed"] and lead["stage"] not in ("handoff", "review"):
                due = stamp(parse(receipt["accepted_at"]) + timedelta(hours=self._get(c, "policy")["followup_hours"]))
                self._new_action(c, lead, "followup", f"Hi {lead['contact']}, following up on our affiliate partnership introduction. Would a conversation be useful? Reply 'unsubscribe' to stop.", f"followup:{action['id']}", due)
                self._audit(c, "followup_scheduled", action["lead_id"], action["id"], due_at=due, basis="Elapsed hours from provider acceptance; proposed unconfirmed business rule", followup_hours=self._get(c, "policy")["followup_hours"])
        self._audit(c, "mock_dispatch_succeeded", action["lead_id"], action["id"], provider_id=receipt["provider_id"], accepted_at=receipt["accepted_at"], external_effect=False)

    def reconcile(self, aid):
        with self.tx() as c:
            row = c.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone()
            if not row:
                raise ValueError("Unknown action")
            if row["status"] == "unknown_outcome":
                if c.execute("SELECT 1 FROM receipts WHERE action_id=?", (aid,)).fetchone():
                    self._succeed(c, dict(row))
                    c.execute("UPDATE issues SET status='resolved' WHERE lead_id=? AND kind='unknown_outcome'", (row["lead_id"],))
                    self._audit(c, "mock_outcome_reconciled", row["lead_id"], aid, evidence="Durable mock provider receipt; live lookup contract still unverified")
                else:
                    self._audit(c, "outcome_still_unknown", row["lead_id"], aid, human_resolution_required=True)
        return self.state()

    def _issue(self, c, lead, kind, summary, change_stage=True):
        issue_id = "ISS-" + hashlib.sha256((lead["id"] + kind + summary).encode()).hexdigest()[:12]
        c.execute("INSERT INTO issues VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status='open'", (issue_id, lead["id"], kind, summary, lead["owner"], "open", self._get(c, "now")))
        if change_stage:
            c.execute("UPDATE leads SET stage=? WHERE id=?", ("handoff" if kind in ("interest", "human_requested", "round_limit") else "review", lead["id"]))
        self._audit(c, "owned_issue_opened", lead["id"], kind=kind, owner=lead["owner"], summary=summary)

    def _cancel_pending(self, c, lead_id, reason):
        rows = c.execute("SELECT * FROM actions WHERE lead_id=? AND status IN ('scheduled','authorized','executing')", (lead_id,)).fetchall()
        for row in rows:
            self._cancel(c, dict(row), reason)

    def reply(self, lead_id, text, event_id):
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise ValueError("Reply must contain 1–16000 characters")
        if not event_id or len(event_id) > 200:
            raise ValueError("Stable event ID required")
        response_id = None
        with self.tx() as c:
            lead = self._lead(c, lead_id)
            existing = c.execute("SELECT lead_id FROM inbox WHERE event_id=?", (event_id,)).fetchone()
            if existing:
                if existing[0] != lead_id:
                    raise ValueError("Event ID belongs to another lead")
                return self._state(c)
            c.execute("INSERT INTO inbox VALUES(?,?,?)", (event_id, lead_id, self._get(c, "now")))
            c.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?)", ("IN-" + event_id, lead_id, "inbound", text, self._get(c, "now"), None, "synthetic injected reply"))
            c.execute("UPDATE leads SET replied=1 WHERE id=?", (lead_id,))
            self._cancel_pending(c, lead_id, "reply_persisted")
            normalized = text.strip().lower().rstrip("?.!")
            self._audit(c, "inbound_received", lead_id, event_id=event_id, trusted_as_instruction=False)
            if lead["suppressed"]:
                self._audit(c, "suppression_preserved", lead_id)
            elif normalized in ("unsubscribe", "stop", "stop contacting me", "do not contact me", "not interested"):
                c.execute("UPDATE leads SET suppressed=1,stage='suppressed' WHERE id=?", (lead_id,))
                self._audit(c, "opt_out_suppressed", lead_id)
            elif normalized in ("i am interested", "interested", "let's talk", "lets talk", "please arrange a meeting"):
                self._issue(c, lead, "interest", "Clear interest: human BD owns discovery and final negotiation")
            elif "human" in normalized or normalized == "call me":
                self._issue(c, lead, "human_requested", "Partner requested human ownership")
            elif lead["stage"] in ("handoff", "review"):
                self._audit(c, "human_ownership_preserved", lead_id)
            elif lead["rounds"] >= self._get(c, "policy")["max_standard_rounds"]:
                self._issue(c, lead, "round_limit", "Configured standard-response limit reached; human takes next round")
            else:
                terms = self._get(c, "terms")
                answers = {
                    "what is the payout": f"The synthetic approved payout is {terms['currency']} {terms['payout']} per {terms['billable_event']}. This is a demonstration, not a commercial commitment.",
                    "payout": f"The synthetic approved payout is {terms['currency']} {terms['payout']} per {terms['billable_event']}. This is a demonstration, not a commercial commitment.",
                    "what are the settlement terms": f"Synthetic approved settlement: {terms['settlement']}. Any change requires the commercial owner.",
                    "settlement": f"Synthetic approved settlement: {terms['settlement']}. Any change requires the commercial owner.",
                    "what traffic is allowed": f"Synthetic approved traffic rule: {terms['traffic']}. Unverified sources require review.",
                    "traffic": f"Synthetic approved traffic rule: {terms['traffic']}. Unverified sources require review."
                }
                if normalized in answers:
                    response_id = self._new_action(c, self._lead(c, lead_id), "standard_response", answers[normalized], f"response:{event_id}")
                    self._authorize(c, response_id)
                    self._audit(c, "standard_terms_rendered", lead_id, response_id, terms_version=terms["version"], mode="deterministic approved structured facts")
                else:
                    self._issue(c, lead, "ambiguous_or_out_of_policy", "Free-text request needs review; no inferred consent, commercial term or operational permission")
            AccountManagement(self).sync(c, lead_id)
        if response_id:
            self.run_action(response_id)
        return self.state()

    def tick(self, advance_hours=0):
        if isinstance(advance_hours, bool) or not isinstance(advance_hours, (int, float)) or advance_hours < 0 or advance_hours > 24 * 365:
            raise ValueError("advance_hours must be 0–8760")
        with self.tx() as c:
            now = stamp(parse(self._get(c, "now")) + timedelta(hours=advance_hours))
            self._set(c, "now", now)
            # A crash between claim and finish cannot establish external failure.
            abandoned = c.execute("SELECT * FROM actions WHERE status='executing' AND lease_until<=?", (now,)).fetchall()
            for row in abandoned:
                c.execute("UPDATE actions SET status='unknown_outcome',last_error='expired_claim_requires_reconciliation' WHERE id=?", (row["id"],))
                self._audit(c, "expired_claim_quarantined", row["lead_id"], row["id"], blind_retry=False)
            due = c.execute("SELECT id FROM actions WHERE status IN ('scheduled','authorized') AND due_at<=? ORDER BY due_at,id", (now,)).fetchall()
            aids = []
            for row in due:
                # Outreach is explicitly dispatched by the demo operator. The
                # durable worker handles only scheduled follow-ups and retries.
                action = c.execute("SELECT * FROM actions WHERE id=?", (row["id"],)).fetchone()
                if action["kind"] == "outreach" and not action["attempts"]:
                    continue
                if self._authorize(c, row["id"]):
                    aids.append(row["id"])
            ReconciliationService(self).check_due(c)
            AccountManagement(self).check_due(c)
            self._audit(c, "scheduler_tick", due_actions=len(aids), advance_hours=advance_hours)
        for aid in aids:
            self.run_action(aid)
        return self.state()

    def edit(self, lead_id, *, recipient=None, content=None):
        if recipient is not None:
            recipient = recipient.strip().lower()
            if "@" not in recipient or not recipient.endswith(".example"):
                raise ValueError("Only synthetic .example recipients are accepted")
        with self.tx() as c:
            self._lead(c, lead_id)
            self._cancel_pending(c, lead_id, "material_edit_invalidates_authorization")
            c.execute("UPDATE leads SET version=version+1 WHERE id=?", (lead_id,))
            if recipient is not None:
                c.execute("UPDATE leads SET recipient=? WHERE id=?", (recipient, lead_id))
            # Free edits are not automatically authorized. Content is retained
            # as a review note rather than sent from a mutable draft.
            if content is not None:
                self._issue(c, self._lead(c, lead_id), "edited_content", "Free-text draft edit requires human review; it will not auto-dispatch")
            AccountManagement(self).sync(c, lead_id)
            self._audit(c, "lead_edited", lead_id, recipient_changed=recipient is not None, free_text_changed=content is not None)
        return self.state()

    def change_policy(self, *, enabled=None, expires_at=None, kill_switch=None):
        with self.tx() as c:
            policy = self._get(c, "policy")
            if enabled is not None:
                if not isinstance(enabled, bool):
                    raise ValueError("enabled must be boolean")
                policy["enabled"] = enabled
            if expires_at is not None:
                if not isinstance(expires_at, str):
                    raise ValueError("expires_at must be a timezone-qualified ISO string")
                parse(expires_at)
                policy["expires_at"] = expires_at
            policy["version"] = "synthetic-policy-" + str(uuid.uuid4())[:8]
            self._set(c, "policy", policy)
            if kill_switch is not None:
                if not isinstance(kill_switch, bool):
                    raise ValueError("kill_switch must be boolean")
                self._set(c, "kill_switch", kill_switch)
            rows = c.execute("SELECT * FROM actions WHERE status IN ('scheduled','authorized','executing')").fetchall()
            for row in rows:
                self._cancel(c, dict(row), "policy_changed_or_revoked")
            self._audit(c, "synthetic_policy_changed", owner=policy["owner"], enabled=policy["enabled"], kill_switch=self._get(c, "kill_switch"))
        return self.state()

    def change_terms(self, payout):
        value = Decimal(payout)
        if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2:
            raise ValueError("Positive exact monetary amount with at most two decimal places required")
        with self.tx() as c:
            terms = self._get(c, "terms")
            terms["payout"] = str(value)
            terms["version"] = "synthetic-terms-" + str(uuid.uuid4())[:8]
            self._set(c, "terms", terms)
            for row in c.execute("SELECT * FROM actions WHERE status IN ('scheduled','authorized','executing')").fetchall():
                self._cancel(c, dict(row), "terms_version_changed")
            AccountManagement(self).sync(c)
            self._audit(c, "synthetic_terms_changed", terms_version=terms["version"], no_live_authority=True)
        return self.state()

    def resolve_issue(self, issue_id, resolution, evidence):
        if not all(isinstance(v, str) and 1 <= len(v.strip()) <= 2000 for v in (resolution, evidence)):
            raise ValueError("Resolution and verification evidence must contain 1–2000 characters each")
        with self.tx() as c:
            row = c.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
            if not row:
                raise ValueError("Unknown issue")
            if row["status"] == "resolved":
                return self._state(c)
            c.execute("UPDATE issues SET status='resolved' WHERE id=?", (issue_id,))
            self._audit(c, "owned_issue_resolved", row["lead_id"], issue_id=issue_id,
                        owner=row["owner"], resolution=resolution, verification_evidence=evidence,
                        actor="Synthetic local operator", automatic_authority_restored=False,
                        external_effect=False)
            # Closing an issue is not permission to resume contact or change
            # commercial policy. Handoff/review and suppression remain intact.
        return self.state()

    def state(self):
        with self.db() as c:
            return self._state(c)

    def _state(self, c):
        def rows(table, order="rowid"):
            return [dict(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY {order}")]
        leads = rows("leads")
        actions = rows("actions")
        provenance = rows("provenance")
        for lead in leads:
            lead["score_reasons"] = json.loads(lead["score_reasons"])
            lead["provenance"] = [p for p in provenance if p["lead_id"] == lead["id"]]
            lead["qualification"] = "eligible" if lead["score"] >= 80 else "needs_review"
        for action in actions:
            action["fact_refs"] = json.loads(action["fact_refs"])
        audit = rows("audit")
        for event in audit:
            event["detail"] = json.loads(event["detail"])
        contacted_ids = {a["lead_id"] for a in actions if a["status"] == "succeeded" and a["kind"] == "outreach"}
        accepted = len(contacted_ids)
        contacted_replies = sum(bool(l["replied"]) and l["id"] in contacted_ids for l in leads)
        cohorts = []
        for src in self._get(c, "sources"):
            members = [l for l in leads if l["source"] == src["id"]]
            cohorts.append({"source": src["id"], "lead_count": len(members), "qualified": sum(l["score"] >= 80 for l in members),
                            "contacted": sum(any(a["lead_id"] == l["id"] and a["kind"] == "outreach" and a["status"] == "succeeded" for a in actions) for l in members),
                            "replied": sum(l["replied"] for l in members), "handoffs": sum(l["stage"] == "handoff" for l in members),
                            "buyer_accepted": None, "billable_outcomes": None, "revenue_usd": None, "contribution_usd": None,
                            "attribution_method": "first supplied source, observational; secondary provenance retained", "synthetic": True})
        return {
            "now": self._get(c, "now"), "label": self._get(c, "label"),
            "mode": {"workflow": "deterministic", "inference": "template-fixture", "transport": "mock adapter", "everflow": "not connected", "live_effects": False},
            "policy": self._get(c, "policy"), "terms": self._get(c, "terms"), "kill_switch": self._get(c, "kill_switch"),
            "leads": leads, "actions": actions, "messages": rows("messages"), "audit": audit,
            "issues": rows("issues"), "authorizations": rows("authorizations"), "attempts": rows("attempts"),
            "reconciliation": ReconciliationService(self).state(c),
            "account_management": AccountManagement(self).state(c),
            "commercial": CommercialService(self).state(c),
            "offer_v2": OfferService(self).state(c),
            "metrics": {"leads": len(leads), "qualified": sum(l["score"] >= 80 for l in leads),
                        "outreach_accepted": accepted, "replies": sum(l["replied"] for l in leads),
                        "replies_after_accepted_outreach": contacted_replies,
                        "reply_rate": contacted_replies / accepted if accepted else None,
                        "reply_rate_denominator": "unique leads with accepted mock outreach; numerator is the replied subset of those same leads",
                        "handoffs": sum(l["stage"] == "handoff" for l in leads), "source_cohorts": cohorts,
                        "window": "since synthetic reset, fake UTC clock", "freshness": self._get(c, "now"),
                        "unknown_costs_are_zero": False, "spend": None},
            "cost": {"provider": None, "model": None, "provider_attempts": 0, "input_tokens": 0, "output_tokens": 0,
                     "estimated_usd": "0.00", "actual_model_usd": "0.00", "paid_calls_enabled": False,
                     "hosting_usd": None, "human_review_usd": None, "reason": "No live inference adapter or approved price/budget; template mode only"},
            "limitations": ["Single-user loopback demo; production identity/tenant controls are not implemented",
                             "SQLite mock receipts prove only local logical deduplication, not external exactly-once delivery",
                             "Only persisted replies can cancel actions; external ingestion latency remains unmeasured",
                             "Narrow deterministic FAQ fixtures route other language to an owned review case"]
        }
