"""scripts/replay.py + scripts/tracing_glue.py — credential-free logic tests.

No ClickHouse and no Langfuse are mocked: tests exercise the pure logic (CSV
parsing, batching, sleep scaling) and the HONEST unconfigured behavior — the
real NotConfiguredError paths that exist while B2/B3 are open.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.errors import NotConfiguredError
from scripts import incident_profile as profile
from scripts.replay import (
    DEFAULT_CSV,
    INSERT_COLUMNS,
    iter_batches,
    load_rows,
    main,
    run_replay,
    sleep_interval,
)
from scripts.tracing_glue import call_traced

log = logging.getLogger("test.replay")


def test_load_rows_parses_committed_csv():
    rows = load_rows(DEFAULT_CSV)
    assert len(rows) == 960
    ts, service, metric, value = rows[0]
    assert ts == profile.WINDOW_START and ts.tzinfo is not None
    assert isinstance(value, float)
    # Sorted by (ts, service, metric) for tick batching.
    assert rows == sorted(rows, key=lambda r: (r[0], r[1], r[2]))


def test_iter_batches_groups_one_insert_per_tick():
    rows = load_rows(DEFAULT_CSV)
    batches = iter_batches(rows)
    assert len(batches) == 240  # one batch per 5 s tick
    for ts, batch in batches:
        assert len(batch) == 4  # 3 services / 4 series per tick
        assert all(r[0] == ts for r in batch)
        assert all(len(r) == len(INSERT_COLUMNS) for r in batch)
    assert sum(len(b) for _, b in batches) == len(rows)


def test_sleep_interval_scales_with_speed():
    a = datetime(2026, 6, 12, 14, 0, 0, tzinfo=UTC)
    b = a + timedelta(seconds=5)
    assert sleep_interval(a, b, speed=1.0) == 5.0
    assert sleep_interval(a, b, speed=10.0) == 0.5
    assert sleep_interval(a, b, speed=100.0) == pytest.approx(0.05)
    assert sleep_interval(b, a, speed=10.0) == 0.0  # never negative
    with pytest.raises(ValueError):
        sleep_interval(a, b, speed=0)


def test_load_rows_rejects_empty_csv(tmp_path: Path):
    empty = tmp_path / "empty.csv"
    empty.write_text("ts,service,metric_name,value\n")
    with pytest.raises(ValueError):
        load_rows(empty)


def test_run_replay_raises_not_configured_while_b2_open():
    """Honest blocker: no CLICKHOUSE_* env (conftest guarantees it) -> B2 error."""
    with pytest.raises(NotConfiguredError, match="B2"):
        run_replay(csv_path=DEFAULT_CSV, speed=1000.0, truncate_first=False)


def test_main_exits_nonzero_while_b2_open():
    assert main(["--speed", "1000"]) == 2


def test_call_traced_warns_loudly_and_runs_untraced_while_b3_open(caplog):
    """Tracing degrades LOUDLY (B3 named), and the workload still runs."""
    calls: list[int] = []

    def workload(x: int) -> int:
        calls.append(x)
        return x * 2

    with caplog.at_level(logging.WARNING):
        result = call_traced("test.span", workload, 21, logger=log)

    assert result == 42 and calls == [21]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "TRACING DISABLED" in message
    assert "B3" in message  # names the blocker


def test_call_traced_never_swallows_other_blockers(caplog):
    """A B2 (ClickHouse) NotConfiguredError from the workload must propagate."""

    def workload() -> None:
        raise NotConfiguredError("ClickHouse not configured — see BUILD-STATE.md B2")

    with caplog.at_level(logging.WARNING), pytest.raises(NotConfiguredError, match="B2"):
        call_traced("test.span", workload, logger=log)
