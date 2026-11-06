#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
task_python=${EVERFLOW_PYTHON:-.venv/bin/python}
export EVERFLOW_DEMO_DB=${EVERFLOW_DEMO_DB:-.run/v2-offer-cycle.sqlite3}
exec "$task_python" -m uvicorn backend.app:app --host 127.0.0.1 --port "${EVERFLOW_PORT:-8020}" --workers 1
