"""Causal-chain detection over the `metrics` table — runs ENTIRELY in ClickHouse.

Approach (no pandas, no client-side post-processing):

  1. `scored`  — per (service, metric), window functions compute a rolling
     baseline (mean / stddevPop / count) over the PRECEDING rows only, then a
     z-score for each sample against that baseline.
  2. `onsets`  — per service, the FIRST ts whose value exceeds
     baseline_mean + threshold_z * baseline_std (constant series are excluded
     by the `baseline_std > 0` guard, e.g. pool_max == 100).
  3. `ordered` — lagInFrame (ClickHouse's LAG) pairs consecutive onsets in
     onset-time order, yielding (cause_service, effect_service, lag_seconds)
     edges for onsets within the window.

`threshold_z` / `window_minutes` are bound as server-side query parameters
({name:Type}), never string-interpolated. The structural knobs
(baseline_rows / min_baseline_rows) are validated ints interpolated into the
window frame, because frame bounds cannot be parameterized.

`detect_onset_index` is the pure-python REFERENCE implementation of step 1+2's
math — unit-tested against synthetic arrays without any cluster; the SQL
itself is exercised by the @pytest.mark.live test once B2 lands.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, NamedTuple

# Rolling baseline: up to 60 preceding samples (5 min at 5 s resolution),
# requiring at least 12 (1 min) before a z-score is trusted.
DEFAULT_BASELINE_ROWS = 60
DEFAULT_MIN_BASELINE_ROWS = 12

_CAUSAL_SQL_TEMPLATE = """
WITH
scored AS (
    SELECT
        service,
        ts,
        value,
        avg(value)       OVER baseline AS baseline_mean,
        stddevPop(value) OVER baseline AS baseline_std,
        count(value)     OVER baseline AS baseline_n
    FROM metrics
    WINDOW baseline AS (
        PARTITION BY service, metric
        ORDER BY ts
        ROWS BETWEEN {baseline_rows} PRECEDING AND 1 PRECEDING
    )
),
onsets AS (
    SELECT
        service,
        min(ts) AS onset_ts
    FROM scored
    WHERE baseline_n >= {min_baseline_rows}
      AND baseline_std > 0
      AND (value - baseline_mean) / baseline_std > {{threshold_z:Float64}}
    GROUP BY service
),
ordered AS (
    SELECT
        lagInFrame(service)  OVER chain AS cause_service,
        lagInFrame(onset_ts) OVER chain AS cause_onset_ts,
        service                         AS effect_service,
        onset_ts                        AS effect_onset_ts
    FROM onsets
    WINDOW chain AS (
        ORDER BY onset_ts
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
)
SELECT
    cause_service,
    effect_service,
    dateDiff('second', cause_onset_ts, effect_onset_ts) AS lag_seconds
FROM ordered
WHERE cause_service != ''
  AND dateDiff('second', cause_onset_ts, effect_onset_ts)
      BETWEEN 1 AND {{window_minutes:UInt32}} * 60
ORDER BY effect_onset_ts
"""


class CausalEdge(NamedTuple):
    cause_service: str
    effect_service: str
    lag_seconds: int


def build_causal_sql(
    baseline_rows: int = DEFAULT_BASELINE_ROWS,
    min_baseline_rows: int = DEFAULT_MIN_BASELINE_ROWS,
) -> str:
    """Render the causal-chain SQL (threshold_z / window_minutes stay bound)."""
    baseline_rows = int(baseline_rows)
    min_baseline_rows = int(min_baseline_rows)
    if baseline_rows < 2 or min_baseline_rows < 2 or min_baseline_rows > baseline_rows:
        raise ValueError(
            f"invalid baseline frame: baseline_rows={baseline_rows}, "
            f"min_baseline_rows={min_baseline_rows}"
        )
    return _CAUSAL_SQL_TEMPLATE.format(
        baseline_rows=baseline_rows,
        min_baseline_rows=min_baseline_rows,
    )


def find_causal_chains(
    client: Any,
    window_minutes: int = 15,
    threshold_z: float = 3.0,
    baseline_rows: int = DEFAULT_BASELINE_ROWS,
    min_baseline_rows: int = DEFAULT_MIN_BASELINE_ROWS,
) -> list[CausalEdge]:
    """Run the causal SQL on a real clickhouse-connect client.

    Returns (cause_service, effect_service, lag_seconds) edges, chained in
    onset order — e.g. payments-db-primary -> payments-service with the
    measured anomaly-onset lag. `lag_seconds` is the lag between DETECTED
    anomaly onsets (rolling z-score crossings); the 4m10s headline number is
    the recorded climb-start -> 2400ms-breach lead, asserted over the demo
    CSV in tests/test_incident_csv.py.
    """
    result = client.query(
        build_causal_sql(baseline_rows=baseline_rows, min_baseline_rows=min_baseline_rows),
        parameters={
            "threshold_z": float(threshold_z),
            "window_minutes": int(window_minutes),
        },
    )
    return [
        CausalEdge(cause_service=row[0], effect_service=row[1], lag_seconds=int(row[2]))
        for row in result.result_rows
    ]


def detect_onset_index(
    values: Sequence[float],
    threshold_z: float = 3.0,
    baseline_rows: int = DEFAULT_BASELINE_ROWS,
    min_baseline_rows: int = DEFAULT_MIN_BASELINE_ROWS,
) -> int | None:
    """Pure-python reference of the SQL onset math (scored + onsets stages).

    Mirrors the frame `ROWS BETWEEN {baseline_rows} PRECEDING AND 1 PRECEDING`
    with stddevPop semantics: the first index whose value exceeds
    rolling_mean + threshold_z * rolling_stddev (population), given at least
    `min_baseline_rows` preceding samples and a non-zero stddev.
    """
    for i in range(len(values)):
        window = values[max(0, i - baseline_rows) : i]
        n = len(window)
        if n < min_baseline_rows:
            continue
        mean = sum(window) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in window) / n)
        if std > 0 and (values[i] - mean) / std > threshold_z:
            return i
    return None
