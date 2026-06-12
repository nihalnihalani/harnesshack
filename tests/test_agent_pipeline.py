"""IncidentAgent orchestration tests — pipeline ordering + dual-sink event log.

The REAL agent pipeline runs against in-process event sinks and recording
step callables (test isolation of real code, not runtime mocks — every
production default is the real client). No credentials, no network.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from apps.worker.agent import (
    OWNER_SUGGESTION_WORDING,
    EventLogFatalError,
    IllegalTransitionError,
    IncidentAgent,
    IncidentState,
    TypedEvent,
    airbyte_context_lookup,
    first_runbook_step,
    primary_owner_from_ownership_doc,
)
from libs.errors import NotConfiguredError
from libs.resilience import reset_breakers
from libs.senso.retrieve import CitedDocument

ALERT = {
    "service": "payments-service",
    "metric": "p99_ms",
    "value": 2466.1,
    "timestamp": "2026-06-12T14:15:00Z",
}


@pytest.fixture(autouse=True)
def fresh_breakers():
    reset_breakers()
    yield
    reset_breakers()


class FakeExtraction:
    """Real-shaped SeverityExtraction values (severity/affected/latency)."""

    severity = "P0"
    affected_services = ("payments-service", "payments-db-primary")
    latency_ms = 142.3


class FakeEdge:
    cause_service = "payments-db-primary"
    effect_service = "payments-service"
    lag_seconds = 250


RUNBOOK_DOC = CitedDocument(
    content="## Steps\n1. Confirm blast radius: compare p99 against checkout.\n2. Check pool.",
    citation="Runbook: payments-service p99 latency breach",
    source_id="cnt_runbook_1",
)
OWNERSHIP_DOC = CitedDocument(
    content="## payments-service\n- Primary owner: dana-chen",
    citation="Service ownership map: payments and checkout surfaces",
    source_id="cnt_ownership_1",
)


def build_agent(**overrides) -> tuple[IncidentAgent, list[TypedEvent], list[TypedEvent], list]:
    """A real IncidentAgent wired to in-process sinks + a recording step trail."""
    clickhouse_events: list[TypedEvent] = []
    guild_events: list[TypedEvent] = []
    published: list[TypedEvent] = []
    step_calls: list[str] = overrides.pop("step_calls", [])

    def record_step(name: str, value):
        def step(*_args, **_kwargs):
            step_calls.append(name)
            return value

        return step

    def blocked_context_lookup(_incident_id: str, _query: str):
        step_calls.append("airbyte")
        raise NotConfiguredError("Airbyte not configured — see BUILD-STATE.md B5")

    defaults = dict(
        clickhouse_sink=clickhouse_events.append,
        guild_sink=guild_events.append,
        publish=published.append,
        extract_severity=record_step("gliner2", FakeExtraction()),
        run_causal_query=record_step("causal", [FakeEdge()]),
        get_runbook=record_step("runbook", RUNBOOK_DOC),
        get_ownership=record_step("ownership", OWNERSHIP_DOC),
        context_lookup=blocked_context_lookup,
        now=lambda: datetime.now(UTC),
    )
    defaults.update(overrides)
    agent = IncidentAgent("inc-test-1", **defaults)
    agent._step_calls = step_calls  # test handle only
    return agent, clickhouse_events, guild_events, published


def event_types(events: list[TypedEvent]) -> list[str]:
    return [event.event_type for event in events]


class TestPipelineOrdering:
    def test_gliner2_runs_first_and_precedes_everything_downstream(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        # Step-call order: small model FIRST.
        assert agent._step_calls[0] == "gliner2"
        assert agent._step_calls == ["gliner2", "causal", "runbook", "ownership", "airbyte"]

    def test_gliner2_precedes_any_frontier_llm_step(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        types = event_types(ch)
        extraction_index = types.index("extraction.completed")
        # No frontier-LLM event may precede GLiNER2 extraction. (Phase 3 has
        # no LLM step at all; Phase 6 postmortem events are llm.* — this
        # assertion is the contract they must keep.)
        llm_indexes = [
            i
            for i, t in enumerate(types)
            if t.startswith("llm.") or t.startswith("postmortem")
        ]
        assert all(i > extraction_index for i in llm_indexes)
        # And extraction is the FIRST analysis event after incident.opened.
        assert types.index("incident.opened") == 0
        assert extraction_index == 1

    def test_event_sequence(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        assert event_types(ch) == [
            "incident.opened",
            "extraction.completed",
            "causal.chains_detected",
            "runbook.retrieved",
            "ownership.suggested",
            "SKIPPED_NOT_CONFIGURED",
            "runbook.step_selected",
            "state.transition",
        ]


class TestDualSinkEventLog:
    def test_every_event_lands_in_both_sinks_and_the_bus(self):
        agent, ch, guild, published = build_agent()
        agent.ingest_alert(ALERT)
        agent.resolve()
        assert event_types(ch) == event_types(guild) == event_types(published)
        assert len(ch) == len(agent.events)

    def test_every_state_transition_produced_both_sink_events(self):
        agent, ch, guild, _ = build_agent()
        agent.ingest_alert(ALERT)
        agent.resolve()
        for sink in (ch, guild):
            transitions = [e for e in sink if e.event_type == "state.transition"]
            assert [(e.payload["from"], e.payload["to"]) for e in transitions] == [
                ("INVESTIGATING", "MITIGATING"),
                ("MITIGATING", "RESOLVED"),
            ]
            opened = [e for e in sink if e.event_type == "incident.opened"]
            assert opened and opened[0].payload["state"] == "INVESTIGATING"


class TestStateMachineFlow:
    def test_ingest_then_resolve(self):
        agent, _, _, _ = build_agent()
        assert agent.ingest_alert(ALERT) is IncidentState.MITIGATING
        assert agent.resolve() is IncidentState.RESOLVED

    def test_double_ingest_is_illegal(self):
        agent, _, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        with pytest.raises(IllegalTransitionError):
            agent.ingest_alert(ALERT)

    def test_resolve_before_ingest_is_illegal(self):
        agent, _, _, _ = build_agent()
        with pytest.raises(IllegalTransitionError):
            agent.resolve()

    def test_double_resolve_is_illegal(self):
        agent, _, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        agent.resolve()
        with pytest.raises(IllegalTransitionError):
            agent.resolve()


class TestHonestDegradation:
    def test_airbyte_blocker_emits_visible_skip_naming_b5(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        skipped = [e for e in ch if e.event_type == "SKIPPED_NOT_CONFIGURED"]
        assert len(skipped) == 1
        assert skipped[0].payload["step"] == "airbyte_context_lookup"
        assert skipped[0].payload["blocker"] == "B5"

    def test_degraded_step_emits_degraded_event_and_pipeline_continues(self):
        def senso_down(_query):
            raise httpx.ConnectError("senso unreachable")

        agent, ch, _, _ = build_agent(get_runbook=senso_down)
        agent.ingest_alert(ALERT)
        types = event_types(ch)
        assert "DEGRADED" in types
        degraded = next(e for e in ch if e.event_type == "DEGRADED")
        assert degraded.payload["service"] == "senso"
        assert "runbook.retrieved" not in types  # no substitute data, ever
        assert types[-1] == "state.transition"  # pipeline still reached MITIGATING
        step_event = next(e for e in ch if e.event_type == "runbook.step_selected")
        assert step_event.payload["step"] is None  # honest: no cited step available

    def test_one_sink_degraded_emits_degraded_via_survivor(self):
        def clickhouse_down(_event):
            raise httpx.ConnectError("clickhouse unreachable")

        agent, _, guild, _ = build_agent(clickhouse_sink=clickhouse_down)
        agent.ingest_alert(ALERT)
        degraded = [e for e in guild if e.event_type == "DEGRADED"]
        assert degraded, "surviving sink must record the DEGRADED event"
        assert any(e.payload.get("service") == "clickhouse" for e in degraded)

    def test_both_sinks_failing_is_fatal(self):
        def down(_event):
            raise httpx.ConnectError("unreachable")

        agent, _, _, _ = build_agent(clickhouse_sink=down, guild_sink=down)
        with pytest.raises(EventLogFatalError):
            agent.ingest_alert(ALERT)

    def test_required_step_blocker_propagates_untouched(self):
        def keyless_gliner2(_text):
            raise NotConfiguredError("Pioneer not configured — see BUILD-STATE.md B4")

        agent, _, _, _ = build_agent(extract_severity=keyless_gliner2)
        with pytest.raises(NotConfiguredError, match="B4"):
            agent.ingest_alert(ALERT)


class TestClaimIntegrityPayloads:
    def test_extraction_event_carries_measured_latency(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        extraction = next(e for e in ch if e.event_type == "extraction.completed")
        assert extraction.payload["latency_ms"] == FakeExtraction.latency_ms
        assert extraction.payload["severity"] == "P0"

    def test_ownership_event_uses_suggestion_wording_never_assigned(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        ownership = next(e for e in ch if e.event_type == "ownership.suggested")
        assert ownership.payload["note"] == OWNER_SUGGESTION_WORDING
        assert "assigned" not in str(ownership.payload).lower()
        assert ownership.payload["citation"] == OWNERSHIP_DOC.citation

    def test_runbook_event_is_cited(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        runbook = next(e for e in ch if e.event_type == "runbook.retrieved")
        assert runbook.payload["citation"] == RUNBOOK_DOC.citation
        assert runbook.payload["source_id"] == RUNBOOK_DOC.source_id

    def test_senso_latency_is_never_invented(self):
        # The test docs carry no measured latency -> the payload must say
        # None (UI: "awaiting measurement"), never substitute a number.
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        runbook = next(e for e in ch if e.event_type == "runbook.retrieved")
        assert runbook.payload["latency_ms"] is None

    def test_causal_event_ships_the_real_sql(self):
        from libs.clickhouse.causal import build_causal_sql

        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        causal = next(e for e in ch if e.event_type == "causal.chains_detected")
        # The UI popover renders this verbatim — it must BE the executed SQL.
        assert causal.payload["sql"] == build_causal_sql()
        assert "lagInFrame" in causal.payload["sql"]

    def test_ownership_event_carries_parsed_owner_from_cited_doc(self):
        agent, ch, _, _ = build_agent()
        agent.ingest_alert(ALERT)
        ownership = next(e for e in ch if e.event_type == "ownership.suggested")
        assert ownership.payload["suggested_owner"] == "dana-chen"


class TestOwnerConfirmation:
    def test_confirm_owner_emits_typed_event_to_both_sinks(self):
        agent, ch, guild, published = build_agent()
        agent.ingest_alert(ALERT)
        event = agent.confirm_owner("dana-chen", confirmed_by="presenter")
        assert event.event_type == "owner_confirmed"
        assert event.payload == {"owner": "dana-chen", "confirmed_by": "presenter"}
        for sink in (ch, guild, published):
            assert sink[-1].event_type == "owner_confirmed"

    def test_confirm_owner_before_ingest_is_illegal(self):
        agent, _, _, _ = build_agent()
        with pytest.raises(IllegalTransitionError):
            agent.confirm_owner("dana-chen")


class TestModuleHelpers:
    def test_airbyte_context_lookup_raises_b5_until_phase_5(self):
        with pytest.raises(NotConfiguredError, match="B5"):
            airbyte_context_lookup("inc-1", "payments p99")

    def test_first_runbook_step_parses_seeded_format(self):
        assert first_runbook_step("## Steps\n1. Confirm blast radius.\n2. x") == (
            "Confirm blast radius."
        )

    def test_first_runbook_step_returns_none_when_absent(self):
        assert first_runbook_step("no numbered steps here") is None

    def test_primary_owner_parses_seeded_section_format(self):
        content = (
            "## payments-service\n- Primary owner: dana-chen (payments platform team)\n"
            "## payments-db-primary\n- Primary owner: alex-kim (database reliability team)\n"
        )
        assert primary_owner_from_ownership_doc(content, "payments-service") == "dana-chen"
        assert primary_owner_from_ownership_doc(content, "payments-db-primary") == "alex-kim"

    def test_primary_owner_returns_none_when_absent(self):
        assert primary_owner_from_ownership_doc("no owners documented here", "payments") is None


class TestAlertToText:
    """firing-12: GLiNER2 returns severity=None for a key=value blob; the agent
    must feed it a faithful natural-language sentence (no severity words)."""

    def test_renders_natural_language_sentence(self):
        from apps.worker.agent import _alert_to_text

        text = _alert_to_text(
            {
                "incident_id": "inc-1",
                "service": "payments-service",
                "metric": "p99_ms",
                "value": 2466.1,
                "timestamp": "2026-06-12T14:15:00Z",
            }
        )
        assert "payments-service" in text and "p99_ms" in text and "2466.1" in text
        # prose, not a key=value blob
        assert "=" not in text
        assert text.endswith(".")
        # claim integrity: no severity label words injected into the text
        for label in ("P0", "P1", "P2", "P3", "critical", "severe"):
            assert label not in text

    def test_unknown_shape_is_described_truthfully(self):
        from apps.worker.agent import _alert_to_text

        text = _alert_to_text({"foo": "bar"})
        assert "foo" in text and "bar" in text and "=" not in text
