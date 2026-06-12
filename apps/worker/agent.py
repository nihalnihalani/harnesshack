"""Incident agent — typed event log, state machine, and Phase 3 orchestration.

The event log IS the product: every pipeline step and every state transition
becomes a TypedEvent persisted to BOTH ClickHouse `events` and the Guild
session audit log (each wrapped in libs.resilience.with_retries), and is
published to the API's in-process EventBus so the SSE timeline streams live.
If an action isn't in the log, it didn't happen, and the postmortem can't
mention it.

Pipeline order inside INVESTIGATING (CLAUDE.md state-machine table —
small models FIRST, unit-tested in tests/test_agent_pipeline.py):

  1. GLiNER2 schema-conditioned extraction (severity + affected services)
     BEFORE any frontier-LLM step — the small-model-first economics are a
     judge talking point.
  2. ClickHouse causal LAG/LEAD query (libs/clickhouse/causal.py).
  3. Senso runbook + ownership retrieval — CITED or refused.
  4. Airbyte Context Store lookup — a NAMED integration point that raises
     NotConfiguredError(B5) until Phase 5 wires it; the agent catches exactly
     that and emits an honest, visible SKIPPED_NOT_CONFIGURED event.

Degradation policy: a DegradedError from one analysis step or one event sink
becomes an explicit DEGRADED event (never swallowed, never substituted).
ClickHouse AND Guild both failing is FATAL (EventLogFatalError) — with no
event log there is no product. NotConfiguredError from a required step
propagates untouched: an open blocker is a blocker, not a degradation.

Test isolation (NOT runtime mocks): the constructor accepts sink/step
callables so unit tests can run the REAL pipeline against in-process event
sinks without credentials; every default is the real client.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from typing import Any

from libs.errors import NotConfiguredError
from libs.resilience import DegradedError, with_retries

# CLAUDE.md claim integrity: the agent SUGGESTS a likely owner; a human
# confirms. This exact wording — never "assigned" — appears in every
# ownership payload and outbound action text.
OWNER_SUGGESTION_WORDING = "Suggested owner — awaiting confirmation"


class IncidentState(StrEnum):
    """Incident lifecycle states (CLAUDE.md core domain model)."""

    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"


class IllegalTransitionError(ValueError):
    """Raised on any state transition not in LEGAL_TRANSITIONS."""


class EventLogFatalError(RuntimeError):
    """BOTH event sinks (ClickHouse + Guild) failed — the event log IS the product."""


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
    and the Guild session audit log. The postmortem is generated FROM these
    events, never reconstructed from chat.
    """

    ts: datetime
    incident_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Default (real) sinks and steps — every one raises its honest
# NotConfiguredError while its BUILD-STATE blocker is open.
# ---------------------------------------------------------------------------


def airbyte_context_lookup(incident_id: str, query: str) -> Any:
    """NAMED Airbyte Context Store integration point (Phase 5 wires it).

    Until AIRBYTE_CLIENT_ID/SECRET land and Phase 5 implements the live
    semantic query (<500ms, latency badge), this raises NotConfiguredError
    naming B5 — the agent catches exactly that and emits an honest, visible
    SKIPPED_NOT_CONFIGURED event. Never fake related tickets/PRs.
    """
    from libs.airbyte import get_airbyte_client

    return get_airbyte_client()  # raises NotConfiguredError (B5) until Phase 5


def _clickhouse_event_sink(event: TypedEvent) -> None:
    from libs.clickhouse import record_event

    record_event(event.ts, event.incident_id, event.event_type, event.payload)


class GuildAuditSink:
    """Lazily creates the incident's Guild session, then appends every event."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._session_id: str | None = None

    def __call__(self, event: TypedEvent) -> None:
        from libs.guild.session import append_audit_event, create_session

        if self._session_id is None:
            self._session_id = create_session(self._incident_id)
        append_audit_event(self._session_id, event)

    def close(self) -> None:
        from libs.guild.session import close_session

        if self._session_id is not None:
            close_session(self._session_id)


def _default_publish(event: TypedEvent) -> None:
    """Publish to the API's in-process EventBus so /events SSE streams live."""
    # Imported lazily: apps.api.main imports this module at startup.
    from apps.api.main import bus

    bus.publish(
        {
            "ts": event.ts.isoformat(),
            "incident_id": event.incident_id,
            "event_type": event.event_type,
            "payload": event.payload,
        }
    )


