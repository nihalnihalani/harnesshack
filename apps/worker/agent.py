"""Incident agent domain model — Phase 1 skeleton.

ONLY the typed-event dataclass and the incident state machine live here at
this phase. The IncidentAgent business logic (GLiNER2 extraction, causal
SQL, runbook retrieval, postmortem) lands in Phase 3. Everything in this
file is real and tested NOW (tests/test_state_machine.py).

The event log IS the product: every state transition becomes a TypedEvent
persisted to ClickHouse `events` and the Guild session audit log. If an
action isn't in the log, it didn't happen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class IncidentState(StrEnum):
    """Incident lifecycle states (CLAUDE.md core domain model)."""

    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"


class IllegalTransitionError(ValueError):
    """Raised on any state transition not in LEGAL_TRANSITIONS."""


# Strict forward-only lifecycle: INVESTIGATING -> MITIGATING -> RESOLVED.
# No skips (an unmitigated incident cannot resolve), no backwards moves,
# no self-transitions, and RESOLVED is terminal.
LEGAL_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    IncidentState.INVESTIGATING: frozenset({IncidentState.MITIGATING}),
    IncidentState.MITIGATING: frozenset({IncidentState.RESOLVED}),
    IncidentState.RESOLVED: frozenset(),
}


def validate_transition(current: IncidentState, new: IncidentState) -> IncidentState:
    """Validate a state transition; return the new state or raise.

    Raises IllegalTransitionError for any move not in LEGAL_TRANSITIONS —
    illegal transitions must fail loudly, never be silently coerced.
    """
    current = IncidentState(current)
    new = IncidentState(new)
    if new not in LEGAL_TRANSITIONS[current]:
        legal = ", ".join(s.value for s in LEGAL_TRANSITIONS[current]) or "none (terminal)"
        raise IllegalTransitionError(
            f"Illegal incident state transition {current.value} -> {new.value}; "
            f"legal next states from {current.value}: {legal}"
        )
    return new


@dataclass(frozen=True)
class TypedEvent:
    """One immutable entry in the typed event log.

    Serialized verbatim into ClickHouse `events` (libs.clickhouse.record_event)
    and, from Phase 3 on, the Guild session audit log. The postmortem is
    generated FROM these events, never reconstructed from chat.
    """

    ts: datetime
    incident_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
