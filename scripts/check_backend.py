"""Run the focused backend checks and retain genuine command output."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
evidence = root / "evidence" / "tests"
evidence.mkdir(parents=True, exist_ok=True)
command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
started = datetime.now(timezone.utc).isoformat()
run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=90)
output = result.stdout + result.stderr
(evidence / "backend-tests.log").write_text(output)
runs = evidence / "runs"
runs.mkdir(exist_ok=True)
(runs / f"backend-{run_id}.log").write_text(output)
print(output, end="")
revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True)
files = sorted([*root.glob("backend/**/*.py"), *root.glob("backend/fixtures/*.json"), *root.glob("tests/*.py")])
manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
summary = {
    "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    "command": command, "working_directory": str(root), "exit_code": result.returncode,
    "test_count": int(re.search(r"Ran (\d+) tests?", output).group(1)) if re.search(r"Ran (\d+) tests?", output) else None,
    "revision": revision.stdout.strip() if revision.returncode == 0 else "uncommitted intake",
    "files_sha256": manifest,
    "boundaries": {"provider": "SQLite mock receipts", "inference": "template-fixture", "live_calls": 0},
    "unexecuted": ["Paid model token/deadline/atomic-budget accounting", "Live provider idempotency and ingestion lag", "Production auth/tenant isolation", "Browser UI exercise (separate root evidence)"]
}
(evidence / "backend-tests.json").write_text(json.dumps(summary, indent=2))
(runs / f"backend-{run_id}.json").write_text(json.dumps(summary, indent=2))
sys.exit(result.returncode)
