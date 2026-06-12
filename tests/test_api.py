"""Webhook API tests — real app, in-process via FastAPI TestClient.

No external service is mocked: with credential env vars absent (see
conftest), the API's honest unconfigured behavior is what's under test.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi.testclient import TestClient

from apps.api.main import DEPENDENCY_ENV_VARS


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


class TestTriggerValidation:
    def test_missing_required_field_is_422(self, client: TestClient):
        bad = make_alert()
        del bad["metric"]
        assert client.post("/trigger", json=bad).status_code == 422

    def test_non_numeric_value_is_422(self, client: TestClient):
        assert (
            client.post("/trigger", json=make_alert(value="not-a-number")).status_code
            == 422
        )

    def test_bad_timestamp_is_422(self, client: TestClient):
        assert (
            client.post("/trigger", json=make_alert(timestamp="yesterday-ish")).status_code
            == 422
        )

    def test_empty_service_is_422(self, client: TestClient):
        assert client.post("/trigger", json=make_alert(service="")).status_code == 422


class TestTriggerUnconfigured:
    def test_valid_alert_is_503_while_clickhouse_blocked(self, client: TestClient):
        resp = client.post("/trigger", json=make_alert())
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert "ClickHouse not configured" in detail
        assert "BUILD-STATE.md" in detail


class TestIdempotency:
    def test_second_identical_payload_is_duplicate(self, client: TestClient):
        alert = make_alert()
        first = client.post("/trigger", json=alert)
        assert first.status_code == 503  # honest: B2 open, nothing persisted
        second = client.post("/trigger", json=alert)
        assert second.status_code == 200
        assert second.json() == {"duplicate": True}

    def test_idempotency_key_header_wins_over_payload(self, client: TestClient):
        key = f"key-{uuid.uuid4().hex}"
        client.post("/trigger", json=make_alert(), headers={"Idempotency-Key": key})
        # Different payload, same key -> duplicate.
        resp = client.post(
            "/trigger", json=make_alert(), headers={"Idempotency-Key": key}
        )
        assert resp.status_code == 200
        assert resp.json() == {"duplicate": True}

    def test_distinct_alerts_are_not_duplicates(self, client: TestClient):
        assert client.post("/trigger", json=make_alert()).status_code == 503
        assert client.post("/trigger", json=make_alert()).status_code == 503


class TestHealth:
    EXPECTED_DEPS = {
        "clickhouse",
        "langfuse",
        "pioneer",
        "senso",
        "airbyte",
        "composio",
        "guild",
        "anthropic",
    }

    def test_all_dependencies_reported(self, client: TestClient):
        body = client.get("/health").json()
        assert set(body["dependencies"]) == self.EXPECTED_DEPS
        assert self.EXPECTED_DEPS == set(DEPENDENCY_ENV_VARS)

    def test_all_blocked_when_env_empty(self, client: TestClient):
        body = client.get("/health").json()
        for name, dep in body["dependencies"].items():
            assert dep["status"] == "blocked", f"{name} must be blocked with empty env"
            assert dep["missing_env"], f"{name} must name its missing env vars"
        assert body["status"] == "degraded"
        assert set(body["blocked"]) == self.EXPECTED_DEPS

    def test_configured_when_env_present(self, client: TestClient, monkeypatch):
        # Presence-check only (real config surface) — no liveness claim made.
        monkeypatch.setenv("SENSO_API_KEY", "present-for-presence-check")
        body = client.get("/health").json()
        assert body["dependencies"]["senso"] == {"status": "configured", "missing_env": []}
        assert "senso" not in body["blocked"]
        assert body["status"] == "degraded"  # others still blocked


class TestEventsSSE:
    """Drives the REAL /events endpoint coroutine with a controlled ASGI
    receive channel (TestClient cannot consume unbounded streams — it runs
    the app to completion). The endpoint, EventBus, and SSE framing under
    test are the production objects, unmodified."""

    def test_stream_headers_framing_and_disconnect(self):
        from starlette.requests import Request

        from apps.api.main import bus, events

        async def scenario():
            calls = {"n": 0}

            async def receive():
                calls["n"] += 1
                # First is_disconnected() poll: still connected; then the
                # client goes away and the generator must exit cleanly.
                if calls["n"] >= 2:
                    return {"type": "http.disconnect"}
                return {"type": "http.request", "body": b"", "more_body": False}

            scope = {"type": "http", "method": "GET", "path": "/events", "headers": [],
                     "query_string": b""}
            resp = await events(Request(scope, receive))

            assert resp.status_code == 200
            assert resp.media_type == "text/event-stream"
            assert resp.headers["cache-control"] == "no-cache"
            assert resp.headers["x-accel-buffering"] == "no"

            # Publish through the real in-process bus while subscribed.
            bus.publish({"event_type": "alert.received", "incident_id": "inc-sse"})

            chunks = [chunk async for chunk in resp.body_iterator]
            assert chunks[0] == ": connected\n\n"
            assert chunks[1].startswith("data: ")
            assert json.loads(chunks[1][len("data: "):].strip()) == {
                "event_type": "alert.received",
                "incident_id": "inc-sse",
            }
            assert len(chunks) == 2  # disconnect ended the stream
            assert len(bus._subscribers) == 0  # unsubscribed on exit

        asyncio.run(scenario())
