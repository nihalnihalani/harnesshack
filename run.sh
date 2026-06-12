#!/usr/bin/env bash
#
# run.sh — launch IncidentSherpa locally with thorough debugging logs.
#
#   ./run.sh                      # start API + frontend, stream live logs
#   FRONTEND_PORT=3001 ./run.sh   # override a port
#   DEBUG=1 ./run.sh              # extra-verbose orchestration tracing
#
# Starts the FastAPI backend (the incident agent runs in-process) and the
# Next.js frontend. Ctrl+C stops both and frees the ports. Everything is
# logged to ./logs/  — the run log (orchestration), api.log, and frontend.log.
#
# Secret safety: this script logs which .env keys are SET vs EMPTY, but NEVER
# their values. There is no `set -x` (it would echo secrets while sourcing
# .env). Compatible with the macOS system bash (3.2).

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT" || { echo "run.sh: cannot cd to repo root" >&2; exit 1; }

API_PORT="${API_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
DEBUG="${DEBUG:-0}"

# --- logging -----------------------------------------------------------------
LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR" || { echo "run.sh: cannot create $LOG_DIR" >&2; exit 1; }
RUN_LOG="$LOG_DIR/run-$(date '+%Y%m%d-%H%M%S').log"
API_LOG="$LOG_DIR/api.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
# Console gets color; the log file gets plain text (no ANSI noise).
_emit() {
  local color="$1" level="$2"; shift 2
  local line="[$(ts)] ${level}$*"
  printf '%b%s\033[0m\n' "$color" "$line"
  printf '%s\n' "$line" >> "$RUN_LOG"
}
log()   { _emit '\033[1;36m' ''        "$@"; }   # cyan headline
note()  { _emit '\033[0;90m' 'DEBUG ' "$@"; }    # gray detail line (always on)
warn()  { _emit '\033[1;33m' 'WARN  ' "$@"; }    # yellow
fail()  { _emit '\033[1;31m' 'ERROR ' "$@"; exit 1; }

log "==================== IncidentSherpa launcher ===================="
note "run log        : $RUN_LOG"
note "api log        : $API_LOG"
note "frontend log   : $FRONTEND_LOG"

# --- environment diagnostics -------------------------------------------------
log "Environment diagnostics"
note "repo root      : $REPO_ROOT"
note "git            : $(git rev-parse --short HEAD 2>/dev/null || echo '?') on $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
note "os             : $(uname -srm)"
note "bash           : ${BASH_VERSION:-unknown}"
note "python         : $(.venv/bin/python --version 2>&1 || echo 'MISSING')"
note "uvicorn        : $(.venv/bin/uvicorn --version 2>&1 | head -1 || echo 'MISSING')"
note "node           : $(command -v node >/dev/null 2>&1 && node --version || echo 'MISSING')"
note "npm            : $(command -v npm  >/dev/null 2>&1 && npm --version  || echo 'MISSING')"
note "API port       : $API_PORT     frontend port: $FRONTEND_PORT"

# --- prerequisites -----------------------------------------------------------
log "Checking prerequisites"
[ -f .env ] || fail ".env not found in $REPO_ROOT — copy .env.example to .env and fill it."
note "  .env present"
[ -x .venv/bin/uvicorn ] || fail "Python venv not set up. Run once:
    python3 -m venv .venv && .venv/bin/pip install -r apps/api/requirements.txt -r apps/worker/requirements.txt"
note "  .venv/bin/uvicorn present"
command -v npm >/dev/null 2>&1 || fail "npm not found — install Node.js (https://nodejs.org)."
note "  npm present"

# --- .env key presence (SET/EMPTY only — NEVER values) -----------------------
log "Validating .env keys (showing SET/EMPTY — never the values)"
_envset=0; _envempty=0
while IFS= read -r _line || [ -n "$_line" ]; do
  case "$_line" in ''|\#*) continue ;; esac
  case "$_line" in *=*) : ;; *) continue ;; esac
  _key="${_line%%=*}"
  _val="${_line#*=}"
  # strip one layer of surrounding single/double quotes for the emptiness test
  _val="${_val%\"}"; _val="${_val#\"}"; _val="${_val%\'}"; _val="${_val#\'}"
  if [ -n "$_val" ]; then note "  SET    $_key"; _envset=$((_envset+1))
  else                    note "  empty  $_key"; _envempty=$((_envempty+1)); fi
done < .env
log ".env summary: $_envset set, $_envempty empty"

