"""Actual SIGKILL/restart of a temporary BD server; no original demo data touched."""
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
sys.path.insert(0, str(ROOT))
from backend.domain import Workflow

OUT = ROOT / 'evidence/tests'
OUT.mkdir(exist_ok=True)
result = {'started_at': datetime.now(timezone.utc).isoformat(), 'checks': [],
          'live_effects': False, 'model_calls': 0, 'database': 'Temporary verifier DB; original demo DB unused'}
process = None
log = (OUT / 'bd-process.log').open('w')
with socket.socket() as reserve:
    reserve.bind(('127.0.0.1', 0))
    port = reserve.getsockname()[1]
base = f'http://127.0.0.1:{port}'


def call(path, payload=None):
    request = urllib.request.Request(base + path, data=None if payload is None else json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'} if payload is not None else {})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)


def start(db):
    global process
    command = [sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', str(port), '--workers', '1']
    result.setdefault('commands', []).append(command)
    process = subprocess.Popen(command, cwd=ROOT, env={**os.environ, 'EVERFLOW_DEMO_DB': str(db)}, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Temporary BD server exited; inspect bd-process.log')
        try:
            if call('/api/health')['status'] == 'ok':
                return
        except (OSError, ValueError):
            time.sleep(.1)
    raise RuntimeError('Temporary BD server not ready')


def stop(abrupt=False):
    global process
    if process is None:
        return
    if abrupt:
        process.kill()
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    result.setdefault('stops', []).append({'pid': process.pid, 'signal': 'SIGKILL' if abrupt else 'SIGTERM', 'exit_code': process.returncode})
    process = None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def check(name, condition, **detail):
    result['checks'].append({'name': name, 'pass': bool(condition), **detail})
    if not condition:
        raise AssertionError(name)


try:
    with tempfile.TemporaryDirectory(prefix='everflow-bd-kill-restart-') as temp:
        db = Path(temp) / 'verify.sqlite3'
        workflow = Workflow(db)
        workflow.draft('L001')
        workflow.draft('L002')
        workflow.dispatch('L002', transport_result='timeout_after_accept')
        seeded = workflow.state()
        unknown = next(a['id'] for a in seeded['actions'] if a['lead_id'] == 'L002')
        check('Seed retains pending and possible-acceptance action with one durable mock receipt',
              {a['status'] for a in seeded['actions']} == {'scheduled', 'unknown_outcome'} and sum(a['attempts'] for a in seeded['actions']) == 1)
        start(db)
        check('Actual HTTP server reads the exact persisted seed', fingerprint(call('/api/state')) == fingerprint(seeded))
        before = call('/api/state')
        stop(abrupt=True)
        start(db)
        after = call('/api/state')
        check('SIGKILL/restart preserves pending and unknown rows without automatic resend', fingerprint(before) == fingerprint(after),
              before_sha256=fingerprint(before), after_sha256=fingerprint(after))
        call('/api/tick', {'advance_hours': 0})
        state = call('/api/tick', {'advance_hours': 0})
        check('Scheduler does not bypass explicit initial-draft dispatch approval',
              next(a for a in state['actions'] if a['lead_id'] == 'L001')['status'] == 'scheduled'
              and next(a for a in state['actions'] if a['lead_id'] == 'L001')['attempts'] == 0)
        call('/api/leads/L001/dispatch', {})
        state = call('/api/leads/L001/dispatch', {})
        check('Ready unrelated outreach progresses while unknown action stays quarantined',
              next(a for a in state['actions'] if a['lead_id'] == 'L001' and a['kind'] == 'outreach')['attempts'] == 1
              and next(a for a in state['actions'] if a['id'] == unknown)['status'] == 'unknown_outcome'
              and next(a for a in state['actions'] if a['id'] == unknown)['attempts'] == 1)
        call('/api/leads/L002/reply', {'text': 'What is the payout?', 'event_id': 'reply-after-restart'})
        call(f'/api/actions/{unknown}/reconcile', {})
        state = call(f'/api/actions/{unknown}/reconcile', {})
        check('Reconciliation after a reply preserves conversation and creates no orphan follow-up',
              next(l for l in state['leads'] if l['id'] == 'L002')['stage'] == 'conversation'
              and not [a for a in state['actions'] if a['lead_id'] == 'L002' and a['kind'] == 'followup']
              and len([e for e in state['audit'] if e['event'] == 'mock_outcome_reconciled' and e['action_id'] == unknown]) == 1)
        before = state
        stop(abrupt=True)
        start(db)
        after = call('/api/state')
        check('Second SIGKILL/restart preserves receipts, conversation and scheduled follow-up', fingerprint(before) == fingerprint(after),
              before_sha256=fingerprint(before), after_sha256=fingerprint(after))
        call('/api/tick', {'advance_hours': 72})
        state = call('/api/tick', {'advance_hours': 0})
        followups = [a for a in state['actions'] if a['kind'] == 'followup']
        check('Recovered timer sends one logical mock follow-up at the due boundary',
              len(followups) == 1 and followups[0]['status'] == 'succeeded' and followups[0]['attempts'] == 1
              and all(a['attempts'] == 1 for a in state['actions']))
        check('Crash/restart verification enables no live or monetary authority', not state['mode']['live_effects'] and state['cost']['provider_attempts'] == 0)
        stop()
    result['pass'] = True
except Exception as exc:
    result.update({'pass': False, 'error': repr(exc)})
    raise
finally:
    stop()
    log.close()
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    result['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for folder in ('backend', 'tests') for p in (ROOT / folder).rglob('*')
                             if p.is_file() and p.suffix in ('.py', '.json') and '__pycache__' not in p.parts}
    result['verifier_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (OUT / 'bd-restart.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
