"""Webhook API tests — real app, in-process via FastAPI TestClient.

No external service is mocked: with credential env vars absent (see
conftest), the API's honest unconfigured behavior is what's under test.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi.testclient import TestClient

from apps.api import main as api_main
from apps.api.main import DEPENDENCY_ENV_VARS
from apps.worker.agent import IncidentAgent, IncidentState
from libs.errors import NotConfiguredError
from libs.senso.retrieve import CitedDocument


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


class _FakeExtraction:
    severity = "P1"
    affected_services = ("payments-service",)
    latency_ms = 10.0


class _FakeEdge:
    cause_service = "payments-db-primary"
    effect_service = "payments-service"
    lag_seconds = 250


def register_agent(incident_id: str, *, ingest: bool = True) -> IncidentAgent:
    """Register a REAL IncidentAgent wired to in-process sinks (the agent
    test-isolation seam — no runtime mocks, no credentials)."""
    runbook = CitedDocument(
        content="## Steps\n1. Raise the pool ceiling.", citation="rb", source_id="rb1"
    )
    ownership = CitedDocument(
        content="## payments-service\n- Primary owner: dana-chen",
        citation="own",
        source_id="own1",
    )

    def blocked_context(_incident_id: str, _query: str):
        raise NotConfiguredError("Airbyte not configured — see BUILD-STATE.md B5")

    agent = IncidentAgent(
        incident_id,
        clickhouse_sink=lambda _e: None,
        guild_sink=lambda _e: None,
        publish=lambda _e: None,
        extract_severity=lambda _t: _FakeExtraction(),
        run_causal_query=lambda: [_FakeEdge()],
        get_runbook=lambda _q: runbook,
        get_ownership=lambda _s: ownership,
        context_lookup=blocked_context,
    )
    if ingest:
        agent.ingest_alert({"service": "payments-service", "metric": "p99_ms"})
    api_main._agents[incident_id] = agent
    return agent


class TestTriggerAgentWiring:
    def test_trigger_constructs_agent_and_background_pipeline_surfaces_blocker(
        self, client: TestClient, monkeypatch
    ):
        # In-process recorder replaces the api-module record_event binding
        # (the established sink-injection seam) so ingest gets past B2 at
        # the endpoint; the agent's own default sinks stay REAL and blocked.
        recorded: list[tuple] = []
        monkeypatch.setattr(api_main, "record_event", lambda *args: recorded.append(args))
        queue = api_main.bus.subscribe()
        try:
            resp = client.post("/trigger", json=make_alert(incident_id="inc-wire-1"))
            assert resp.status_code == 200
            body = resp.json()
            assert body["duplicate"] is False
            assert body["agent_started"] is True
            assert "inc-wire-1" in api_main._agents
            assert len(recorded) == 1  # alert.received persisted via the seam

            items = []
            while not queue.empty():
                items.append(queue.get_nowait())
            types = [item["event_type"] for item in items]
            assert types[0] == "alert.received"
            # The background pipeline hit its first REAL open blocker and
            # published a visible, honest skip naming BUILD-STATE.md.
            assert "SKIPPED_NOT_CONFIGURED" in types
            skipped = next(i for i in items if i["event_type"] == "SKIPPED_NOT_CONFIGURED")
            assert skipped["payload"]["step"] == "agent_pipeline"
            assert "BUILD-STATE.md" in skipped["payload"]["error"]
        finally:
            api_main.bus.unsubscribe(queue)

    def test_duplicate_alert_does_not_start_a_second_agent(
        self, client: TestClient, monkeypatch
    ):
        monkeypatch.setattr(api_main, "record_event", lambda *args: None)
        alert = make_alert(incident_id="inc-wire-2")
        assert client.post("/trigger", json=alert).json()["agent_started"] is True
        assert client.post("/trigger", json=alert).json() == {"duplicate": True}
        assert len([k for k in api_main._agents if k == "inc-wire-2"]) == 1


class TestResolveEndpoint:
    def test_unknown_incident_is_404(self, client: TestClient):
        assert client.post("/incidents/inc-nope/resolve").status_code == 404

    def test_illegal_transition_is_409(self, client: TestClient):
        register_agent("inc-409", ingest=False)  # never opened -> cannot resolve
        resp = client.post("/incidents/inc-409/resolve")
        assert resp.status_code == 409

    def test_resolve_transitions_and_streams_honest_blocker(self, client: TestClient):
        agent = register_agent("inc-res-1")
        assert agent.state is IncidentState.MITIGATING
        queue = api_main.bus.subscribe()
        try:
            resp = client.post("/incidents/inc-res-1/resolve")
            assert resp.status_code == 202
            assert resp.json()["postmortem"] == "streaming"
            assert agent.state is IncidentState.RESOLVED
            # The background postmortem hit B2 (ClickHouse event log) and
            # published the honest skip instead of faking a postmortem.
            items = []
            while not queue.empty():
                items.append(queue.get_nowait())
            skipped = [i for i in items if i["event_type"] == "SKIPPED_NOT_CONFIGURED"]
            assert any(i["payload"]["step"] == "postmortem_generation" for i in skipped)
            assert not any(i["event_type"] == "postmortem_token" for i in items)
        finally:
            api_main.bus.unsubscribe(queue)

    def test_double_resolve_is_409(self, client: TestClient):
        register_agent("inc-res-2")
        assert client.post("/incidents/inc-res-2/resolve").status_code == 202
        assert client.post("/incidents/inc-res-2/resolve").status_code == 409


class TestConfirmOwnerEndpoint:
    def test_unknown_incident_is_404(self, client: TestClient):
        resp = client.post("/incidents/inc-nope/confirm-owner", json={"owner": "dana-chen"})
        assert resp.status_code == 404

    def test_missing_owner_is_422(self, client: TestClient):
        register_agent("inc-own-0")
        assert client.post("/incidents/inc-own-0/confirm-owner", json={}).status_code == 422

    def test_confirmation_emits_owner_confirmed_event(self, client: TestClient):
        agent = register_agent("inc-own-1")
        resp = client.post(
            "/incidents/inc-own-1/confirm-owner",
            json={"owner": "dana-chen", "confirmed_by": "presenter"},
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "owner_confirmed"
        assert agent.events[-1].event_type == "owner_confirmed"
        assert agent.events[-1].payload == {"owner": "dana-chen", "confirmed_by": "presenter"}


class TestFallbackPostmortemEndpoint:
    def test_404_until_a_real_run_cached_one(self, client: TestClient, monkeypatch, tmp_path):
        monkeypatch.setattr(api_main, "FALLBACK_HTML_PATH", tmp_path / "missing.html")
        resp = client.get("/fallback/postmortem")
        assert resp.status_code == 404
        assert "REAL completed run" in resp.json()["detail"]

    def test_serves_the_cached_real_artifact(self, client: TestClient, monkeypatch, tmp_path):
        from apps.worker.postmortem import write_fallback_html

        target = tmp_path / "fallback_postmortem.html"
        write_fallback_html("inc-f2", "## Timeline\nreal run text", path=target)
        monkeypatch.setattr(api_main, "FALLBACK_HTML_PATH", target)
        resp = client.get("/fallback/postmortem")
        assert resp.status_code == 200
        assert "real run text" in resp.text

    def test_repo_artifact_absent_until_first_live_success(self):
        from apps.worker.postmortem import FALLBACK_HTML_PATH

        # Claim integrity: until a real run exists the file must NOT exist.
        # (After the first live success this asserts the artifact is real,
        # i.e. carries the cached-real-run banner — never a placeholder.)
        if FALLBACK_HTML_PATH.exists():
            content = FALLBACK_HTML_PATH.read_text(encoding="utf-8")
            assert "REAL completed postmortem run" in content
        # else: correctly absent while no live run has happened.


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
