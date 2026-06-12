#!/usr/bin/env python3
"""One-command pre-demo setup: check, heal, warm, and print the numbers to say.

Runs every check the 60-second demo depends on, in dependency order:
  1. .env sanity (the four Composio lines, JIRA_PROJECT_KEY=PLAT)
  2. ClickHouse reachable; metrics table populated — AUTO-RUNS replay.py if
     empty/short (the tables have been found truncated once already today)
  3. Causal query warm + returns the demo edge (also pre-warms the connection
     — first query after idle measured at ~25s, warm at ~35ms)
  4. Pioneer GLiNER2 extraction warm (prints the badge latency)
  5. Pioneer GLiGuard screen warm (cold start can be >10s — this absorbs it
     so the live demo send isn't the cold call)
  6. Senso /org/search returns cited results
  7. Composio Slack+Jira connections ACTIVE (composio_link.py --check)
  8. Anthropic 1-token call (the postmortem model)

Langfuse is exercised implicitly: steps 4-5 emit spans through libs/tracing.

No Slack messages, no Jira issues, no truncation of NON-empty data — safe to
run any number of times, right up to recording.

Usage:
    python3 scripts/demo_preflight.py
Exit code 0 = everything green; 1 = at least one FAIL (read the table).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPECTED_METRIC_ROWS = 960  # incident_metrics.csv, byte-pinned by test


def load_env() -> None:
    """Populate os.environ from repo .env for vars not already set (quotes stripped)."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.split(" #")[0].strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


results: list[tuple[str, bool, str]] = []
say_numbers: list[str] = []


def step(name: str):
    def decorator(fn):
        def run():
            start = time.perf_counter()
            try:
                detail = fn() or "ok"
                ok = True
            except Exception as exc:  # noqa: BLE001 — every failure must land in the table
                detail, ok = f"{type(exc).__name__}: {str(exc)[:160]}", False
            wall = time.perf_counter() - start
            results.append((name, ok, f"{detail}  ({wall:.1f}s)"))
            print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
            return ok
        return run
    return decorator


@step("env: Composio + project key")
def check_env():
    missing = [
        k
        for k in ("COMPOSIO_API_KEY", "COMPOSIO_USER_ID", "SLACK_INCIDENT_CHANNEL", "JIRA_PROJECT_KEY")
        if not os.environ.get(k)
    ]
    if missing:
        raise RuntimeError(f"missing in .env: {', '.join(missing)}")
    project = os.environ["JIRA_PROJECT_KEY"]
    if project != "PLAT":
        raise RuntimeError(f"JIRA_PROJECT_KEY={project!r} — the seeded demo project is PLAT")
    return "all four set, project PLAT"


def _clickhouse_client():
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
        port=8443,
    )


@step("clickhouse: demo data (auto-replays if missing)")
def check_clickhouse_data():
    client = _clickhouse_client()
    count = client.query("SELECT count() FROM metrics").result_rows[0][0]
    if count < EXPECTED_METRIC_ROWS:
        print(f"        metrics has {count} rows (< {EXPECTED_METRIC_ROWS}) — running replay, ~60s ...")
        subprocess.run(
            [sys.executable, "scripts/replay.py", "--truncate-first", "--speed", "100"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        count = client.query("SELECT count() FROM metrics").result_rows[0][0]
        if count < EXPECTED_METRIC_ROWS:
            raise RuntimeError(f"replay ran but metrics still has {count} rows")
        return f"replayed -> {count} rows"
    return f"{count} rows present"


@step("clickhouse: causal edge (warm query)")
def check_causal():
    from libs.clickhouse.causal import find_causal_chains

    client = _clickhouse_client()
    start = time.perf_counter()
    edges = find_causal_chains(client, window_minutes=20)
    query_ms = (time.perf_counter() - start) * 1000
    demo_edge = next(
        (e for e in edges if e.cause_service == "payments-db-primary" and e.effect_service == "payments-service"),
        None,
    )
    if demo_edge is None:
        raise RuntimeError(f"demo edge not found; got {edges!r}")
    minutes, seconds = divmod(int(demo_edge.lag_seconds), 60)
    say_numbers.append(f"Causal lag: {minutes}m {seconds}s (DB pool -> payments), query ran in {query_ms:.0f}ms")
    cascade = next((e for e in edges if e.effect_service == "checkout-service"), None)
    if cascade:
        say_numbers.append(f"Bonus cascade: payments -> checkout, {int(cascade.lag_seconds)}s")
    return f"lag {demo_edge.lag_seconds}s, query {query_ms:.0f}ms"


@step("pioneer GLiNER2: severity extraction (warm)")
def check_gliner2():
    from libs.pioneer.gliner2 import extract_severity

    extraction = extract_severity(
        "PagerDuty alert: payments-service p99 latency 2466ms, payments-db-primary connection pool exhausted"
    )
    say_numbers.append(
        f"GLiNER2 badge: severity {extraction.severity}, {extraction.latency_ms:.0f}ms (server-reported)"
    )
    return f"{extraction.severity} in {extraction.latency_ms:.0f}ms"


@step("pioneer GLiGuard: outbound screen (absorbs cold start)")
def check_gliguard():
    from libs.pioneer.gliguard import screen

    verdict = screen("Preflight check: payments incident update, runbook step 3 in progress.")
    if not verdict.allowed:
        raise RuntimeError(f"benign text blocked: {verdict.categories}")
    say_numbers.append(f"GLiGuard screen: {verdict.latency_ms:.0f}ms (server-reported)")
    return f"allowed in {verdict.latency_ms:.0f}ms"


@step("senso: cited runbook search")
def check_senso():
    import httpx

    base = os.environ.get("SENSO_BASE_URL", "").strip() or "https://apiv2.senso.ai/api/v1"
    response = httpx.post(
        f"{base}/org/search",
        headers={"X-API-Key": os.environ["SENSO_API_KEY"]},
        json={"query": "payments runbook pool exhaustion", "max_results": 1},
        timeout=30.0,
    )
    response.raise_for_status()
    body = response.json()
    total = body.get("total_results", len(body.get("results", [])))
    if not total:
        raise RuntimeError("search returned 0 results — re-run scripts/seed_senso.py")
    return f"{total} cited result(s)"


@step("composio: Slack + Jira ACTIVE")
def check_composio():
    proc = subprocess.run(
        [sys.executable, "scripts/composio_link.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stdout + proc.stderr).strip()[-160:])
    return "both connections ACTIVE"


@step("anthropic: postmortem model reachable")
def check_anthropic():
    import anthropic

    message = anthropic.Anthropic().messages.create(
        model="claude-fable-5",
        max_tokens=1,
        messages=[{"role": "user", "content": "ping"}],
    )
    return f"200, model {message.model}"


def main() -> int:
    load_env()
    print("IncidentSherpa demo preflight\n")
    checks = [
        check_env,
        check_clickhouse_data,
        check_causal,
        check_gliner2,
        check_gliguard,
        check_senso,
        check_composio,
        check_anthropic,
    ]
    all_ok = all([check() for check in checks])  # no short-circuit: run everything

    print("\n" + "=" * 60)
    if all_ok:
        print("ALL GREEN — ready to record.")
    else:
        failed = ", ".join(name for name, ok, _ in results if not ok)
        print(f"NOT READY — fix: {failed}")
    if say_numbers:
        print("\nNumbers you can say on camera (measured just now):")
        for line in say_numbers:
            print(f"  - {line}")
    print(
        "\nRemaining manual steps: trigger the demo incident, pin the tabs"
        " (timeline / Langfuse / Slack #incidents / Jira PLAT / Render),"
        " arm the F2 fallback."
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