# --- port availability (auto-free) -------------------------------------------
# A stale uvicorn/next from a previous run is the #1 reason "./run.sh won't
# start". Rather than hard-fail and make you hunt the PID mid-demo, we FREE the
# port: SIGTERM the holder, wait, escalate to SIGKILL, then proceed. (You
# authorized reclaiming these project ports.) Only a port we truly cannot free
# is fatal.
log "Checking ports (busy ones are freed automatically)"
port_busy() { command -v lsof >/dev/null 2>&1 || return 1; lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
free_port() {  # $1 = port, $2 = human label
  if ! port_busy "$1"; then note "  $1 ($2) free"; return 0; fi
  warn "port $1 ($2) is in use — freeing it:"
  lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | tee -a "$RUN_LOG"
  lsof -ti :"$1" 2>/dev/null | xargs kill 2>/dev/null      # polite SIGTERM
  _n=1; while [ "$_n" -le 5 ]; do port_busy "$1" || break; sleep 1; _n=$((_n+1)); done
  if port_busy "$1"; then
    note "  $1 still held after SIGTERM — escalating to kill -9"
    lsof -ti :"$1" 2>/dev/null | xargs kill -9 2>/dev/null
    sleep 1
  fi
  port_busy "$1" && fail "Port $1 ($2) could not be freed. Inspect:  lsof -nP -iTCP:$1 -sTCP:LISTEN"
  note "  $1 ($2) freed"
}
free_port "$API_PORT" "API"
free_port "$FRONTEND_PORT" "frontend"

# --- load .env (the Python apps read os.environ directly) --------------------
log "Loading .env into the environment"
set -a
. ./.env
set +a
note "  sourced (NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE:-unset}, RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-unset})"
[ -n "${WEBHOOK_AUTH_TOKEN:-}" ] && note "  webhook auth ENABLED" || warn "  WEBHOOK_AUTH_TOKEN empty — webhook auth DISABLED (fine for local/demo)"

# --- frontend dependencies (first run only) ----------------------------------
if [ ! -d apps/frontend/node_modules ]; then
  log "Installing frontend dependencies (first run, ~1 min)…"
  ( cd apps/frontend && npm install ) >> "$FRONTEND_LOG" 2>&1 || fail "npm install failed — see $FRONTEND_LOG"
  note "  frontend deps installed"
else
  note "frontend node_modules present"
fi

# --- start services ----------------------------------------------------------
API_PID=""; FRONTEND_PID=""; TAIL_PID=""

cleanup() {
  trap - EXIT
  echo
  log "Shutting down…"
  [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null
  if [ -n "$FRONTEND_PID" ]; then note "killing frontend tree (pid $FRONTEND_PID)"; pkill -P "$FRONTEND_PID" 2>/dev/null; kill "$FRONTEND_PID" 2>/dev/null; fi
  if [ -n "$API_PID" ];      then note "killing API (pid $API_PID)";              pkill -P "$API_PID" 2>/dev/null;      kill "$API_PID" 2>/dev/null; fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti :"$API_PORT" 2>/dev/null | xargs kill 2>/dev/null
    lsof -ti :"$FRONTEND_PORT" 2>/dev/null | xargs kill 2>/dev/null
  fi
  wait 2>/dev/null
  log "Stopped. Logs: $RUN_LOG | $API_LOG | $FRONTEND_LOG"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

: > "$API_LOG"; : > "$FRONTEND_LOG"
log "Starting API (uvicorn, --log-level debug) → http://localhost:$API_PORT"
note "  cmd: .venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port $API_PORT --log-level debug"
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port "$API_PORT" --log-level debug >> "$API_LOG" 2>&1 &
API_PID=$!
note "  API pid $API_PID"

log "Starting frontend (next dev) → http://localhost:$FRONTEND_PORT"
note "  cmd: (cd apps/frontend && npm run dev -- -p $FRONTEND_PORT)"
( cd apps/frontend && npm run dev -- -p "$FRONTEND_PORT" ) >> "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
note "  frontend pid $FRONTEND_PID"

# --- wait for the API /health, logging every attempt -------------------------
log "Polling http://localhost:$API_PORT/health"
api_up=""; i=1
while [ "$i" -le 30 ]; do
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://localhost:$API_PORT/health" 2>/dev/null)"
  note "  attempt $i/30 → HTTP ${code:-no-response}"
  [ "$code" = "200" ] && { api_up=yes; break; }
  kill -0 "$API_PID" 2>/dev/null || fail "API (pid $API_PID) exited during startup — last lines of $API_LOG:
$(tail -n 15 "$API_LOG")"
  sleep 1; i=$((i+1))
done

if [ -n "$api_up" ]; then
  log "API is UP. /health response:"
  _health="$(curl -s -m 5 "http://localhost:$API_PORT/health")"
  printf '%s\n' "$_health" >> "$RUN_LOG"
  printf '%s\n' "$_health" | .venv/bin/python -m json.tool 2>/dev/null || printf '%s\n' "$_health"
else
  warn "API did not answer /health within 30s — it may still be starting. See $API_LOG"
fi

cat <<EOF

  ───────────────────────────────────────────────────────────────
   IncidentSherpa is running
     Frontend UI :  http://localhost:$FRONTEND_PORT
     API / health:  http://localhost:$API_PORT/health
     Logs        :  $LOG_DIR/   (run-*.log, api.log, frontend.log)

   Drive a demo incident in a SEPARATE terminal:
     cd "$REPO_ROOT" && set -a && source .env && set +a
     .venv/bin/python scripts/replay.py  --speed 100 --truncate-first
     .venv/bin/python scripts/trigger.py --payload demo_assets/incident_payload.json

   Live service logs follow below. Press Ctrl+C to stop everything.
  ───────────────────────────────────────────────────────────────

EOF

# Stream both service logs live (single tail process → clean shutdown). The
# "==> file <==" headers tell you which service each block came from.
log "Streaming live service logs (also persisted in $LOG_DIR)…"
tail -n +1 -f "$API_LOG" "$FRONTEND_LOG" &
TAIL_PID=$!

# Block until a service exits or Ctrl+C; the EXIT trap cleans everything up.
wait "$API_PID" "$FRONTEND_PID"
