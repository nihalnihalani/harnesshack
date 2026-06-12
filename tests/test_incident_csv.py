"""demo_assets/incident_metrics.csv — well-formedness + ground-truth timing.

These tests need NO credentials: they validate the committed artifact and its
generator math (claim integrity — the 4m10s causal lead the demo cites is a
property of this file, asserted here, not a number typed into a slide).
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import incident_profile as profile

CSV_PATH = Path(__file__).resolve().parents[1] / "demo_assets" / "incident_metrics.csv"


def _load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _parse_ts(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _series(rows: list[dict[str, str]], service: str, metric: str) -> list[tuple[datetime, float]]:
    return [
        (_parse_ts(r["ts"]), float(r["value"]))
        for r in rows
        if r["service"] == service and r["metric_name"] == metric
    ]


def test_csv_shape_and_columns():
    rows = _load_rows()
    # 20 min / 5 s = 240 ticks x 4 series (3 services; db emits pool_used + pool_max)
    assert len(rows) == 960
    assert tuple(rows[0].keys()) == profile.CSV_COLUMNS
    services = {r["service"] for r in rows}
    assert services == {profile.PAYMENTS, profile.DB_PRIMARY, profile.CHECKOUT}


def test_timestamps_are_iso8601_sorted_5s_grid():
    rows = _load_rows()
    stamps = [_parse_ts(r["ts"]) for r in rows]
    assert stamps == sorted(stamps)
    unique = sorted(set(stamps))
    assert len(unique) == 240
    assert unique[0] == profile.WINDOW_START
    assert all((b - a) == timedelta(seconds=5) for a, b in zip(unique, unique[1:], strict=False))


def test_every_series_has_full_coverage():
    rows = _load_rows()
    for service, metric in [
        (profile.PAYMENTS, profile.P99),
        (profile.DB_PRIMARY, profile.POOL_USED),
        (profile.DB_PRIMARY, profile.POOL_MAX),
        (profile.CHECKOUT, profile.P99),
    ]:
        assert len(_series(rows, service, metric)) == 240, (service, metric)


def test_baselines_are_realistic():
    rows = _load_rows()
    onset = profile.WINDOW_START + timedelta(seconds=profile.DB_CLIMB_ONSET_OFFSET)

    pay = [v for ts, v in _series(rows, profile.PAYMENTS, profile.P99) if ts < onset]
    assert all(150 <= v <= 210 for v in pay)
    assert 170 <= sum(pay) / len(pay) <= 190
    assert max(pay) - min(pay) > 10  # real noise, not a flat line

    pool = [v for ts, v in _series(rows, profile.DB_PRIMARY, profile.POOL_USED) if ts < onset]
    assert all(30 <= v <= 50 for v in pool)
    assert 37 <= sum(pool) / len(pool) <= 43

    chk = [v for ts, v in _series(rows, profile.CHECKOUT, profile.P99) if ts < onset]
    assert all(130 <= v <= 170 for v in chk)
    assert 142 <= sum(chk) / len(chk) <= 158


def test_pool_exhaustion_climb_is_gradual_and_reaches_100():
    rows = _load_rows()
    series = _series(rows, profile.DB_PRIMARY, profile.POOL_USED)
    onset = profile.WINDOW_START + timedelta(seconds=profile.DB_CLIMB_ONSET_OFFSET)

    post = [(ts, v) for ts, v in series if ts >= onset]
    assert max(v for _, v in post) == 100.0
    # Pinned at exhaustion once full.
    first_full = next(ts for ts, v in post if v == 100.0)
    assert all(v == 100.0 for ts, v in post if ts >= first_full)
    # Exhaustion happens BEFORE the latency breach (the causal story).
    breach_ts = profile.WINDOW_START + timedelta(seconds=profile.PAYMENTS_BREACH_OFFSET)
    assert first_full < breach_ts
    # Gradual: no single 5 s jump anywhere near baseline->full.
    climb = [v for ts, v in post if ts < first_full]
    deltas = [b - a for a, b in zip(climb, climb[1:], strict=False)]
    assert max(deltas) < 12  # ~60 connections over ~220 s, never a step function

    pool_max = [v for _, v in _series(rows, profile.DB_PRIMARY, profile.POOL_MAX)]
    assert set(pool_max) == {100.0}


def test_payments_breach_exactly_250s_after_pool_climb_onset():
    rows = _load_rows()
    series = _series(rows, profile.PAYMENTS, profile.P99)
    breach_ts = next(ts for ts, v in series if v >= profile.BREACH_THRESHOLD_MS)

    climb_onset = profile.WINDOW_START + timedelta(seconds=profile.DB_CLIMB_ONSET_OFFSET)
    assert (breach_ts - climb_onset).total_seconds() == profile.BREACH_LEAD_SECONDS == 250

    # Gradual approach: the sample before the breach is elevated but sub-2400,
    # and the rise spans many samples (not a step function).
    before = [v for ts, v in series if ts < breach_ts]
    assert 1000 < before[-1] < profile.BREACH_THRESHOLD_MS
    rising = [v for ts, v in series if climb_onset <= ts < breach_ts]
    assert sum(1 for a, b in zip(rising, rising[1:], strict=False) if b > a) >= 15


def test_csv_matches_seeded_generator_exactly():
    """The committed CSV is exactly generate_rows(DEFAULT_SEED) — no drift."""
    expected = [
        (profile.format_ts(ts), service, metric, profile.format_value(metric, value))
        for ts, service, metric, value in profile.generate_rows(profile.DEFAULT_SEED)
    ]
    actual = [
        (r["ts"], r["service"], r["metric_name"], r["value"]) for r in _load_rows()
    ]
    assert actual == expected
