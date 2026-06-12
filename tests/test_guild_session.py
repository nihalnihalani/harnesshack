"""Guild REST session client tests — request shapes + keyless honesty.

No credentials, no network: real builders/parsers of libs/guild/session.py.
Live endpoint confirmation happens on-site when B1 lands (descope.md).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.worker.agent import TypedEvent
from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.guild.session import (
    SESSIONS_PATH,
    _parse_session_id,
    append_audit_event,
    build_audit_event_payload,
    build_session_request,
    close_session,
    create_session,
)


class TestKeyless:
    def test_create_session_raises_b1(self):
        with pytest.raises(NotConfiguredError, match="B1"):
            create_session("inc-1")

    def test_append_audit_event_raises_b1(self):
        event = TypedEvent(
            ts=datetime.now(UTC), incident_id="inc-1", event_type="state.transition"
        )
        with pytest.raises(NotConfiguredError, match="B1"):
            append_audit_event("sess-1", event)

    def test_close_session_raises_b1(self):
        with pytest.raises(NotConfiguredError, match="B1"):
            close_session("sess-1")

    def test_partial_config_names_the_missing_var(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GUILD_API_BASE", "https://api.guild.test")
        with pytest.raises(NotConfiguredError, match="GUILD_PAT"):
            create_session("inc-1")


class TestRequestShapes:
    def test_sessions_path_is_the_descope_convention(self):
        assert SESSIONS_PATH == "/v1/sessions"

    def test_session_request_names_the_incident(self):
        body = build_session_request("inc-42")
        assert body["name"] == "incident-inc-42"
        assert body["metadata"]["incident_id"] == "inc-42"

    def test_audit_event_payload_is_the_typed_event_verbatim(self):
        ts = datetime(2026, 6, 12, 14, 15, 0, tzinfo=UTC)
        event = TypedEvent(
            ts=ts,
            incident_id="inc-42",
            event_type="runbook.retrieved",
            payload={"citation": "Runbook: payments-service p99 latency breach"},
        )
        assert build_audit_event_payload(event) == {
            "ts": "2026-06-12T14:15:00+00:00",
            "incident_id": "inc-42",
            "event_type": "runbook.retrieved",
            "payload": {"citation": "Runbook: payments-service p99 latency breach"},
        }


class TestSessionIdParse:
    @pytest.mark.parametrize(
        "data",
        [
            {"id": "sess_1"},
            {"session_id": "sess_1"},
            {"sessionId": "sess_1"},
            {"data": {"id": "sess_1"}},
            {"session": {"id": "sess_1"}},
        ],
    )
    def test_tolerant_locations(self, data):
        assert _parse_session_id(data) == "sess_1"

    def test_numeric_id_stringified(self):
        assert _parse_session_id({"id": 7}) == "7"

    def test_missing_id_fails_loudly(self):
        with pytest.raises(UnexpectedResponseShapeError):
            _parse_session_id({"ok": True})
