#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
exec .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $PORT

