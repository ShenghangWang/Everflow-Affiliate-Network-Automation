"""Create a separate inspectable checkpoint; never mutate frozen review inputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'reviews/checkpoint-evidence-20261104-r2'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(output=OUTPUT):
    manifest = json.loads((output / 'manifest.json').read_text())
    for entry in manifest['files']:
        path = output / entry['path']
        if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('Checkpoint evidence mismatch: ' + entry['path'])
    listed = {entry['path'] for entry in manifest['files']} | {'manifest.json'}
    actual = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
    if actual != listed:
        raise ValueError('Checkpoint contains unlisted/missing files')
    return manifest


def export(output=OUTPUT):
    if output.exists():
        raise FileExistsError('Preserve existing checkpoint; use --verify instead of overwriting')
    backend = json.loads((ROOT / 'evidence/tests/backend-tests.json').read_text())
    process = json.loads((ROOT / 'evidence/tests/bd-restart.json').read_text())
    browser = json.loads((ROOT / 'evidence/tests/ui/browser-results.json').read_text())
    if backend['exit_code'] != 0 or not process['pass'] or not browser['pass']:
        raise ValueError('Checkpoint must retain genuinely passing current results')
    for mapping in (backend['files_sha256'], process['source_sha256']):
        for name, expected in mapping.items():
            if digest(ROOT / name) != expected:
                raise ValueError('Current source differs from tested source: ' + name)
    paths = set()
    for directory in ('backend', 'frontend/src', 'tests', 'scripts'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix in ('.py', '.json', '.jsx', '.js', '.css', '.mjs', '.sh'))
    paths.update(ROOT / name for name in (
        '.gitignore', 'README.md', 'architecture.md', 'requirements.md', 'delivery.md',
        'requirements.txt', 'requirements.lock', 'frontend/index.html', 'frontend/package.json',
        'frontend/package-lock.json', 'frontend/vite.config.js',
        'reviews/status.md', 'reviews/combined-adjudication-D1-HLD-R2.md',
        'reviews/codex-original-D1-HLD-R1.md', 'reviews/codex-followup-D1-HLD-R2.md',
        'reviews/gemini-original-D1-HLD-R1.md', 'reviews/gemini-original-D1-HLD-R1.receipt.json',
        'reviews/gemini-followup-D1-HLD-R2.md', 'reviews/gemini-followup-D1-HLD-R2.receipt.json',
        'evidence/tests/fresh-setup.json', 'evidence/tests/fresh-setup.log', 'evidence/tests/fresh-final-manifest.json'))
    paths.update(p for p in (ROOT / 'evidence/tests/review-r2').rglob('*') if p.is_file())
    output.mkdir(parents=True)
    for path in sorted(paths):
        target = output / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (output / 'BUNDLE-README.md').write_text('''# Current local checkpoint evidence supplement

This separate bundle includes current application/fixture sources, test assertions and verifier scripts, dependency locks, actual logs/JSON, build hashes and browser screenshots. It does not amend either frozen D1-HLD-R1/R2 packet or imply that Codex/Gemini inspected this bundle. The review response cycle is complete for those frozen inputs; finding resolution/current readiness remains conditional and sponsor acceptance pending.

Read reviews/combined-adjudication-D1-HLD-R2.md and delivery.md §16, then evidence/tests/review-r2/manifest.json. That record links the current tested source hashes, 105 backend/API/export tests, 45 browser checks, build and nine BD process checks (three starts/two SIGKILL restarts). The current runtime uses synthetic fixtures, template fallback and mock transport, with zero paid model calls or live business effects. Full six-role architecture is distinct from implemented depth.

evidence/tests/fresh-setup.json/log and fresh-final-manifest.json are historical installation/recovery records at their own dates/source hashes, not a new installation of this revision. Backend/browser/process/build evidence in review-r2 is current at its recorded hashes. No clean foreign-machine or real-provider claim is made. Parent revision identifies the Git state before these working-source changes were committed; the exact included file hashes and resulting checkpoint tag bind the candidate.

Use README.md for setup and scripts/check_backend.py, check_bd_restart.py and check_ui.mjs for relevant checks. Normal runtime/dependencies are not bundled: no .venv, node_modules, .env, credential store or live/demo database. Original assignment bytes and frozen architecture inputs remain preserved separately in the project. manifest.json hashes every included file; scripts/export_checkpoint_evidence.py --verify checks this immutable supplement without overwriting it.
''')
    manifest = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'kind': 'Current local evidence supplement; not a reviewed architecture revision',
                'git_parent_at_export': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'candidate_tag': 'demo-review-followthrough-r1',
                'verification': {'backend_tests': backend['test_count'], 'browser_checks': len(browser['checks']),
                                 'bd_process_checks': len(process['checks']), 'source_hashes_match_actual_runs': True},
                'historical_files': ['evidence/tests/fresh-setup.json', 'evidence/tests/fresh-setup.log', 'evidence/tests/fresh-final-manifest.json'],
                'review_completion': 'Original Codex/Gemini R1/R2 response cycle complete; current code not independently approved',
                'finding_resolution': 'See combined ledger: local verified, design amended, future checks/business decisions open',
                'sponsor_acceptance': 'pending',
                'files': [{'path': str(p.relative_to(output)), 'bytes': p.stat().st_size, 'sha256': digest(p)}
                          for p in sorted(output.rglob('*')) if p.is_file()]}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return verify(output)


if __name__ == '__main__':
    result = verify() if sys.argv[1:] == ['--verify'] else export()
    print(json.dumps({'path': str(OUTPUT), 'files_verified': len(result['files']), 'verification': result['verification']}, indent=2))
