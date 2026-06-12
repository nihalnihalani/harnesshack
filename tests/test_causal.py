"""libs/clickhouse/causal.py — SQL construction + onset-math reference tests.

Everything here runs WITHOUT credentials: SQL string construction is asserted
structurally, and the onset-detection math is exercised through the
pure-python reference implementation against synthetic arrays and against the
real generated incident profile. The SQL's end-to-end behavior on a real
cluster is the @pytest.mark.live test at the bottom (runs once B2 lands).
"""

from __future__ import annotations

import random

import pytest

from libs.clickhouse import schema
from libs.clickhouse.causal import (
    CausalEdge,
    build_causal_sql,
    detect_onset_index,
    find_causal_chains,
)
from libs.errors import NotConfiguredError
from scripts import incident_profile as profile

# ---------------------------------------------------------------------------
# SQL string construction
# ---------------------------------------------------------------------------


def test_sql_targets_metrics_table_with_window_functions():
    sql = build_causal_sql()
    assert "FROM metrics" in sql
    assert "PARTITION BY service, metric" in sql
    assert "ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING" in sql
    assert "stddevPop(value)" in sql and "avg(value)" in sql
    assert "lagInFrame(" in sql  # LAG/LEAD pairing of onsets
    assert "min(ts) AS onset_ts" in sql
    assert "dateDiff('second'" in sql


def test_sql_binds_tunables_as_server_side_parameters():
    sql = build_causal_sql()
    # Bound parameters survive as {name:Type} — never interpolated values.
    assert "{threshold_z:Float64}" in sql
    assert "{window_minutes:UInt32}" in sql


def test_sql_guards_constant_series_and_thin_baselines():
    sql = build_causal_sql(baseline_rows=24, min_baseline_rows=6)
    assert "baseline_std > 0" in sql  # pool_max (constant 100) can never onset
    assert "baseline_n >= 6" in sql
    assert "ROWS BETWEEN 24 PRECEDING AND 1 PRECEDING" in sql


def test_sql_rejects_nonsense_frames():
    with pytest.raises(ValueError):
        build_causal_sql(baseline_rows=10, min_baseline_rows=20)
    with pytest.raises(ValueError):
        build_causal_sql(baseline_rows=1)


def test_sql_output_columns_are_the_contract():
    sql = build_causal_sql()
    for column in ("cause_service", "effect_service", "lag_seconds"):
        assert column in sql
    assert "pandas" not in sql.lower()  # runs entirely in ClickHouse


# ---------------------------------------------------------------------------
# Onset-detection math (pure-python reference of the SQL)
# ---------------------------------------------------------------------------


def test_onset_none_for_steady_noise():
    rng = random.Random(7)
    values = [100 + rng.gauss(0, 2) for _ in range(200)]
    # Clamp like the profile does — steady noise must never z-breach.
    values = [min(max(v, 95.6), 104.4) for v in values]
    assert detect_onset_index(values) is None


def test_onset_none_for_constant_series():
    assert detect_onset_index([100.0] * 200) is None  # stddev == 0 guard


def test_onset_exact_index_for_injected_anomaly():
    rng = random.Random(11)
    values = [40 + max(-4, min(4, rng.gauss(0, 1.5))) for _ in range(120)]
    # Inject a climb from index 80: +2 per sample.
    for i in range(80, 120):
        values[i] = 40 + (i - 80 + 1) * 2.0
    onset = detect_onset_index(values)
    assert onset is not None
    assert 80 <= onset <= 83  # detected within a few samples of injection


def test_onset_requires_min_baseline_rows():
    values = [1000.0] + [10.0] * 5 + [1000.0] * 5
    assert detect_onset_index(values, min_baseline_rows=12) is None


def test_onsets_on_generated_profile_form_the_demo_chain():
    """db pool onset precedes payments onset precedes checkout onset."""
    rows = profile.generate_rows(profile.DEFAULT_SEED)

    def series(service: str, metric: str) -> list[float]:
        return [v for ts, s, m, v in rows if s == service and m == metric]

    step = profile.STEP_SECONDS
    db_onset = detect_onset_index(series(profile.DB_PRIMARY, profile.POOL_USED))
    pay_onset = detect_onset_index(series(profile.PAYMENTS, profile.P99))
    chk_onset = detect_onset_index(series(profile.CHECKOUT, profile.P99))
    assert db_onset is not None and pay_onset is not None and chk_onset is not None

    # Chain order is the causal story: db -> payments -> checkout.
    assert db_onset < pay_onset < chk_onset

    # db anomaly detected shortly after the true climb start (+650 s)...
    assert profile.DB_CLIMB_ONSET_OFFSET <= db_onset * step <= profile.DB_CLIMB_ONSET_OFFSET + 90
    # ...and payments detected during its rise, before the 2400 ms breach.
    assert db_onset * step + 60 <= pay_onset * step <= profile.PAYMENTS_BREACH_OFFSET

    # pool_max is constant — the reference (like the SQL guard) never onsets.
    assert detect_onset_index(series(profile.DB_PRIMARY, profile.POOL_MAX)) is None


# ---------------------------------------------------------------------------
# Live cluster (B2) — excluded by default, run via `pytest -m live`
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_find_causal_chains_live_cluster():
    """End-to-end on the REAL cluster. Pre-req: scripts/replay.py has run.

    Run order once B2 lands:
        python3 scripts/replay.py --truncate-first --speed 100
        pytest -m live
    """
    from libs.clickhouse import get_client, is_configured

    if not is_configured():
        pytest.skip("CLICKHOUSE_* not set — BUILD-STATE.md B2 still open")

    try:
        client = get_client()
    except NotConfiguredError as exc:  # pragma: no cover - guarded above
        pytest.skip(str(exc))

    client.command(schema.METRICS_TABLE_DDL)
    count = client.query("SELECT count() FROM metrics").result_rows[0][0]
    assert count > 0, "metrics table is empty — run scripts/replay.py first"

    edges = find_causal_chains(client, window_minutes=15, threshold_z=3.0)
    assert edges, "expected at least one causal edge from the replayed incident"
    assert all(isinstance(e, CausalEdge) for e in edges)

    db_to_payments = [
        e
        for e in edges
        if e.cause_service == profile.DB_PRIMARY and e.effect_service == profile.PAYMENTS
    ]
    assert db_to_payments, f"expected {profile.DB_PRIMARY} -> {profile.PAYMENTS} edge in {edges}"
    assert 0 < db_to_payments[0].lag_seconds <= 900
