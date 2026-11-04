"""Exercise real process restart and correction follow-through; local fixtures only."""
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
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "tests"
EVIDENCE.mkdir(exist_ok=True)
result = {"started_at": datetime.now(timezone.utc).isoformat(), "checks": [], "live_effects": False, "model_calls": 0}
process = None
log = (EVIDENCE / "reconciliation-process.log").open("w")
with socket.socket() as reserve:
    reserve.bind(("127.0.0.1", 0))
    port = reserve.getsockname()[1]
base = f"http://127.0.0.1:{port}"


def call(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=body, headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)


def start(db_path):
    global process
    env = {**os.environ, "EVERFLOW_DEMO_DB": str(db_path)}
    command = [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", str(port), "--workers", "1"]
    result.setdefault("commands", []).append(command)
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Verification server exited; inspect reconciliation-process.log")
        try:
            if call("/api/health")["status"] == "ok":
                return
        except (OSError, ValueError):
            time.sleep(0.1)
    raise RuntimeError("Loopback verification server was not ready")


def stop():
    global process
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        result.setdefault("server_exit_codes", []).append(process.returncode)
        process = None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def check(name, condition, **evidence):
    result["checks"].append({"name": name, "pass": bool(condition), **evidence})
    if not condition:
        raise AssertionError(name)


try:
    with tempfile.TemporaryDirectory(prefix="everflow-finance-restart-") as temp:
        db_path = Path(temp) / "verification.sqlite3"
        start(db_path)
        finance = call("/api/reconciliation/compare", {"fixture_id": "partial"})
        case = finance["cases"][0]
        finance = call(f"/api/reconciliation/cases/{case['id']}/decision", {
            "expected_run_id": case["current_run_id"], "expected_version": case["version"],
            "decision": "request_correction", "note": "Synthetic incomplete input requires correction",
            "evidence": "Retained control-count and completeness mismatch"})
        check("Owned correction follow-up is durably scheduled", finance["tasks"][0]["status"] == "scheduled")
        before = call("/api/state")
        stop()
        start(db_path)
        after = call("/api/state")
        check("Process restart preserves the entire workflow and finance state", fingerprint(before) == fingerprint(after), before_sha256=fingerprint(before), after_sha256=fingerprint(after))
        call("/api/tick", {"advance_hours": 24})
        state = call("/api/tick", {"advance_hours": 0})
        due = [e for e in state["audit"] if e["event"] == "reconciliation_followup_due"]
        check("Due correction produces one in-app alert after repeated ticks", len(due) == 1 and state["reconciliation"]["tasks"][0]["status"] == "due")
        finance = call("/api/reconciliation/compare", {"fixture_id": "partial_corrected"})
        case = finance["cases"][0]
        check("Corrected evidence completes prior follow-up and reopens owned review", finance["tasks"][0]["status"] == "completed" and case["status"] == "review_required")
        finance = call(f"/api/reconciliation/cases/{case['id']}/decision", {
            "expected_run_id": case["current_run_id"], "expected_version": case["version"],
            "decision": "review_complete", "note": "Synthetic corrected match reviewed",
            "evidence": "Complete immutable controls, current report hashes and event IDs verified"})
        before = call("/api/state")
        stop()
        start(db_path)
        final = call("/api/state")
        check("Final finance decision and original evidence survive a second restart", fingerprint(before) == fingerprint(final) and final["reconciliation"]["cases"][0]["status"] == "resolved" and len(final["reconciliation"]["decisions"]) == 2)
        check("Restart and finance review create no external or financial authority", not final["actions"] and not final["messages"] and not final["reconciliation"]["effects"]["settlement_enabled"] and final["cost"]["provider_attempts"] == 0)
        stop()
    result["pass"] = True
except Exception as exc:
    result["pass"] = False
    result["error"] = repr(exc)
    raise
finally:
    stop()
    log.close()
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for folder in ("backend", "tests") for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".json") and "__pycache__" not in p.parts}
    (EVIDENCE / "reconciliation-restart.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
