"""Incident state machine + typed event tests (apps/worker/agent.py)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.worker.agent import (
    LEGAL_TRANSITIONS,
    IllegalTransitionError,
    IncidentState,
    TypedEvent,
    validate_transition,
)


class TestLegalTransitions:
    def test_investigating_to_mitigating(self):
        assert (
            validate_transition(IncidentState.INVESTIGATING, IncidentState.MITIGATING)
            is IncidentState.MITIGATING
        )

    def test_mitigating_to_resolved(self):
        assert (
            validate_transition(IncidentState.MITIGATING, IncidentState.RESOLVED)
            is IncidentState.RESOLVED
        )

    def test_accepts_raw_string_values(self):
        assert validate_transition("INVESTIGATING", "MITIGATING") is IncidentState.MITIGATING


class TestIllegalTransitions:
    @pytest.mark.parametrize(
        ("current", "new"),
        [
            (IncidentState.INVESTIGATING, IncidentState.RESOLVED),  # no skipping
            (IncidentState.MITIGATING, IncidentState.INVESTIGATING),  # no backwards
            (IncidentState.RESOLVED, IncidentState.INVESTIGATING),  # terminal
            (IncidentState.RESOLVED, IncidentState.MITIGATING),  # terminal
            (IncidentState.INVESTIGATING, IncidentState.INVESTIGATING),  # no self
            (IncidentState.MITIGATING, IncidentState.MITIGATING),  # no self
            (IncidentState.RESOLVED, IncidentState.RESOLVED),  # no self
        ],
    )
    def test_raises(self, current: IncidentState, new: IncidentState):
        with pytest.raises(IllegalTransitionError):
            validate_transition(current, new)

    def test_error_message_names_both_states(self):
        with pytest.raises(IllegalTransitionError, match="INVESTIGATING -> RESOLVED"):
            validate_transition(IncidentState.INVESTIGATING, IncidentState.RESOLVED)

    def test_unknown_state_rejected(self):
        with pytest.raises(ValueError):
            validate_transition("INVESTIGATING", "ESCALATED")


class TestStateMachineShape:
    def test_every_state_has_transition_rules(self):
        assert set(LEGAL_TRANSITIONS) == set(IncidentState)

    def test_resolved_is_terminal(self):
        assert LEGAL_TRANSITIONS[IncidentState.RESOLVED] == frozenset()


class TestTypedEvent:
    def test_fields(self):
        ts = datetime.now(UTC)
        event = TypedEvent(
            ts=ts,
            incident_id="inc-123",
            event_type="alert.received",
            payload={"service": "payments"},
        )
        assert event.ts is ts
        assert event.incident_id == "inc-123"
        assert event.event_type == "alert.received"
        assert event.payload == {"service": "payments"}

    def test_immutable(self):
        event = TypedEvent(
            ts=datetime.now(UTC), incident_id="inc-1", event_type="x"
        )
        with pytest.raises(AttributeError):
            event.incident_id = "inc-2"  # type: ignore[misc]

    def test_payload_defaults_to_empty_dict(self):
        event = TypedEvent(
            ts=datetime.now(UTC), incident_id="inc-1", event_type="x"
        )
        assert event.payload == {}
