"""scripts/load_generator.py — credential-free logic tests.

Tick construction, anomaly-injection math (shared profile curves), the rate
multiplier, and the honest B2 blocker path. No live cluster needed.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from libs.errors import NotConfiguredError
from scripts import incident_profile as profile
from scripts.load_generator import INSERT_COLUMNS, build_tick_rows, main, run_generator

TICK_TS = datetime(2026, 6, 12, 15, 0, 0, tzinfo=UTC)


def test_baseline_tick_emits_all_series_once():
    rows = build_tick_rows(TICK_TS, rel_s=None, rate_multiplier=1, rng=random.Random(1))
    assert len(rows) == 4
    assert all(len(r) == len(INSERT_COLUMNS) for r in rows)
    assert {(r[1], r[2]) for r in rows} == {
        (profile.PAYMENTS, profile.P99),
        (profile.DB_PRIMARY, profile.POOL_USED),
        (profile.DB_PRIMARY, profile.POOL_MAX),
        (profile.CHECKOUT, profile.P99),
    }
    assert all(r[0] == TICK_TS for r in rows)


def test_baseline_values_match_recorded_distributions():
    rng = random.Random(2)
    samples = {key: [] for key in ["pay", "pool", "chk"]}
    for _ in range(200):
        for _ts, service, metric, value in build_tick_rows(TICK_TS, None, 1, rng):
            if service == profile.PAYMENTS:
                samples["pay"].append(value)
            elif metric == profile.POOL_USED:
                samples["pool"].append(value)
            elif service == profile.CHECKOUT:
                samples["chk"].append(value)
    assert 170 <= sum(samples["pay"]) / 200 <= 190 and all(150 <= v <= 210 for v in samples["pay"])
    assert 37 <= sum(samples["pool"]) / 200 <= 43 and all(30 <= v <= 50 for v in samples["pool"])
    assert 142 <= sum(samples["chk"]) / 200 <= 158 and all(130 <= v <= 170 for v in samples["chk"])


def test_injection_reaches_breach_exactly_at_250s():
    """Walk the injected timeline tick by tick — same ground truth as the CSV."""
    rng = random.Random(3)
    breach_rel = None
    pool_full_rel = None
    for rel in range(0, 400, profile.STEP_SECONDS):
        rows = build_tick_rows(TICK_TS, float(rel), 1, rng)
        by_series = {(r[1], r[2]): r[3] for r in rows}
        pay = by_series[(profile.PAYMENTS, profile.P99)]
        pool = by_series[(profile.DB_PRIMARY, profile.POOL_USED)]
        if breach_rel is None and pay >= profile.BREACH_THRESHOLD_MS:
            breach_rel = rel
        if pool_full_rel is None and pool == 100.0:
            pool_full_rel = rel
    assert breach_rel == profile.BREACH_LEAD_SECONDS == 250
    assert pool_full_rel is not None and pool_full_rel < breach_rel  # exhaustion first


def test_rate_multiplier_scales_rows_and_spreads_timestamps():
    rows = build_tick_rows(TICK_TS, rel_s=None, rate_multiplier=5, rng=random.Random(4))
    assert len(rows) == 20  # 4 series x 5 samples
    stamps = sorted({r[0] for r in rows})
    assert len(stamps) == 5
    assert stamps[0] == TICK_TS
    assert stamps[-1] == TICK_TS + timedelta(seconds=4)  # spread inside the 5 s tick
    with pytest.raises(ValueError):
        build_tick_rows(TICK_TS, None, 0, random.Random(5))


def test_run_generator_raises_not_configured_while_b2_open():
    with pytest.raises(NotConfiguredError, match="B2"):
        run_generator(inject=None, rate_multiplier=1, max_ticks=1, seed=1)


def test_main_exits_nonzero_while_b2_open():
    assert main(["--max-ticks", "1"]) == 2
    assert main(["--inject", "db_pool_exhaustion", "--max-ticks", "1"]) == 2
