"""Shared incident shape — single source of truth for the demo metric curves.

Used by scripts/make_incident_csv.py (recorded 20-minute incident window) and
scripts/load_generator.py (live baseline emitter + on-demand anomaly), so the
replayed CSV and the live generator emit IDENTICAL distributions.

Ground truth (claim integrity — every demo number traces back to these
constants):

  - payments-db-primary `pool_used` departs its ~40-connection baseline at
    DB_CLIMB_ONSET_OFFSET and climbs linearly to pool_max (100) over
    ~220 s — full exhaustion BEFORE the latency breach.
  - payments-service `p99_ms` first meets/exceeds BREACH_THRESHOLD_MS
    (2400 ms) EXACTLY BREACH_LEAD_SECONDS = 250 s (4 m 10 s) after the pool
    climb begins. The rise itself is gradual (quadratic ease over 100 s),
    not a step.
  - checkout-service `p99_ms` degrades mildly afterwards (downstream of
    payments) — third link in the causal chain.

All curve functions take `rel_s`: seconds since the DB pool climb onset
(None or negative = pure baseline). Randomness comes from a caller-supplied
`random.Random`, so a fixed seed reproduces the committed CSV byte-for-byte.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

# ---------------------------------------------------------------------------
# Window + identity constants
# ---------------------------------------------------------------------------

WINDOW_SECONDS = 1200  # 20-minute incident window
STEP_SECONDS = 5  # 5 s resolution
WINDOW_START = datetime(2026, 6, 12, 14, 0, 0, tzinfo=UTC)
DEFAULT_SEED = 20260612

PAYMENTS = "payments-service"
DB_PRIMARY = "payments-db-primary"
CHECKOUT = "checkout-service"

P99 = "p99_ms"
POOL_USED = "pool_used"
POOL_MAX = "pool_max"

CSV_COLUMNS = ("ts", "service", "metric_name", "value")

# ---------------------------------------------------------------------------
# Ground-truth incident timing
# ---------------------------------------------------------------------------

DB_CLIMB_ONSET_OFFSET = 650  # s after WINDOW_START: pool_used trend departs baseline
BREACH_LEAD_SECONDS = 250  # EXACTLY 4 m 10 s — the headline causal lead
PAYMENTS_BREACH_OFFSET = DB_CLIMB_ONSET_OFFSET + BREACH_LEAD_SECONDS  # 900 s
BREACH_THRESHOLD_MS = 2400.0

# ---------------------------------------------------------------------------
# Curve parameters (rel_s = seconds since DB pool climb onset)
# ---------------------------------------------------------------------------

POOL_BASELINE, _POOL_SIGMA = 40.0, 2.5  # ~40 ± 5 of pool_max 100
POOL_LIMIT = 100.0
_POOL_RAMP_SECONDS = 220  # exhaustion ~30 s before the latency breach

PAYMENTS_BASELINE, _PAY_SIGMA = 180.0, 7.0  # ~180 ± 20
_PAY_RAMP_START_REL = 150  # latency starts rising once the pool is ~80% used
_PAY_RAMP_SECONDS = 100  # gradual quadratic ease into the breach
_PAY_AT_BREACH = 2455.0
_PAY_PLATEAU = 3200.0
_PAY_PLATEAU_REL = 300

CHECKOUT_BASELINE, _CHK_SIGMA = 150.0, 5.0  # ~150 ± 15
_CHK_RAMP_START_REL = 200  # downstream of payments — degrades last
_CHK_RAMP_SECONDS = 130
_CHK_PLATEAU = 420.0

# Gaussian noise is clamped so the synthetic BASELINE never z-breaches on its
# own — the only anomaly onsets in this recording are the injected ones.
_NOISE_CLAMP_SIGMAS = 2.2


def _noise(rng: random.Random, sigma: float) -> float:
    bound = _NOISE_CLAMP_SIGMAS * sigma
    return max(-bound, min(bound, rng.gauss(0.0, sigma)))


def _smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


# ---------------------------------------------------------------------------
# Per-series value functions
# ---------------------------------------------------------------------------


def pool_used_at(rel_s: float | None, rng: random.Random) -> float:
    """payments-db-primary pool_used: ~40 baseline, linear climb to 100."""
    if rel_s is None or rel_s < 0:
        return float(round(POOL_BASELINE + _noise(rng, _POOL_SIGMA)))
    if rel_s < _POOL_RAMP_SECONDS:
        base = POOL_BASELINE + (POOL_LIMIT - POOL_BASELINE) * rel_s / _POOL_RAMP_SECONDS
        value = base + _noise(rng, 1.5)
        # 100 first appears at exhaustion, never mid-climb.
        return float(round(min(value, POOL_LIMIT - 1.0)))
    return POOL_LIMIT  # exhausted — pinned at pool_max


def payments_p99_at(rel_s: float | None, rng: random.Random) -> float:
    """payments-service p99_ms: ~180 baseline; first >= 2400 at rel 250 exactly."""
    if rel_s is None or rel_s < _PAY_RAMP_START_REL:
        return round(PAYMENTS_BASELINE + _noise(rng, _PAY_SIGMA), 1)
    if rel_s < BREACH_LEAD_SECONDS:
        frac = (rel_s - _PAY_RAMP_START_REL) / _PAY_RAMP_SECONDS
        base = PAYMENTS_BASELINE + (_PAY_AT_BREACH - PAYMENTS_BASELINE) * frac * frac
        value = base + _noise(rng, max(_PAY_SIGMA, 0.01 * base))
        # Guard: the breach sample is AT rel 250, never one sample early.
        return round(min(value, BREACH_THRESHOLD_MS - 40.0), 1)
    if rel_s < _PAY_PLATEAU_REL:
        frac = (rel_s - BREACH_LEAD_SECONDS) / (_PAY_PLATEAU_REL - BREACH_LEAD_SECONDS)
        base = _PAY_AT_BREACH + (_PAY_PLATEAU - _PAY_AT_BREACH) * _smoothstep(frac)
        value = base + _noise(rng, 0.01 * base)
        return round(max(value, BREACH_THRESHOLD_MS + 2.0), 1)
    value = _PAY_PLATEAU + _noise(rng, 40.0)
    return round(max(value, BREACH_THRESHOLD_MS + 2.0), 1)


def checkout_p99_at(rel_s: float | None, rng: random.Random) -> float:
    """checkout-service p99_ms: ~150 baseline; mild downstream degradation."""
    if rel_s is None or rel_s < _CHK_RAMP_START_REL:
        return round(CHECKOUT_BASELINE + _noise(rng, _CHK_SIGMA), 1)
    if rel_s < _CHK_RAMP_START_REL + _CHK_RAMP_SECONDS:
        frac = (rel_s - _CHK_RAMP_START_REL) / _CHK_RAMP_SECONDS
        base = CHECKOUT_BASELINE + (_CHK_PLATEAU - CHECKOUT_BASELINE) * _smoothstep(frac)
        return round(base + _noise(rng, max(_CHK_SIGMA, 0.015 * base)), 1)
    return round(_CHK_PLATEAU + _noise(rng, 8.0), 1)


def sample_services(rel_s: float | None, rng: random.Random) -> list[tuple[str, str, float]]:
    """One sample tick for all 3 services / 4 series, in a FIXED draw order.

    The fixed order keeps a seeded RNG reproducible across generator runs.
    """
    return [
        (PAYMENTS, P99, payments_p99_at(rel_s, rng)),
        (DB_PRIMARY, POOL_USED, pool_used_at(rel_s, rng)),
        (DB_PRIMARY, POOL_MAX, POOL_LIMIT),
        (CHECKOUT, P99, checkout_p99_at(rel_s, rng)),
    ]


# ---------------------------------------------------------------------------
# Full-window generation (the recorded CSV)
# ---------------------------------------------------------------------------


def generate_rows(seed: int = DEFAULT_SEED) -> list[tuple[datetime, str, str, float]]:
    """All rows of the 20-minute incident window, sorted by (ts, service, metric)."""
    rng = random.Random(seed)
    rows: list[tuple[datetime, str, str, float]] = []
    for offset in range(0, WINDOW_SECONDS, STEP_SECONDS):
        ts = WINDOW_START + timedelta(seconds=offset)
        rel_s = offset - DB_CLIMB_ONSET_OFFSET
        for service, metric, value in sample_services(rel_s, rng):
            rows.append((ts, service, metric, value))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


def format_ts(ts: datetime) -> str:
    """ISO8601 UTC on the 5 s grid (no sub-second digits)."""
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_value(metric: str, value: float) -> str:
    """Pool sizes are whole connections; latencies carry one decimal."""
    if metric in (POOL_USED, POOL_MAX):
        return f"{value:.0f}"
    return f"{value:.1f}"
