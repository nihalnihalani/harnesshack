"""Guild session client tests — VERIFIED-LIVE REST contract + keyless honesty.

No credentials, no network: real builders/parsers of libs/guild/session.py.
The live REST contract (app.guild.ai/api, /workspaces/{ws}/sessions,
/sessions/{id}/events) was confirmed live 2026-06-13 (BUILD-STATE.md firing 20).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.worker.agent import TypedEvent
from libs.errors import NotConfiguredError, UnexpectedResponseShapeError
from libs.guild.session import (
    API_BASE,
    _parse_session_id,
    build_audit_event_payload,
    build_session_request,
    create_session,
)


class TestKeyless:
    def test_create_session_raises_b1_without_workspace(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("GUILD_WORKSPACE", raising=False)
        with pytest.raises(NotConfiguredError, match="B1"):
            create_session("inc-1")


class TestRequestShapes:
    def test_api_base_is_the_control_plane(self):
        assert API_BASE == "https://app.guild.ai/api"

    def test_session_request_is_chat_with_initial_prompt(self):
        body = build_session_request("inc-42")
        assert body["session_type"] == "chat"
        assert "inc-42" in body["initial_prompt"]

    def test_audit_event_payload_wraps_typed_event_as_json_mode(self):
        ts = datetime(2026, 6, 12, 14, 15, 0, tzinfo=UTC)
        event = TypedEvent(
            ts=ts,
            incident_id="inc-42",
            event_type="runbook.retrieved",
            payload={"citation": "payments-p99-runbook.md (6cff5947)"},
        )
        assert build_audit_event_payload(event) == {
            "content": {
                "ts": "2026-06-12T14:15:00+00:00",
                "incident_id": "inc-42",
                "event_type": "runbook.retrieved",
                "payload": {"citation": "payments-p99-runbook.md (6cff5947)"},
            },
            "mode": "json",
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
