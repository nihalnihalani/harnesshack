#!/usr/bin/env python3
"""Replay demo_assets/incident_metrics.csv into the REAL ClickHouse `metrics` table.

The honest DEFAULT ingest path for the demo, disclosed on stage as "replaying
a recorded incident at 10x speed" — the causal SQL still runs live against
ClickHouse Cloud. Batches one insert per 5 s tick (all services together) and
sleeps the recorded interval scaled by --speed between ticks.

Raises NotConfiguredError while CLICKHOUSE_* is unset (BUILD-STATE.md B2) —
there is no offline pretend mode. The whole run executes inside a Langfuse
span via libs/tracing.@traced; while B3 is open it proceeds untraced with a
LOUD warning (never a silent no-op).

Usage:
    python3 scripts/replay.py [--speed 10] [--truncate-first] [--csv PATH]
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from libs.clickhouse import get_client
from libs.clickhouse.schema import METRICS_TABLE_DDL
from libs.errors import NotConfiguredError
from scripts.tracing_glue import call_traced

DEFAULT_CSV = REPO_ROOT / "demo_assets" / "incident_metrics.csv"
INSERT_COLUMNS = ["ts", "service", "metric", "value"]
PROGRESS_EVERY_BATCHES = 24  # one log line per 2 simulated minutes

log = logging.getLogger("replay")


def load_rows(csv_path: Path) -> list[tuple[datetime, str, str, float]]:
    """Parse the recorded CSV into typed rows (ts is timezone-aware UTC)."""
    rows: list[tuple[datetime, str, str, float]] = []
    with csv_path.open(newline="") as fh:
        for record in csv.DictReader(fh):
            ts = datetime.fromisoformat(record["ts"].replace("Z", "+00:00")).astimezone(UTC)
            rows.append((ts, record["service"], record["metric_name"], float(record["value"])))
    if not rows:
        raise ValueError(f"no rows in {csv_path}")
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


def iter_batches(
    rows: list[tuple[datetime, str, str, float]],
) -> list[tuple[datetime, list[list[Any]]]]:
    """Group rows into one insert batch per timestamp tick (CSV `metric_name`
    maps onto the `metrics` table's `metric` column)."""
    return [
        (ts, [[r[0], r[1], r[2], r[3]] for r in group])
        for ts, group in groupby(rows, key=lambda r: r[0])
    ]


def sleep_interval(current_ts: datetime, next_ts: datetime, speed: float) -> float:
    """Recorded gap between ticks, scaled by the replay speed."""
    if speed <= 0:
        raise ValueError(f"--speed must be > 0, got {speed}")
    return max(0.0, (next_ts - current_ts).total_seconds() / speed)


def run_replay(csv_path: Path, speed: float, truncate_first: bool) -> int:
    """Bulk-insert the recorded incident into ClickHouse. Returns rows inserted."""
    rows = load_rows(csv_path)
    batches = iter_batches(rows)

    client = get_client()  # raises NotConfiguredError while B2 is open
    client.command(METRICS_TABLE_DDL)
    if truncate_first:
        log.info("truncating metrics table")
        client.command("TRUNCATE TABLE metrics")

    window = (batches[-1][0] - batches[0][0]).total_seconds()
    log.info(
        "replaying %d rows / %d ticks (%.0fs window) at %gx -> ~%.0fs wall clock",
        len(rows),
        len(batches),
        window,
        speed,
        window / speed,
    )

    inserted = 0
    started = time.monotonic()
    for i, (ts, batch) in enumerate(batches):
        client.insert("metrics", batch, column_names=INSERT_COLUMNS)
        inserted += len(batch)
        if (i + 1) % PROGRESS_EVERY_BATCHES == 0 or i + 1 == len(batches):
            log.info(
                "tick %d/%d (%s) — %d rows inserted, %.1fs elapsed",
                i + 1,
                len(batches),
                ts.isoformat(),
                inserted,
                time.monotonic() - started,
            )
        if i + 1 < len(batches):
            time.sleep(sleep_interval(ts, batches[i + 1][0], speed))

    log.info("replay complete: %d rows in %.1fs", inserted, time.monotonic() - started)
    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--speed",
        type=float,
        default=10.0,
        help="replay speed multiplier (default 10x: 20-min window in ~2 min)",
    )
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help="TRUNCATE the metrics table before inserting",
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="recorded incident CSV")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    try:
        call_traced(
            "scripts.replay",
            run_replay,
            csv_path=args.csv,
            speed=args.speed,
            truncate_first=args.truncate_first,
            logger=log,
        )
    except NotConfiguredError as exc:
        log.error("blocked: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
