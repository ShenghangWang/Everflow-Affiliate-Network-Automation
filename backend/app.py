"""FastAPI surface for the loopback-only, synthetic prototype."""
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .domain import Workflow
from .scenarios import scenario
from .reconciliation import ReconciliationService, StaleReconciliation
from .account_management import AccountManagement, StaleAccountAction

from .commercial import CommercialService

from .offer_v2 import OfferService, StaleOfferAction
from .offer_followthrough import OfferFollowthrough

ROOT = Path(__file__).resolve().parents[1]
workflow = Workflow(os.environ.get("EVERFLOW_DEMO_DB", str(ROOT / "data" / "demo.sqlite3")))
app = FastAPI(title="Affiliate Network Foundation — synthetic local demo", docs_url="/api/docs")


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    host = request.url.hostname
    if host not in ("127.0.0.1", "localhost", "testserver", "::1"):
        return JSONResponse({"detail": "This demo accepts loopback hosts only"}, status_code=403)
    origin = request.headers.get("origin")
    # Accept the actual loopback server origin, including an explicit demo port.
    # Vite is the only cross-origin development exception; other ports stay blocked.
    if origin and request.method not in ("GET", "HEAD", "OPTIONS"):
        try:
            parsed = urlsplit(origin)
            clean = not (parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment)
            same_origin = (parsed.scheme == request.url.scheme == "http" and parsed.hostname == host
                           and (parsed.port or 80) == (request.url.port or 80))
            vite_origin = (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
                           and parsed.port == 5173)
            permitted = clean and (same_origin or vite_origin)
        except ValueError:
            permitted = False
        if not permitted:
            return JSONResponse({"detail": "Cross-origin mutation rejected"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response


@app.exception_handler(StaleOfferAction)
async def stale_offer_action(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(StaleAccountAction)
async def stale_account_action(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(StaleReconciliation)
async def stale_reconciliation(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(ValueError)
async def value_error(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(sqlite3.IntegrityError)
async def record_conflict(_request, _exc):
    return JSONResponse({"detail": "Conflicting synthetic record; preserve the existing record and review the edit"}, status_code=409)


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "synthetic-mock", "live_effects": False}


@app.get("/api/state")
def state():
    return workflow.state()


@app.post("/api/reset")
def reset():
    return workflow.reset()


@app.post("/api/leads/{lead_id}/draft")
def draft(lead_id: str):
    return workflow.draft(lead_id)


@app.post("/api/leads/{lead_id}/dispatch")
def dispatch(lead_id: str):
    return workflow.dispatch(lead_id)


@app.post("/api/leads/{lead_id}/reply")
def reply(lead_id: str, payload: dict = Body(...)):
    if set(payload) != {"text", "event_id"} or not all(isinstance(payload[k], str) for k in payload):
        raise ValueError("Reply requires exactly text and event_id strings")
    return workflow.reply(lead_id, payload["text"], payload["event_id"])


@app.post("/api/tick")
def tick(payload: dict = Body(default={})):
    if set(payload) - {"advance_hours"}:
        raise ValueError("Unknown clock setting")
    return workflow.tick(payload.get("advance_hours", 0))


@app.post("/api/leads/{lead_id}/edit")
def edit(lead_id: str, payload: dict = Body(...)):
    if set(payload) - {"recipient", "content"} or not payload or not all(isinstance(v, str) for v in payload.values()):
        raise ValueError("Edit accepts recipient/content strings only")
    return workflow.edit(lead_id, **payload)


@app.post("/api/policy")
def policy(payload: dict = Body(...)):
    if set(payload) - {"enabled", "expires_at", "kill_switch"} or not payload:
        raise ValueError("Only synthetic policy enable/expiry/kill-switch settings are exposed")
    return workflow.change_policy(**payload)


@app.post("/api/actions/{action_id}/reconcile")
def reconcile(action_id: str):
    return workflow.reconcile(action_id)


@app.post("/api/issues/{issue_id}/resolve")
def resolve_issue(issue_id: str, payload: dict = Body(...)):
    if set(payload) != {"resolution", "evidence"}:
        raise ValueError("Closing an internal case requires resolution and verification evidence")
    return workflow.resolve_issue(issue_id, payload["resolution"], payload["evidence"])


@app.get("/api/scenario")
def scenario_defaults():
    return scenario()


@app.post("/api/scenario")
def scenario_calculate(payload: dict = Body(default={})):
    return scenario(payload)



@app.get("/api/reconciliation")
def reconciliation_state():
    return ReconciliationService(workflow).state()


@app.post("/api/reconciliation/compare")
def reconciliation_compare(payload: dict = Body(...)):
    if set(payload) != {"fixture_id"} or not isinstance(payload["fixture_id"], str):
        raise ValueError("Select exactly one allowlisted synthetic fixture_id")
    return ReconciliationService(workflow).compare_fixture(payload["fixture_id"])


@app.post("/api/reconciliation/cases/{case_id}/decision")
def reconciliation_decision(case_id: str, payload: dict = Body(...)):
    if set(payload) != {"expected_run_id", "expected_version", "decision", "note", "evidence"}:
        raise ValueError("Finance review requires exact current run/version, decision, note and evidence")
    return ReconciliationService(workflow).decide(case_id, **payload)



@app.get("/api/am")
def account_management_state():
    return AccountManagement(workflow).state()


@app.post("/api/am/start")
def account_management_start(payload: dict = Body(...)):
    if set(payload) != {"lead_id"} or not isinstance(payload["lead_id"], str):
        raise ValueError("Activation intake requires exactly one handed-off lead_id")
    return AccountManagement(workflow).start(payload["lead_id"])


@app.post("/api/am/accounts/{account_id}/fixture")
def account_management_fixture(account_id: str, payload: dict = Body(...)):
    if set(payload) != {"fixture_id", "event_id"} or not all(isinstance(v, str) for v in payload.values()):
        raise ValueError("Choose an allowlisted fixture and stable event_id; no authority fields accepted")
    return AccountManagement(workflow).apply_fixture(account_id, **payload)


@app.post("/api/am/accounts/{account_id}/decision")
def account_management_decision(account_id: str, payload: dict = Body(...)):
    if set(payload) != {"expected_version", "decision", "note", "evidence"}:
        raise ValueError("AM decision requires current version, decision, note and verification evidence")
    return AccountManagement(workflow).decide(account_id, **payload)


@app.post("/api/leads/{lead_id}/proposal")
def prepare_proposal(lead_id: str, payload: dict = Body(...)):
    if set(payload) != {"meeting_note", "event_id"}:
        raise ValueError("Proposal accepts only a meeting note and stable event ID")
    return CommercialService(workflow).prepare(lead_id, **payload)


@app.post("/api/proposals/{draft_id}/review")
def review_proposal(draft_id: str, payload: dict = Body(...)):
    if set(payload) != {"expected_version", "note", "evidence"}:
        raise ValueError("Proposal review requires version, note and verification evidence only")
    return CommercialService(workflow).review(draft_id, **payload)


@app.get("/api/v2/offers")
def v2_offer_state():
    return OfferService(workflow).state()


def offer_payload(payload, fields):
    if set(payload) != set(fields):
        raise ValueError("Only declared Offer workflow fields accepted; actor/live authority cannot be supplied")


@app.post("/api/v2/offers/{offer_id}/configure")
def v2_offer_configure(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_version", "change", "event_id"])
    return OfferService(workflow).configure(offer_id, **payload)


@app.post("/api/v2/offers/{offer_id}/test")
def v2_offer_test(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_version", "scenario", "event_id"])
    return OfferService(workflow).test(offer_id, **payload)


@app.post("/api/v2/offers/{offer_id}/release")
def v2_offer_release(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_version", "test_id", "note", "event_id"])
    return OfferService(workflow).release(offer_id, **payload)


@app.post("/api/v2/offers/{offer_id}/batch")
def v2_offer_batch(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_version", "scenario", "event_id"])
    return OfferService(workflow).run_batch(offer_id, **payload)


@app.post("/api/v2/offers/{offer_id}/feedback")
def v2_offer_feedback(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["batch_id", "scenario", "event_id"])
    return OfferService(workflow).feedback(offer_id, **payload)


@app.post("/api/v2/offers/{offer_id}/reconcile")
def v2_offer_reconcile(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["batch_id", "expected_feedback_id", "note", "event_id"])
    return OfferService(workflow).reconcile(offer_id, **payload)


@app.get("/api/v2/offers/{offer_id}/followthrough")
def offer_followthrough_state(offer_id: str):
    return OfferFollowthrough(workflow).state(offer_id)


@app.post("/api/v2/offers/{offer_id}/followthrough/proposals")
def prepare_offer_proposal(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_evidence_sha", "requested_terms", "event_id"])
    return OfferFollowthrough(workflow).prepare(offer_id, **payload)


@app.post("/api/v2/offers/{offer_id}/followthrough/proposals/{proposal_id}/review")
def review_offer_proposal(offer_id: str, proposal_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_evidence_sha", "expected_version", "note", "event_id"])
    return OfferFollowthrough(workflow).review(offer_id, proposal_id, **payload)


@app.post("/api/v2/offers/{offer_id}/followthrough/am-actions")
def open_offer_am_action(offer_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_evidence_sha", "event_id"])
    return OfferFollowthrough(workflow).open_action(offer_id, **payload)


@app.post("/api/v2/offers/{offer_id}/followthrough/am-actions/{action_id}/resolve")
def resolve_offer_am_action(offer_id: str, action_id: str, payload: dict = Body(...)):
    offer_payload(payload, ["expected_evidence_sha", "expected_version", "note", "event_id"])
    return OfferFollowthrough(workflow).resolve(offer_id, action_id, **payload)


dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
