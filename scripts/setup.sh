#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
task_python=${EVERFLOW_PYTHON:-python3}
"$task_python" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ is required; this candidate was verified on Python 3.12"'
"$task_python" -m venv .venv
if command -v uv >/dev/null 2>&1; then
  uv --cache-dir "${EVERFLOW_UV_CACHE:-${TMPDIR:-/tmp}/everflow-uv-cache}" pip install --python .venv/bin/python -r requirements.lock
else
  .venv/bin/python -m pip install --no-cache-dir -r requirements.lock
fi
npm --prefix frontend ci --cache "${EVERFLOW_NPM_CACHE:-${TMPDIR:-/tmp}/everflow-npm-cache}" --prefer-offline --no-audit --no-fund
npm --prefix frontend run build
