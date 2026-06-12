"""Postmortem tests — stenographer prompt, buffer-then-stream ordering, gates.

The REAL generate_postmortem pipeline runs against injected in-process step
callables (test isolation of real code, not runtime mocks — every production
default is the real credential-gated client, exercised by the keyless tests).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from apps.worker.postmortem import (
    ANTHROPIC_MODEL,
    LOG_BEGIN_SENTINEL,
    LOG_END_SENTINEL,
    REQUIRED_SECTIONS,
    EmptyEventLogError,
    GuardrailBypassError,
    LogEvent,
    PostmortemBlockedError,
    build_postmortem_prompt,
    fetch_event_log,
    format_event_log,
    generate_postmortem,
    stream_anthropic_completion,
    write_fallback_html,
)
from libs.errors import NotConfiguredError
from libs.pioneer.gliguard import ScreenResult
from libs.resilience import reset_breakers
from libs.senso.retrieve import CitedDocument

EVENTS = [
    LogEvent(
        ts="2026-06-12T14:15:00+00:00",
        event_type="incident.opened",
        payload={"state": "INVESTIGATING", "alert": {"service": "payments-service"}},
    ),
    LogEvent(
        ts="2026-06-12T14:15:02+00:00",
        event_type="extraction.completed",
        payload={"model": "gliner2", "severity": "P0", "latency_ms": 142.3},
    ),
    LogEvent(
        ts="2026-06-12T14:15:05+00:00",
        event_type="state.transition",
        payload={"from": "INVESTIGATING", "to": "MITIGATING"},
    ),
]


class FakeEdge:
    cause_service = "payments-db-primary"
    effect_service = "payments-service"
    lag_seconds = 250


PRECEDENT = CitedDocument(
    content="## Postmortem summary: INC-2417\nPool exhaustion preceded latency.",
    citation="Postmortem summary: INC-2417",
    source_id="cnt_pm_1",
)


@pytest.fixture(autouse=True)
def fresh_breakers():
    reset_breakers()
    yield
    reset_breakers()


# ---------------------------------------------------------------------------
# Prompt builder — the stenographer principle.
# ---------------------------------------------------------------------------


class TestPromptBuilder:
    def test_embeds_the_event_log_verbatim(self):
        prompt = build_postmortem_prompt("inc-1", EVENTS, [FakeEdge()], [PRECEDENT])
        # The serialized log block appears in the prompt byte-for-byte,
        # between the sentinels.
        block = format_event_log(EVENTS)
        assert block in prompt
        begin = prompt.index(LOG_BEGIN_SENTINEL)
        end = prompt.index(LOG_END_SENTINEL)
        assert prompt[begin + len(LOG_BEGIN_SENTINEL) : end].strip() == block
        # And every single event line is present verbatim.
        for line in block.splitlines():
            assert line in prompt
            json.loads(line)  # each line is the event itself, machine-checkable

    def test_rejects_empty_event_log(self):
        with pytest.raises(EmptyEventLogError):
            build_postmortem_prompt("inc-1", [], [FakeEdge()], [PRECEDENT])

    def test_instructs_only_facts_from_the_log(self):
        prompt = build_postmortem_prompt("inc-1", EVENTS, [FakeEdge()], [PRECEDENT])
        assert "ONLY reference facts present in the typed event log" in prompt

    def test_requires_all_four_sections(self):
        prompt = build_postmortem_prompt("inc-1", EVENTS, [FakeEdge()], [PRECEDENT])
        assert REQUIRED_SECTIONS == ("Timeline", "Root Cause", "Impact", "Action Items")
        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in prompt

    def test_precedents_are_cited_and_causal_edges_included(self):
        prompt = build_postmortem_prompt("inc-1", EVENTS, [FakeEdge()], [PRECEDENT])
        assert "[citation: Postmortem summary: INC-2417]" in prompt
        assert "payments-db-primary precedes payments-service by 250 seconds" in prompt

    def test_empty_precedents_are_honestly_noted(self):
        prompt = build_postmortem_prompt("inc-1", EVENTS, [], [])
        assert "no precedent documents were found" in prompt
        assert "no causal edge detected" in prompt


# ---------------------------------------------------------------------------
# generate_postmortem — buffer-then-stream ordering.
# ---------------------------------------------------------------------------


def run_generator(**overrides):
    """Drive the REAL async generator with recording in-process steps."""
    order: list[str] = []
    published: list[dict] = []
    screened_texts: list[str] = []

    def fetch(_incident_id):
        order.append("fetch")
        return EVENTS

    def causal():
        order.append("causal")
        return [FakeEdge()]

    def precedents(_query):
        order.append("precedents")
        return [PRECEDENT]

    def completion(prompt):
        order.append("model")
        assert LOG_BEGIN_SENTINEL in prompt  # the model saw the verbatim log
        return [("## Timeline\n", 0.0), ("All from ", 0.0), ("the log.", 0.0)]

    def screener(text):
        order.append("screen")
        screened_texts.append(text)
        return ScreenResult(allowed=True, categories=(), latency_ms=12.5)

    def publish(item):
        order.append(f"publish:{item['event_type']}")
        published.append(item)

    async def no_sleep(_seconds):
        return None

    kwargs = dict(
        fetch_events=fetch,
        run_causal_query=causal,
        get_precedents=precedents,
        stream_completion=completion,
        screener=screener,
        publish=publish,
        sleep=no_sleep,
    )
    kwargs.update(overrides)

    async def consume():
        return [chunk async for chunk in generate_postmortem("inc-1", **kwargs)]

    chunks = asyncio.run(consume())
    return chunks, order, published, screened_texts


class TestBufferThenStream:
    def test_screen_runs_on_complete_text_before_any_token_is_released(self):
        chunks, order, published, screened_texts = run_generator()
        # GLiGuard saw the COMPLETE text...
        assert screened_texts == ["## Timeline\nAll from the log."]
        # ...and the screen happened strictly before the first token left.
        first_token = order.index("publish:postmortem_token")
        assert order.index("screen") < first_token
        assert order.index("model") < order.index("screen")
        assert chunks == ["## Timeline\n", "All from ", "the log."]

    def test_token_events_and_complete_event_on_the_bus(self):
        chunks, _, published, _ = run_generator()
        token_events = [p for p in published if p["event_type"] == "postmortem_token"]
        assert [e["payload"]["token"] for e in token_events] == chunks
        assert [e["payload"]["index"] for e in token_events] == [0, 1, 2]
        complete = [p for p in published if p["event_type"] == "postmortem_complete"]
        assert len(complete) == 1
        payload = complete[0]["payload"]
        # elapsed_ms is MEASURED wall clock — a real positive float, present.
        assert isinstance(payload["elapsed_ms"], float) and payload["elapsed_ms"] > 0
        assert payload["token_count"] == 3
        assert payload["model"] == ANTHROPIC_MODEL
        assert payload["screen_latency_ms"] == 12.5

    def test_blocked_content_never_leaks_a_single_token(self):
        def refusing_screener(text):
            return ScreenResult(allowed=False, categories=("harm",), latency_ms=9.9)

        with pytest.raises(PostmortemBlockedError):
            run_generator(screener=refusing_screener)

        # Re-run capturing publishes to assert the event surface.
        published: list[dict] = []
        chunks: list[str] = []

        async def consume():
            async for chunk in generate_postmortem(
                "inc-1",
                fetch_events=lambda _i: EVENTS,
                run_causal_query=lambda: [FakeEdge()],
                get_precedents=lambda _q: [],
                stream_completion=lambda _p: [("secret", 0.0)],
                screener=refusing_screener,
                publish=published.append,
                sleep=lambda _s: asyncio.sleep(0),
            ):
                chunks.append(chunk)

        with pytest.raises(PostmortemBlockedError):
            asyncio.run(consume())
        assert chunks == []  # zero tokens yielded
        assert [p["event_type"] for p in published] == ["BLOCKED_BY_GUARDRAIL"]
        assert published[0]["payload"]["categories"] == ["harm"]

    def test_screener_without_real_verdict_is_a_bypass_error(self):
        with pytest.raises(GuardrailBypassError):
            run_generator(screener=lambda _text: True)  # not a ScreenResult

    def test_empty_log_refuses_loudly(self):
        with pytest.raises(EmptyEventLogError):
            run_generator(fetch_events=lambda _i: [])


# ---------------------------------------------------------------------------
# Honest credential gates (the production defaults, keyless).
# ---------------------------------------------------------------------------


class TestKeylessGates:
    def test_fetch_event_log_raises_b2(self):
        with pytest.raises(NotConfiguredError, match="B2"):
            fetch_event_log("inc-1")

    def test_stream_anthropic_completion_raises_b8(self):
        with pytest.raises(NotConfiguredError, match="B8"):
            stream_anthropic_completion("prompt")

    def test_generate_postmortem_defaults_raise_b2_first(self):
        async def consume():
            async for _ in generate_postmortem("inc-1"):
                pass  # pragma: no cover

        with pytest.raises(NotConfiguredError, match="B2"):
            asyncio.run(consume())


# ---------------------------------------------------------------------------
# F2 fallback artifact — only ever a cached REAL run.
# ---------------------------------------------------------------------------


class TestFallbackHtml:
    def test_writes_escaped_real_text(self, tmp_path):
        target = tmp_path / "fallback_postmortem.html"
        result = write_fallback_html("inc-1", "## Timeline\n<b>raw</b>", path=target)
        assert result == target
        content = target.read_text(encoding="utf-8")
        assert "&lt;b&gt;raw&lt;/b&gt;" in content  # escaped, never injected
        assert "cached output of a real completed postmortem run" in content.lower()

    def test_refuses_empty_text(self, tmp_path):
        with pytest.raises(ValueError, match="REAL completed run"):
            write_fallback_html("inc-1", "   ", path=tmp_path / "x.html")
