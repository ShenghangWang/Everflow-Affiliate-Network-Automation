"""FastAPI surface for the loopback-only, synthetic prototype."""
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .domain import Workflow

ROOT = Path(__file__).resolve().parents[1]
workflow = Workflow(os.environ.get("EVERFLOW_DEMO_DB", str(ROOT / "data" / "demo.sqlite3")))
app = FastAPI(title="Affiliate Network Foundation — synthetic local demo", docs_url="/api/docs")


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    host = request.url.hostname
    if host not in ("127.0.0.1", "localhost", "testserver", "::1"):
        return JSONResponse({"detail": "This demo accepts loopback hosts only"}, status_code=403)
    origin = request.headers.get("origin")
    # Reject browser cross-origin mutations, including local-looking origins on
    # arbitrary ports. Vite is the one explicit local development exception.
    if origin and request.method not in ("GET", "HEAD", "OPTIONS"):
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.port not in (8000, 5173):
            return JSONResponse({"detail": "Cross-origin mutation rejected"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response


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


dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
