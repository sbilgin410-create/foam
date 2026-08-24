#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
