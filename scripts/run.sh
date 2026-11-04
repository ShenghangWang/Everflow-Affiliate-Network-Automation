#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
exec .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
