"""Choke-point enforcement tests — libs/composio_actions/send.py.

No credentials, no network. Screeners injected here return REAL ScreenResult
values (or deliberately wrong types, to prove the choke point refuses them)
— test isolation of real enforcement code, not runtime mocks of Composio:
the moment an allowed send reaches execution it honestly raises
NotConfiguredError(B7).
"""

from __future__ import annotations

import inspect

import pytest

import libs.composio_actions.send as send_module
from libs.composio_actions.send import (
    JIRA_ACTION,
    OWNER_SUGGESTION_WORDING,
    SLACK_ACTION,
    BlockedContentError,
    GuardrailBypassError,
    _screened_send,
    build_jira_followup_text,
    build_slack_update_text,
    create_jira_followup,
    post_slack_update,
    reset_idempotency_registry,
)
from libs.errors import NotConfiguredError
from libs.pioneer.gliguard import ScreenResult
from libs.resilience import reset_breakers


@pytest.fixture(autouse=True)
def fresh_state():
    reset_idempotency_registry()
    reset_breakers()
    yield
    reset_idempotency_registry()
    reset_breakers()


class Incident:
    incident_id = "inc-test-1"
    state = "MITIGATING"


def allow(text: str) -> ScreenResult:
    return ScreenResult(allowed=True, categories=(), latency_ms=12.5)


def refuse(text: str) -> ScreenResult:
    return ScreenResult(allowed=False, categories=("harm",), latency_ms=9.1)


class TestGuardrailScreening:
    def test_refusal_raises_blocked_and_emits_event(self):
        emitted: list[tuple[str, dict]] = []
        with pytest.raises(BlockedContentError):
            _screened_send(
                SLACK_ACTION,
                "bad text",
                "inc-1:MITIGATING",
                screener=refuse,
                emit=lambda t, p: emitted.append((t, p)),
            )
        assert [t for t, _ in emitted] == ["BLOCKED_BY_GUARDRAIL"]
        event_type, payload = emitted[0]
        assert payload["action"] == SLACK_ACTION
        assert payload["categories"] == ["harm"]

    def test_without_a_real_screen_result_sending_is_refused(self):
        # A screener returning anything but a ScreenResult — including a
        # truthy dict that LOOKS like a verdict — must raise, never send.
        for bogus in (None, True, {"allowed": True}, "allowed"):
            with pytest.raises(GuardrailBypassError):
                _screened_send(
                    SLACK_ACTION,
                    "text",
                    "inc-1:MITIGATING",
                    screener=lambda _t, b=bogus: b,
                )

    def test_keyless_screen_path_raises_b4_before_any_send(self):
        # Default screener is the REAL GLiGuard client: keyless it raises B4.
        with pytest.raises(NotConfiguredError, match="B4"):
            _screened_send(SLACK_ACTION, "text", "inc-1:MITIGATING")


class TestKeylessHonesty:
    def test_allowed_send_raises_b7_without_composio_key(self):
        with pytest.raises(NotConfiguredError, match="B7"):
            _screened_send(SLACK_ACTION, "text", "inc-1:MITIGATING", screener=allow)

    def test_public_senders_surface_b7_keyless(self):
        with pytest.raises(NotConfiguredError, match="B7"):
            post_slack_update(Incident(), "db pool -> payments", "dana-chen", screener=allow)
        with pytest.raises(NotConfiguredError, match="B7"):
            create_jira_followup(Incident(), "dana-chen", screener=allow)


class TestIdempotency:
    def test_duplicate_scope_action_is_deduped(self):
        # Simulate a prior successful send for this incident_id+state+action.
        send_module._sent_registry.add(("inc-1:MITIGATING", SLACK_ACTION))
        result = _screened_send(SLACK_ACTION, "text", "inc-1:MITIGATING", screener=allow)
        assert result == {
            "status": "duplicate",
            "action": SLACK_ACTION,
            "idempotency_scope": "inc-1:MITIGATING",
        }

    def test_different_action_same_scope_is_not_deduped(self):
        send_module._sent_registry.add(("inc-1:MITIGATING", SLACK_ACTION))
        with pytest.raises(NotConfiguredError, match="B7"):  # proceeds to execute
            _screened_send(JIRA_ACTION, "text", "inc-1:MITIGATING", screener=allow)

    def test_failed_send_is_not_registered(self):
        with pytest.raises(NotConfiguredError):
            _screened_send(SLACK_ACTION, "text", "inc-1:MITIGATING", screener=allow)
        assert ("inc-1:MITIGATING", SLACK_ACTION) not in send_module._sent_registry


class TestOwnerWording:
    def test_slack_text_says_suggested_never_assigned(self):
        text = build_slack_update_text(
            Incident(), "payments-db-primary preceded payments-service by 250s", "dana-chen"
        )
        assert f"{OWNER_SUGGESTION_WORDING}: dana-chen" in text
        assert "assign" not in text.lower()

    def test_jira_text_says_suggested_never_auto_assigns(self):
        text = build_jira_followup_text(Incident(), "dana-chen")
        assert f"{OWNER_SUGGESTION_WORDING}: dana-chen" in text
        assert "A human must confirm" in text


class TestChokePointStructure:
    """Module-structure enforcement: no send path exists besides _screened_send."""

    @staticmethod
    def _module_functions() -> dict[str, object]:
        return {
            name: obj
            for name, obj in vars(send_module).items()
            if inspect.isfunction(obj) and obj.__module__ == send_module.__name__
        }

    def test_only_the_two_public_senders_exist(self):
        public_senders = {
            name
            for name, fn in self._module_functions().items()
            if not name.startswith("_") and "_screened_send(" in inspect.getsource(fn)
        }
        assert public_senders == {"post_slack_update", "create_jira_followup"}

    def test_only_the_choke_point_touches_the_composio_session(self):
        touchers = {
            name
            for name, fn in self._module_functions().items()
            if name != "_get_session" and "_get_session(" in inspect.getsource(fn)
        }
        assert touchers == {"_screened_send"}, (
            "the Composio session may ONLY be reached from _screened_send"
        )

    def test_no_public_function_executes_directly(self):
        for name, fn in self._module_functions().items():
            if name.startswith("_"):
                continue
            source = inspect.getsource(fn)
            assert "tools.execute" not in source, f"{name} bypasses the choke point"

    def test_public_api_exports_no_raw_send_primitive(self):
        assert "_screened_send" not in send_module.__all__
        assert "_get_session" not in send_module.__all__

    def test_module_never_uses_deprecated_initiate(self):
        source = inspect.getsource(send_module)
        assert ".initiate(" not in source  # link(), never initiate()
