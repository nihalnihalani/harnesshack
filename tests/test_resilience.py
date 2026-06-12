"""Resilience layer tests — retries, DegradedError typing, circuit breaker.

No credentials and no network: callables are in-process and raise REAL httpx
exception types. This is test isolation of real retry/breaker code, not a
runtime mock of any service.
"""

from __future__ import annotations

import httpx
import pytest

from libs.errors import NotConfiguredError
from libs.resilience import (
    CircuitBreaker,
    DegradedError,
    get_breaker,
    reset_breakers,
    with_retries,
)


@pytest.fixture(autouse=True)
def fresh_breakers():
    reset_breakers()
    yield
    reset_breakers()


def _no_sleep(_seconds: float) -> None:
    return None


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example.test/x")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


class TestWithRetries:
    def test_success_passthrough(self):
        assert with_retries(lambda: 42, service="svc") == 42

    def test_retries_transient_then_succeeds(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ConnectError("refused")
            return "ok"

        assert with_retries(flaky, service="svc", sleep=_no_sleep) == "ok"
        assert calls["n"] == 3

    def test_exhausted_retries_raise_degraded_with_service_and_cause(self):
        def always_down():
            raise httpx.ConnectTimeout("timed out")

        with pytest.raises(DegradedError) as exc_info:
            with_retries(always_down, service="senso", attempts=3, sleep=_no_sleep)
        err = exc_info.value
        assert err.service == "senso"
        assert isinstance(err.cause, httpx.ConnectTimeout)
        assert "senso" in str(err)

    def test_retryable_http_statuses_are_retried(self):
        calls = {"n": 0}

        def flaky_503():
            calls["n"] += 1
            if calls["n"] < 2:
                raise _http_status_error(503)
            return "recovered"

        assert with_retries(flaky_503, service="svc", sleep=_no_sleep) == "recovered"
        assert calls["n"] == 2

    def test_non_transient_http_status_fails_fast_as_degraded(self):
        calls = {"n": 0}

        def not_found():
            calls["n"] += 1
            raise _http_status_error(404)

        with pytest.raises(DegradedError):
            with_retries(not_found, service="svc", attempts=5, sleep=_no_sleep)
        assert calls["n"] == 1  # no retry for a 404

    def test_not_configured_error_passes_through_untouched(self):
        def blocked():
            raise NotConfiguredError("Senso not configured — see BUILD-STATE.md B6")

        with pytest.raises(NotConfiguredError, match="B6"):
            with_retries(blocked, service="senso", sleep=_no_sleep)
        # And it never trips the breaker.
        assert get_breaker("senso").state == "closed"

    def test_backoff_is_exponential(self):
        sleeps: list[float] = []

        def always_down():
            raise httpx.ConnectError("refused")

        with pytest.raises(DegradedError):
            with_retries(
                always_down, service="svc", attempts=3, backoff_base=0.5, sleep=sleeps.append
            )
        assert sleeps == [0.5, 1.0]


class TestCircuitBreaker:
    def test_opens_after_consecutive_failures_and_blocks(self):
        def always_down():
            raise httpx.ConnectError("refused")

        calls = {"n": 0}

        def counting_down():
            calls["n"] += 1
            raise httpx.ConnectError("refused")

        get_breaker("guild", failure_threshold=2, cooldown_seconds=60.0)
        for _ in range(2):
            with pytest.raises(DegradedError):
                with_retries(counting_down, service="guild", attempts=1, sleep=_no_sleep)
        before = calls["n"]
        # Circuit now open: fn is NOT called, DegradedError is immediate.
        with pytest.raises(DegradedError, match="circuit open"):
            with_retries(counting_down, service="guild", attempts=1, sleep=_no_sleep)
        assert calls["n"] == before

    def test_half_open_probe_after_cooldown_then_close_on_success(self):
        now = {"t": 0.0}
        breaker = CircuitBreaker(
            "svc", failure_threshold=1, cooldown_seconds=30.0, clock=lambda: now["t"]
        )
        breaker.record_failure()
        assert breaker.state == "open"
        assert not breaker.allow()
        now["t"] = 31.0
        assert breaker.state == "half_open"
        assert breaker.allow()  # single probe permitted
        breaker.record_success()
        assert breaker.state == "closed"

    def test_half_open_probe_failure_reopens(self):
        now = {"t": 0.0}
        breaker = CircuitBreaker(
            "svc", failure_threshold=1, cooldown_seconds=30.0, clock=lambda: now["t"]
        )
        breaker.record_failure()
        now["t"] = 31.0
        assert breaker.allow()
        breaker.record_failure()  # probe failed
        assert breaker.state == "open"
        assert not breaker.allow()

    def test_success_resets_consecutive_failure_count(self):
        breaker = CircuitBreaker("svc", failure_threshold=2)
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        assert breaker.state == "closed"

    def test_breakers_are_per_service(self):
        def always_down():
            raise httpx.ConnectError("refused")

        get_breaker("svc-a", failure_threshold=1)
        with pytest.raises(DegradedError):
            with_retries(always_down, service="svc-a", attempts=1, sleep=_no_sleep)
        assert get_breaker("svc-a").state == "open"
        assert get_breaker("svc-b").state == "closed"
        assert with_retries(lambda: "fine", service="svc-b") == "fine"
