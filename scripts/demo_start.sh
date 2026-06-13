#!/usr/bin/env bash
# One-command demo bring-up: starts both servers, runs preflight (checks +
# heals + warms + prints the numbers to say), then fires the demo incident so
# the timeline is mid-incident with the glowing RESOLVE button live.
#
#   bash scripts/demo_start.sh
#
# Leaves uvicorn + next dev running in the background (logs in /tmp). Ctrl-C
# here does NOT kill them; run `bash scripts/demo_stop.sh` to stop everything.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="$ROOT/.venv/bin"

echo "==> [1/4] starting API (uvicorn :8000)"
if ! curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
  "$PY/uvicorn" apps.api.main:app --port 8000 >/tmp/sherpa-api.log 2>&1 &
  echo "$!" >/tmp/sherpa-api.pid
  for _ in $(seq 1 30); do
    curl -fsS http://localhost:8000/health >/dev/null 2>&1 && break
    sleep 1
  done
  echo "    API up (log: /tmp/sherpa-api.log)"
else
  echo "    API already running"
fi

echo "==> [2/4] starting frontend (next dev :3000)"
if ! curl -fsS http://localhost:3000 >/dev/null 2>&1; then
  ( cd apps/frontend && npm run dev >/tmp/sherpa-web.log 2>&1 & echo "$!" >/tmp/sherpa-web.pid )
  for _ in $(seq 1 40); do
    curl -fsS http://localhost:3000 >/dev/null 2>&1 && break
    sleep 1
  done
  echo "    frontend up at http://localhost:3000 (log: /tmp/sherpa-web.log)"
else
  echo "    frontend already running"
fi

echo "==> [3/4] preflight (check + heal + warm + numbers)"
"$PY/python" scripts/demo_preflight.py || echo "    (preflight reported a non-green check — see above)"

echo "==> [4/4] firing the demo incident"
"$PY/python" scripts/trigger.py --payload demo_assets/incident_payload.json

echo ""
echo "READY. Open http://localhost:3000 — the RESOLVE button glows green when it's your click."
echo "Stop the servers later with: bash scripts/demo_stop.sh"
