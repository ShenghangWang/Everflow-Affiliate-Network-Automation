"""Run backend checks and retain evidence for the tested Offer revision."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.run' / 'v2-evidence'
OUT.mkdir(parents=True, exist_ok=True)
command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
started = datetime.now(timezone.utc).isoformat()
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
clean_checkout = not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
sources = sorted([*ROOT.glob('backend/**/*.py'), *ROOT.glob('backend/fixtures/*.json'),
                  *ROOT.glob('tests/*.py'), ROOT / 'requirements.lock', Path(__file__)])
source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in sources}
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
output = result.stdout + result.stderr
run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
(OUT / 'runs').mkdir(exist_ok=True)
(OUT / 'backend-tests.log').write_text(output)
(OUT / 'runs' / (run_id + '.log')).write_text(output)
test_count = re.search(r'Ran (\d+) tests?', output)
summary = {
    'started_at_utc': started,
    'finished_at_utc': datetime.now(timezone.utc).isoformat(),
    'command': command,
    'exit_code': result.returncode,
    'test_count': int(test_count.group(1)) if test_count else None,
    'git_revision': revision,
    'clean_checkout': clean_checkout,
    'source_sha256': source_hashes,
    'mode': 'Synthetic fixtures and mocked effects',
}
(OUT / 'backend-tests.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
(OUT / 'runs' / (run_id + '.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(output)
sys.exit(result.returncode)
