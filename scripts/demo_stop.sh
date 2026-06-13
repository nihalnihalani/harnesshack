#!/usr/bin/env bash
# Stop the servers started by demo_start.sh.
#   bash scripts/demo_stop.sh
set -uo pipefail
for svc in api web; do
  pidfile="/tmp/sherpa-$svc.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    if kill "$pid" 2>/dev/null; then
      echo "stopped sherpa-$svc (pid $pid)"
    fi
    rm -f "$pidfile"
  fi
done
# Sweep any stragglers bound to the demo ports.
for port in 8000 3000; do
  pid="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  [ -n "$pid" ] && kill $pid 2>/dev/null && echo "freed port $port"
done
echo "done"
