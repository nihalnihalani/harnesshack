"""Resilience layer — bounded retries + per-service circuit breaker (Phase 8).

`with_retries(fn, *, service, ...)` retries TRANSIENT failures (connection /
timeout errors, retryable HTTP statuses) with exponential backoff. On final
failure it raises a typed DegradedError carrying the service name and the
underlying cause — callers convert that into an explicit DEGRADED TypedEvent
in the incident log. Nothing is ever swallowed and no substitute data is ever
returned on any path.

NotConfiguredError passes through UNTOUCHED: a missing credential is a
BUILD-STATE blocker (B1/B2/B4/B6/B7...), not a degradation — retrying it is
noise and converting it would hide which blocker is open. It also never trips
the breaker.

Circuit breaker: per-service, opens after `failure_threshold` CONSECUTIVE
failures, blocks calls (immediate DegradedError) for `cooldown_seconds`, then
allows a single half-open probe; probe success closes the circuit, probe
failure re-opens it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from libs.errors import NotConfiguredError

DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE = 0.5
DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_COOLDOWN_SECONDS = 30.0

# HTTP statuses worth retrying: timeouts, throttling, server-side faults.
TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

# Default retryable exception classes. httpx.TransportError covers connect
# errors, timeouts, and broken reads; HTTPStatusError is additionally gated
# on TRANSIENT_STATUS_CODES (a 404 is not transient and never retried).
DEFAULT_RETRY_ON: tuple[type[BaseException], ...] = (
    httpx.TransportError,
    httpx.HTTPStatusError,
)


class DegradedError(RuntimeError):
    """A service is degraded: retries exhausted or its circuit is open.

    Carries `service` and `cause` so the caller can emit an honest DEGRADED
    typed event naming exactly what failed — never a silent fallback.
    """

    def __init__(self, service: str, message: str, cause: BaseException | None = None) -> None:
        super().__init__(f"{service} degraded: {message}")
        self.service = service
        self.cause = cause


class CircuitBreaker:
    """Per-service breaker: open after N consecutive failures, half-open probe."""

    def __init__(
        self,
        service: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {failure_threshold}")
        self.service = service
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if self._clock() - self._opened_at >= self.cooldown_seconds:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        """True when a call may proceed (closed, or half-open single probe)."""
        return self.state != "open"

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._opened_at = self._clock()


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(service: str, **kwargs: Any) -> CircuitBreaker:
    """Return (creating if needed) the process-wide breaker for `service`."""
    breaker = _breakers.get(service)
    if breaker is None:
        breaker = CircuitBreaker(service, **kwargs)
        _breakers[service] = breaker
    return breaker


def reset_breakers() -> None:
    """Forget all breaker state (test isolation; also useful after redeploys)."""
    _breakers.clear()


def _is_retryable(exc: BaseException, retry_on: tuple[type[BaseException], ...]) -> bool:
    if not isinstance(exc, retry_on):
        return False
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in TRANSIENT_STATUS_CODES
    return True


def with_retries[T](
    fn: Callable[[], T],
    *,
    service: str,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    retry_on: tuple[type[BaseException], ...] = DEFAULT_RETRY_ON,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `fn` with bounded retries + the per-service circuit breaker.

    - Transient failures (instances of `retry_on`; HTTPStatusError only for
      TRANSIENT_STATUS_CODES) are retried up to `attempts` times with
      exponential backoff (backoff_base * 2**attempt_index seconds).
    - Final failure — and any NON-transient failure, immediately — raises
      DegradedError(service, cause) and records a breaker failure.
    - NotConfiguredError propagates untouched (open blocker, not degradation).
    - An OPEN circuit raises DegradedError without calling `fn`; after the
      cooldown one half-open probe is let through.
    """
    if attempts < 1:
        raise ValueError(f"attempts must be >= 1, got {attempts}")
    breaker = get_breaker(service)
    if not breaker.allow():
        raise DegradedError(
            service,
            f"circuit open after {breaker.failure_threshold} consecutive failures; "
            f"retrying after {breaker.cooldown_seconds}s cooldown",
        )
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = fn()
        except NotConfiguredError:
            raise  # blocker, not degradation — never converted, never retried
        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc, retry_on) and attempt < attempts:
                sleep(backoff_base * (2 ** (attempt - 1)))
                continue
            breaker.record_failure()
            raise DegradedError(
                service,
                f"failed after {attempt} attempt(s): {type(exc).__name__}: {exc}",
                cause=exc,
            ) from exc
        breaker.record_success()
        return result
    # Unreachable: every loop path returns or raises.
    raise DegradedError(service, f"failed: {last_exc}", cause=last_exc)  # pragma: no cover


__all__ = [
    "DEFAULT_RETRY_ON",
    "TRANSIENT_STATUS_CODES",
    "CircuitBreaker",
    "DegradedError",
    "get_breaker",
    "reset_breakers",
    "with_retries",
]
