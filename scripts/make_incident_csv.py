#!/usr/bin/env python3
"""Generate demo_assets/incident_metrics.csv — the recorded incident window.

Seeded RNG (default seed in scripts/incident_profile.py) so the committed CSV
is reproducible byte-for-byte. The generator VERIFIES the ground-truth timing
before writing: payments-service p99_ms first breaches 2400 ms EXACTLY 250 s
(4 m 10 s) after payments-db-primary pool_used begins its climb.

Usage:
    python3 scripts/make_incident_csv.py [--seed N] [--out PATH]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import incident_profile as profile

DEFAULT_OUT = REPO_ROOT / "demo_assets" / "incident_metrics.csv"


def verify_ground_truth(rows: list[tuple]) -> tuple[str, str, float]:
    """Assert the 250 s climb->breach lead holds; return the breach row facts."""
    climb_onset_ts = profile.WINDOW_START.timestamp() + profile.DB_CLIMB_ONSET_OFFSET

    breach_ts = None
    breach_value = None
    for ts, service, metric, value in rows:
        if (
            service == profile.PAYMENTS
            and metric == profile.P99
            and value >= profile.BREACH_THRESHOLD_MS
        ):
            breach_ts, breach_value = ts, value
            break
    if breach_ts is None:
        raise AssertionError("payments-service p99_ms never breached 2400 ms")

    lead = breach_ts.timestamp() - climb_onset_ts
    if lead != profile.BREACH_LEAD_SECONDS:
        raise AssertionError(
            f"climb->breach lead is {lead:.0f}s, expected {profile.BREACH_LEAD_SECONDS}s"
        )

    # The climb really begins at the onset: pool trend departs baseline after it.
    pool = [
        (ts, value)
        for ts, service, metric, value in rows
        if service == profile.DB_PRIMARY and metric == profile.POOL_USED
    ]
    pre = [v for ts, v in pool if ts.timestamp() < climb_onset_ts]
    post = [v for ts, v in pool if ts.timestamp() >= climb_onset_ts + 60]
    if max(pre) >= 60 or min(post) <= max(pre):
        raise AssertionError("pool_used climb shape violated (baseline vs post-onset)")

    return profile.format_ts(breach_ts), profile.format_value(profile.P99, breach_value), lead


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=profile.DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    rows = profile.generate_rows(seed=args.seed)
    breach_ts, breach_value, lead = verify_ground_truth(rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(profile.CSV_COLUMNS)
        for ts, service, metric, value in rows:
            writer.writerow(
                [profile.format_ts(ts), service, metric, profile.format_value(metric, value)]
            )

    print(f"wrote {len(rows)} rows -> {args.out}")
    print(
        f"ground truth verified: pool climb onset "
        f"{profile.format_ts(profile.WINDOW_START)}+{profile.DB_CLIMB_ONSET_OFFSET}s, "
        f"payments p99 breach at {breach_ts} ({breach_value} ms), lead {lead:.0f}s (4m10s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
