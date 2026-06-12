"""Webhook security — bearer auth + per-IP token-bucket rate limit.

Same no-mock posture as test_api.py: the real app runs in-process and the
tests control the ENVIRONMENT (WEBHOOK_AUTH_TOKEN / RATE_LIMIT_PER_MINUTE),
which is the real configuration surface.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from apps.api import main as api_main
from apps.api.main import TokenBucketRateLimiter

TOKEN = "test-webhook-token-0123456789abcdef"


def make_alert(**overrides) -> dict:
    alert = {
        "service": "payments",
        "metric": "p99_latency_ms",
        "value": 2412.5,
        "timestamp": "2026-06-12T10:00:00Z",
        "incident_id": f"inc-{uuid.uuid4().hex[:8]}",
    }
    alert.update(overrides)
    return alert


class TestBearerAuth:
    def test_when_token_set_missing_auth_is_401(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", TOKEN)
        resp = client.post("/trigger", json=make_alert())
        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    def test_when_token_set_wrong_token_is_401(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", TOKEN)
        resp = client.post(
            "/trigger",
            json=make_alert(),
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    def test_when_token_set_correct_token_passes_auth(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", TOKEN)
        # In-process recorder via the established sink-injection seam so the
        # request gets past the B2 blocker and proves a full 200 with auth.
        monkeypatch.setattr(api_main, "record_event", lambda *args: None)
        resp = client.post(
            "/trigger",
            json=make_alert(),
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert resp.status_code == 200
        assert resp.json()["duplicate"] is False

    def test_incidents_endpoints_are_protected_too(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", TOKEN)
        assert client.post("/incidents/inc-x/resolve").status_code == 401
        assert (
            client.post(
                "/incidents/inc-x/confirm-owner", json={"owner": "dana-chen"}
            ).status_code
            == 401
        )
        # With the right token, auth passes and the handler answers (404:
        # unknown incident) — proving 401 came from auth, not the handler.
        headers = {"Authorization": f"Bearer {TOKEN}"}
        assert client.post("/incidents/inc-x/resolve", headers=headers).status_code == 404

    def test_read_endpoints_stay_open(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", TOKEN)
        assert client.get("/health").status_code == 200
        assert client.get("/fallback/postmortem").status_code in (200, 404)

    def test_when_token_unset_no_auth_required(self, client: TestClient):
        # Local-dev posture: keyless works (announced loudly at startup);
        # the request proceeds to the honest 503 (B2 open), never a 401.
        assert client.post("/trigger", json=make_alert()).status_code == 503

    def test_startup_logs_loud_warning_when_auth_disabled(self, caplog):
        with caplog.at_level("WARNING", logger="incidentsherpa.api"):
            with TestClient(api_main.app):  # context manager runs the lifespan
                pass
        assert any(
            "webhook auth DISABLED — set WEBHOOK_AUTH_TOKEN in production" in r.message
            for r in caplog.records
        )


class TestRateLimit:
    def test_429_with_retry_after_when_bucket_empty(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
        for _ in range(3):
            resp = client.post("/trigger", json=make_alert())
            assert resp.status_code == 503  # allowed through (honest B2 state)
        resp = client.post("/trigger", json=make_alert())
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) >= 1
        assert "rate limit" in resp.json()["detail"]

    def test_limit_spans_all_protected_post_endpoints(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
        client.post("/trigger", json=make_alert())
        client.post("/incidents/inc-x/resolve")
        assert client.post("/incidents/inc-x/resolve").status_code == 429

    def test_get_endpoints_are_never_rate_limited(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
        client.post("/trigger", json=make_alert())  # drains the bucket
        for _ in range(5):
            assert client.get("/health").status_code == 200

    def test_429_applies_even_with_valid_auth_token(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("WEBHOOK_AUTH_TOKEN", TOKEN)
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
        headers = {"Authorization": f"Bearer {TOKEN}"}
        client.post("/trigger", json=make_alert(), headers=headers)
        assert client.post("/trigger", json=make_alert(), headers=headers).status_code == 429

    def test_invalid_env_value_falls_back_to_default(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "not-a-number")
        assert client.post("/trigger", json=make_alert()).status_code == 503  # not 429/500


class TestTokenBucketUnit:
    """Deterministic bucket math via the injected `now` clock."""

    def test_burst_capacity_equals_limit(self):
        limiter = TokenBucketRateLimiter()
        assert all(limiter.acquire("ip", 5, now=100.0) is None for _ in range(5))
        assert limiter.acquire("ip", 5, now=100.0) is not None

    def test_refills_at_limit_per_minute(self):
        limiter = TokenBucketRateLimiter()
        for _ in range(60):
            limiter.acquire("ip", 60, now=100.0)
        retry_after = limiter.acquire("ip", 60, now=100.0)
        assert retry_after is not None and 0 < retry_after <= 1.0
        # One token refills per second at 60/min.
        assert limiter.acquire("ip", 60, now=101.1) is None

    def test_buckets_are_per_ip(self):
        limiter = TokenBucketRateLimiter()
        assert limiter.acquire("a", 1, now=0.0) is None
        assert limiter.acquire("a", 1, now=0.0) is not None
        assert limiter.acquire("b", 1, now=0.0) is None  # other IP unaffected

    def test_tokens_never_exceed_capacity(self):
        limiter = TokenBucketRateLimiter()
        limiter.acquire("ip", 2, now=0.0)
        # A long idle period must not bank more than `limit` tokens.
        assert limiter.acquire("ip", 2, now=10_000.0) is None
        assert limiter.acquire("ip", 2, now=10_000.0) is None
        assert limiter.acquire("ip", 2, now=10_000.0) is not None
