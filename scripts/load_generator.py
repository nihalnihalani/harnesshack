#!/usr/bin/env python3
"""Long-running live metrics emitter — REAL inserts into ClickHouse every 5 s.

Emits the SAME baselines as the recorded CSV (shared curves in
scripts/incident_profile.py) for payments-service, payments-db-primary and
checkout-service. `--inject db_pool_exhaustion` starts the anomaly pattern on
demand: pool_used climbs from its first tick, payments-service p99_ms
breaches 2400 ms exactly 250 s (4 m 10 s) later, checkout degrades downstream.

`--rate-multiplier N` (Phase 8 load test) emits N samples per series per tick,
spread evenly inside the 5 s tick, multiplying insert volume without changing
the curve shapes.

Same discipline as replay.py: NotConfiguredError naming B2 while CLICKHOUSE_*
is unset (no offline pretend mode); the run executes in a Langfuse span via
libs/tracing.@traced, degrading to a LOUD warning while B3 is open. SIGINT
shuts down cleanly after the in-flight tick.

Usage:
    python3 scripts/load_generator.py [--inject db_pool_exhaustion]
                                      [--rate-multiplier N] [--max-ticks N]
"""

from __future__ import annotations

import argparse
import logging
import random
import signal
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from libs.clickhouse import get_client
from libs.clickhouse.schema import METRICS_TABLE_DDL
from libs.errors import NotConfiguredError
from scripts import incident_profile as profile
from scripts.tracing_glue import call_traced

INSERT_COLUMNS = ["ts", "service", "metric", "value"]
INJECTION_PATTERNS = ("db_pool_exhaustion",)
PROGRESS_EVERY_TICKS = 12  # one log line per simulated minute

log = logging.getLogger("load_generator")

_stop_requested = False


def _handle_sigint(signum: int, frame: Any) -> None:  # noqa: ARG001
    global _stop_requested
    _stop_requested = True
    log.info("SIGINT received — finishing in-flight tick, then shutting down cleanly")


def build_tick_rows(
    tick_ts: datetime,
    rel_s: float | None,
    rate_multiplier: int,
    rng: random.Random,
) -> list[list[Any]]:
    """All rows for one 5 s tick: 4 series x rate_multiplier samples.

    rel_s: seconds since anomaly injection (None = pure baseline). With a
    multiplier, samples are spread evenly inside the tick so the load test
    scales row volume without distorting the per-second timeline.
    """
    if rate_multiplier < 1:
        raise ValueError(f"--rate-multiplier must be >= 1, got {rate_multiplier}")
    rows: list[list[Any]] = []
    spacing = profile.STEP_SECONDS / rate_multiplier
    for i in range(rate_multiplier):
        sample_ts = tick_ts + timedelta(seconds=i * spacing)
        sample_rel = None if rel_s is None else rel_s + i * spacing
        for service, metric, value in profile.sample_services(sample_rel, rng):
            rows.append([sample_ts, service, metric, value])
    return rows


def run_generator(
    inject: str | None,
    rate_multiplier: int,
    max_ticks: int | None,
    seed: int | None,
) -> int:
    """Emit ticks until SIGINT (or max_ticks). Returns total rows inserted."""
    client = get_client()  # raises NotConfiguredError while B2 is open
    client.command(METRICS_TABLE_DDL)

    rng = random.Random(seed)
    rows_per_tick = 4 * rate_multiplier
    log.info(
        "emitting %d rows per %ds tick (rate multiplier %d)%s — Ctrl-C for clean shutdown",
        rows_per_tick,
        profile.STEP_SECONDS,
        rate_multiplier,
        f"; injecting {inject} from the first tick (breach follows in "
        f"{profile.BREACH_LEAD_SECONDS}s = 4m10s)"
        if inject
        else "",
    )

    inserted = 0
    tick = 0
    injection_started = time.monotonic() if inject else None
    next_tick_at = time.monotonic()
    while not _stop_requested:
        now = datetime.now(UTC)
        rel_s = None if injection_started is None else time.monotonic() - injection_started
        batch = build_tick_rows(now, rel_s, rate_multiplier, rng)
        client.insert("metrics", batch, column_names=INSERT_COLUMNS)
        inserted += len(batch)
        tick += 1

        if tick % PROGRESS_EVERY_TICKS == 0:
            log.info(
                "tick %d — %d rows inserted%s",
                tick,
                inserted,
                f", anomaly t+{rel_s:.0f}s" if rel_s is not None else "",
            )
        if rel_s is not None and 0 <= rel_s - profile.BREACH_LEAD_SECONDS < profile.STEP_SECONDS:
            log.info("payments-service p99_ms breach tick reached (t+%.0fs after injection)", rel_s)

        if max_ticks is not None and tick >= max_ticks:
            log.info("max-ticks %d reached", max_ticks)
            break
        next_tick_at += profile.STEP_SECONDS
        while not _stop_requested and time.monotonic() < next_tick_at:
            time.sleep(min(0.2, max(0.0, next_tick_at - time.monotonic())))

    log.info("shutdown: %d ticks, %d rows inserted", tick, inserted)
    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inject",
        choices=INJECTION_PATTERNS,
        default=None,
        help="start the anomaly pattern on demand (pool climb now, p99 breach 250s later)",
    )
    parser.add_argument(
        "--rate-multiplier",
        type=int,
        default=1,
        help="samples per series per tick (Phase 8 load test)",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="stop after N ticks (default: run until SIGINT)",
    )
    parser.add_argument("--seed", type=int, default=None, help="seed the RNG (reproducible runs)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        call_traced(
            "scripts.load_generator",
            run_generator,
            inject=args.inject,
            rate_multiplier=args.rate_multiplier,
            max_ticks=args.max_ticks,
            seed=args.seed,
            logger=log,
        )
    except NotConfiguredError as exc:
        log.error("blocked: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