def _alert_to_text(payload: dict[str, Any]) -> str:
    """Render an alert payload as a faithful natural-language sentence.

    GLiNER2 classifies severity from prose, not a `key=value` blob (firing-12
    live finding). States only true facts from the payload; injects no
    severity words. Falls back to a generic sentence for unknown shapes.
    """
    svc = payload.get("service")
    metric = payload.get("metric")
    value = payload.get("value")
    ts = payload.get("timestamp")
    iid = payload.get("incident_id", "")
    if svc and metric and value is not None:
        sentence = f"Alert {iid}: service {svc} metric {metric} breached with value {value}"
        if ts:
            sentence += f" at {ts}"
        return sentence + "."
    # Unknown payload shape — describe it truthfully rather than guess.
    parts = ", ".join(f"{k} {v}" for k, v in sorted(payload.items()))
    return f"Incident alert with {parts}."


def _default_extract_severity(text: str) -> Any:
    from libs.pioneer.gliner2 import extract_severity

    return extract_severity(text)


def _default_run_causal_query() -> list[Any]:
    from libs.clickhouse import get_client
    from libs.clickhouse.causal import find_causal_chains

    return find_causal_chains(get_client())


def _default_get_runbook(symptom_query: str) -> Any:
    from libs.senso.retrieve import get_runbook

    return get_runbook(symptom_query)


def _default_get_ownership(service: str) -> Any:
    from libs.senso.retrieve import get_ownership

    return get_ownership(service)


_STEP_PATTERN = re.compile(r"^\s*1\.\s+(?P<step>.+)$", re.MULTILINE)


def first_runbook_step(content: str) -> str | None:
    """Extract step 1 from real runbook content (seed_senso.py '## Steps' format).

    Pure parse of retrieved text — returns None (honestly) when the content
    has no numbered step; never invents a step.
    """
    match = _STEP_PATTERN.search(content)
    return match.group("step").strip() if match else None


