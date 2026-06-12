#!/usr/bin/env bash
#
# run.sh — launch IncidentSherpa locally: the FastAPI backend (which also runs
# the incident agent) plus the Next.js frontend. From the repo root:
#
#     ./run.sh
#
# Press Ctrl+C to stop both. Ports are overridable for power users:
#     API_PORT=8000 FRONTEND_PORT=3000 ./run.sh
#
# Compatible with the macOS system bash (3.2). No `set -e` / `set -u`: a
# launcher that juggles background jobs + traps is more reliable with explicit
# checks than with errexit/nounset, which have sharp edges around `wait` and
# empty arrays in bash 3.2.

# Run from this script's own directory no matter where it is invoked from.
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT" || { echo "run.sh: cannot cd to repo root" >&2; exit 1; }

API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

say()  { printf '\033[1;36m[run.sh]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[run.sh] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# --- prerequisites -----------------------------------------------------------
[ -f .env ] || fail ".env not found in $REPO_ROOT — copy .env.example to .env and fill it."
[ -x .venv/bin/uvicorn ] || fail "Python venv not set up. Run once:
    python3 -m venv .venv && .venv/bin/pip install -r apps/api/requirements.txt -r apps/worker/requirements.txt"
command -v npm >/dev/null 2>&1 || fail "npm not found — install Node.js (https://nodejs.org)."

# --- port availability (lsof is present on macOS; skip the check if it isn't) -
port_busy() {
  command -v lsof >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}
port_busy "$API_PORT" && fail "Port $API_PORT (API) is already in use. Free it with:
    lsof -ti :$API_PORT | xargs kill"
port_busy "$FRONTEND_PORT" && fail "Port $FRONTEND_PORT (frontend) is already in use. Free it with:
    lsof -ti :$FRONTEND_PORT | xargs kill
  (or pick another:  FRONTEND_PORT=3001 ./run.sh )"

# --- load .env into the environment (the Python apps read os.environ) --------
say "Loading .env"
set -a
. ./.env
set +a

# --- frontend dependencies (first run only) ----------------------------------
if [ ! -d apps/frontend/node_modules ]; then
  say "Installing frontend dependencies (first run, ~1 min)…"
  ( cd apps/frontend && npm install ) || fail "npm install failed in apps/frontend"
fi

# --- start services ----------------------------------------------------------
API_PID=""
FRONTEND_PID=""

cleanup() {
  trap - EXIT          # ensure cleanup runs only once
  echo
  say "Shutting down…"
  [ -n "$FRONTEND_PID" ] && { pkill -P "$FRONTEND_PID" 2>/dev/null; kill "$FRONTEND_PID" 2>/dev/null; }
  [ -n "$API_PID" ]      && { pkill -P "$API_PID" 2>/dev/null;      kill "$API_PID" 2>/dev/null; }
  # Backstop: free both ports in case a worker subprocess outlived its parent.
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti :"$API_PORT" 2>/dev/null | xargs kill 2>/dev/null
    lsof -ti :"$FRONTEND_PORT" 2>/dev/null | xargs kill 2>/dev/null
  fi
  wait 2>/dev/null
  say "Stopped."
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

say "Starting API       → http://localhost:$API_PORT  (the agent runs here too)"
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

say "Starting frontend  → http://localhost:$FRONTEND_PORT"
( cd apps/frontend && npm run dev -- -p "$FRONTEND_PORT" ) &
FRONTEND_PID=$!

# --- wait for the API to answer /health before declaring ready ---------------
say "Waiting for the API to come up…"
api_up=""
i=1
while [ "$i" -le 30 ]; do
  if curl -fs "http://localhost:$API_PORT/health" >/dev/null 2>&1; then
    api_up="yes"; break
  fi
  kill -0 "$API_PID" 2>/dev/null || fail "API process exited during startup — see the log above."
  sleep 1
  i=$((i + 1))
done
[ -n "$api_up" ] && say "API is up (/health OK)." || say "API did not answer /health yet — check the log above."

cat <<EOF

  ───────────────────────────────────────────────────────────────
   IncidentSherpa is running
     Frontend UI :  http://localhost:$FRONTEND_PORT
     API / health:  http://localhost:$API_PORT/health

   Drive a demo incident in a SEPARATE terminal:
     cd "$REPO_ROOT"
     set -a && source .env && set +a
     .venv/bin/python scripts/replay.py  --speed 100 --truncate-first
     .venv/bin/python scripts/trigger.py --payload demo_assets/incident_payload.json

   Press Ctrl+C to stop everything.
  ───────────────────────────────────────────────────────────────

EOF

# Block until a service exits or Ctrl+C is pressed; the EXIT trap cleans up.
wait