def primary_owner_from_ownership_doc(content: str, service: str) -> str | None:
    """Extract '- Primary owner: <name>' for `service` from a CITED ownership doc.

    Pure parse of the retrieved document (seed_senso.py ownership-map format:
    a '## <service>' section containing 'Primary owner: <name>'). Returns
    None honestly when the section or owner line is absent — the UI then
    shows the citation without a name; a name is never invented.
    """
    section_match = re.search(
        rf"^##\s*{re.escape(service)}\s*$(?P<body>.*?)(?=^##\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    body = section_match.group("body") if section_match else content
    owner_match = re.search(r"Primary owner:\s*(?P<owner>[\w.@-]+)", body)
    return owner_match.group("owner") if owner_match else None


# ---------------------------------------------------------------------------
# IncidentAgent
# ---------------------------------------------------------------------------


class IncidentAgent:
    """Single-incident orchestrator: INVESTIGATING -> MITIGATING -> RESOLVED.

    Every step and transition is emitted through `_emit` to ClickHouse,
    Guild, and the in-process EventBus — there is no other write path.
    """

    def __init__(
        self,
        incident_id: str,
        *,
        clickhouse_sink: Callable[[TypedEvent], None] | None = None,
        guild_sink: Callable[[TypedEvent], None] | None = None,
        publish: Callable[[TypedEvent], None] | None = None,
        extract_severity: Callable[[str], Any] | None = None,
        run_causal_query: Callable[[], list[Any]] | None = None,
        get_runbook: Callable[[str], Any] | None = None,
        get_ownership: Callable[[str], Any] | None = None,
        context_lookup: Callable[[str, str], Any] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.incident_id = incident_id
        self.state: IncidentState | None = None
        self.events: list[TypedEvent] = []
        self._clickhouse_sink = clickhouse_sink or _clickhouse_event_sink
        self._guild_sink = guild_sink or GuildAuditSink(incident_id)
        self._publish = publish or _default_publish
        self._extract_severity = extract_severity or _default_extract_severity
        self._run_causal_query = run_causal_query or _default_run_causal_query
        self._get_runbook = get_runbook or _default_get_runbook
        self._get_ownership = get_ownership or _default_get_ownership
        self._context_lookup = context_lookup or airbyte_context_lookup
        self._now = now or (lambda: datetime.now(UTC))

    # -- event emission ----------------------------------------------------

    def _emit(
        self, event_type: str, payload: dict[str, Any], *, _degraded_followup: bool = True
    ) -> TypedEvent:
        """Write one typed event to ClickHouse AND Guild, publish to the bus.

        Each sink write is wrapped in with_retries; a DegradedError from ONE
        sink becomes an explicit DEGRADED event recorded via the surviving
        sink. BOTH sinks failing raises EventLogFatalError — fatal, because
        the event log IS the product. NotConfiguredError (open blocker)
        propagates untouched.
        """
        event = TypedEvent(
            ts=self._now(), incident_id=self.incident_id, event_type=event_type, payload=payload
        )
        self.events.append(event)
        failures: list[tuple[str, DegradedError]] = []
        for service, sink in (
            ("clickhouse", self._clickhouse_sink),
            ("guild", self._guild_sink),
        ):
            try:
                with_retries(partial(sink, event), service=service)
            except DegradedError as exc:
                failures.append((service, exc))
        self._publish(event)
        if len(failures) == 2:
            details = "; ".join(f"{service}: {exc}" for service, exc in failures)
            raise EventLogFatalError(
                "BOTH event sinks failed — the event log IS the product, "
                f"refusing to continue without it ({details})"
            )
        if failures and _degraded_followup:
            for service, exc in failures:
                self._emit(
                    "DEGRADED",
                    {
                        "service": service,
                        "during_event_type": event_type,
                        "error": str(exc),
                    },
                    _degraded_followup=False,
                )
        return event

    def _transition(self, new_state: IncidentState, payload: dict[str, Any]) -> None:
        if self.state is None:
            raise IllegalTransitionError("incident has not been opened (call ingest_alert)")
        previous = self.state
        self.state = validate_transition(self.state, new_state)
        self._emit(
            "state.transition",
            {"from": previous.value, "to": self.state.value, **payload},
        )

    def _degradable(
        self, step_name: str, fn: Callable[[], Any], *, service: str
    ) -> tuple[Any, bool]:
        """Run one analysis step under with_retries.

        Returns (result, ok). DegradedError -> explicit DEGRADED event and
        (None, False); the pipeline continues visibly degraded. Open
        blockers (NotConfiguredError) propagate untouched.
        """
        try:
            return with_retries(fn, service=service), True
        except DegradedError as exc:
            self._emit(
                "DEGRADED",
                {"service": exc.service, "step": step_name, "error": str(exc)},
            )
            return None, False

    # -- lifecycle ----------------------------------------------------------

    def ingest_alert(self, payload: dict[str, Any]) -> IncidentState:
        """Alert POST hits the webhook -> INVESTIGATING pipeline -> MITIGATING.

        CLAUDE.md state-machine table, row 1+2: GLiNER2 first, then the
        ClickHouse causal query, then cited Senso retrievals, then the named
        Airbyte integration point; finally the runbook-step event and the
        transition to MITIGATING.
        """
        if self.state is not None:
            raise IllegalTransitionError(
                f"incident {self.incident_id} already ingested (state={self.state.value})"
            )
        self.state = IncidentState.INVESTIGATING
        self._emit(
            "incident.opened",
            {"state": IncidentState.INVESTIGATING.value, "alert": payload},
        )

        # (a) GLiNER2 schema-conditioned extraction — FIRST, before any
        # frontier-LLM step (small models first; ordering is unit-tested).
        # Render the alert as a faithful NATURAL-LANGUAGE sentence: GLiNER2's
        # classifier returns severity=None for a terse `key=value` blob (it
        # cannot resolve a label), surfaced by the firing-12 live drive. The
        # sentence states only true alert facts — no severity words injected.
        alert_text = _alert_to_text(payload)
        extraction, ok = self._degradable(
            "gliner2_extraction",
            partial(self._extract_severity, alert_text),
            service="pioneer-gliner2",
        )
        if ok:
            self._emit(
                "extraction.completed",
                {
                    "model": "gliner2",
                    "severity": extraction.severity,
                    "affected_services": list(extraction.affected_services),
                    "latency_ms": extraction.latency_ms,  # MEASURED — feeds the UI badge
                },
            )

        # (b) ClickHouse causal LAG/LEAD query. The payload ships the REAL SQL
        # string the query runs (libs/clickhouse/causal.py) so the UI popover
        # shows judges actual SQL, never a paraphrase.
        edges, ok = self._degradable(
            "causal_query", self._run_causal_query, service="clickhouse-causal"
        )
        if ok:
            from libs.clickhouse.causal import build_causal_sql

            self._emit(
                "causal.chains_detected",
                {
                    "edges": [
                        {
                            "cause_service": edge.cause_service,
                            "effect_service": edge.effect_service,
                            "lag_seconds": edge.lag_seconds,
                        }
                        for edge in edges
                    ],
                    "sql": build_causal_sql(),
                },
            )

        # (c) Senso runbook + ownership — CITED or refused (UncitedResponseError
        # propagates: the agent does not log uncited knowledge).
        primary_service = str(payload.get("service", "")) or self.incident_id
        affected = list(extraction.affected_services) if extraction else []
        symptom_query = " ".join(
            [primary_service, str(payload.get("metric", "")), *affected]
        ).strip()
        runbook, _ = self._degradable(
            "senso_runbook", partial(self._get_runbook, symptom_query), service="senso"
        )
        if runbook is not None:
            self._emit(
                "runbook.retrieved",
                {
                    "citation": runbook.citation,
                    "source_id": runbook.source_id,
                    "query": symptom_query,
                    # MEASURED retrieval latency (None until measured — the UI
                    # badge shows "awaiting measurement", never a made-up number).
                    "latency_ms": getattr(runbook, "latency_ms", None),
                },
            )
        ownership, _ = self._degradable(
            "senso_ownership", partial(self._get_ownership, primary_service), service="senso"
        )
        if ownership is not None:
            self._emit(
                "ownership.suggested",
                {
                    # Exact wording rule — a human confirms; never "assigned".
                    "note": OWNER_SUGGESTION_WORDING,
                    "service": primary_service,
                    "citation": ownership.citation,
                    "source_id": ownership.source_id,
                    # Parsed from the CITED doc; None (honest) when unparseable.
                    "suggested_owner": primary_owner_from_ownership_doc(
                        ownership.content, primary_service
                    ),
                    "latency_ms": getattr(ownership, "latency_ms", None),
                },
            )

        # (d) Airbyte Context Store — named integration point; B5 open is an
        # honest, visible skip (NOT silence, NOT fake tickets).
        context, context_ok = None, False
        try:
            context, context_ok = self._degradable(
                "airbyte_context_lookup",
                partial(self._context_lookup, self.incident_id, symptom_query),
                service="airbyte",
            )
        except NotConfiguredError as exc:
            self._emit(
                "SKIPPED_NOT_CONFIGURED",
                {
                    "step": "airbyte_context_lookup",
                    "blocker": "B5",
                    "error": str(exc),
                },
            )
        if context_ok:
            self._emit("context.related_items", {"result": context})

        # Runbook step selected -> MITIGATING (state-machine table, row 2).
        step = first_runbook_step(runbook.content) if runbook is not None else None
        self._emit(
            "runbook.step_selected",
            {
                "step": step,
                "runbook_citation": runbook.citation if runbook is not None else None,
                "note": (
                    "first runbook step parsed from the cited document"
                    if step is not None
                    else "no cited runbook step available — manual selection required"
                ),
            },
        )
        self._transition(IncidentState.MITIGATING, {"trigger": "runbook.step_selected"})
        return self.state

    def confirm_owner(self, owner: str, confirmed_by: str = "human") -> TypedEvent:
        """A HUMAN confirms the suggested owner -> typed owner_confirmed event.

        This is the confirmation half of the claim-integrity rule: the agent
        only ever SUGGESTS ('Suggested owner — awaiting confirmation'); the
        confirmation is a human action and is logged as such.
        """
        if self.state is None:
            raise IllegalTransitionError("incident has not been opened (call ingest_alert)")
        return self._emit(
            "owner_confirmed",
            {"owner": owner, "confirmed_by": confirmed_by},
        )

    def resolve(self, resolved_by: str = "human") -> IncidentState:
        """Human clicks Resolve -> RESOLVED; closes the Guild session."""
        self._transition(IncidentState.RESOLVED, {"resolved_by": resolved_by})
        close = getattr(self._guild_sink, "close", None)
        if callable(close):
            try:
                with_retries(close, service="guild")
            except DegradedError as exc:
                self._emit(
                    "DEGRADED",
                    {"service": "guild", "step": "close_session", "error": str(exc)},
                )
        return self.state


if __name__ == "__main__":
    # render.yaml agent-worker entrypoint: `python -m apps.worker.agent`.
    # Loads the domain model under structured JSON logging and exits; the
    # long-running incident loop lands once credentials (B1/B2...) exist.
    import logging

    from libs.logging_config import configure_logging

    configure_logging()
    logging.getLogger("incidentsherpa.worker").info(
        "agent-worker domain model loaded — long-running loop is credential-gated",
        extra={"service": "agent-worker", "states": [s.value for s in IncidentState]},
    )
