"""Postmortem generation — streamed FROM the typed event log, never reconstructed.

THE STENOGRAPHER PRINCIPLE (CLAUDE.md: the event log IS the product): the
prompt embeds the incident's FULL typed event log VERBATIM and instructs the
model that it may ONLY reference facts present in that log. If an action
isn't in the log, it didn't happen, and the postmortem cannot mention it.
Senso precedents (past postmortems) are supplied as CITED context only —
they may be referenced with their citation, never paraphrased as fact about
the current incident.

BUFFER-THEN-STREAM (honest about it): GLiGuard must screen the COMPLETE
postmortem text before a single token is released — a partial leak of
blocked content is a guardrail bypass. So the live claude-fable-5 stream is
fully buffered first, recording each chunk's MEASURED arrival delay; the
buffered text is screened; only then are tokens emitted to the EventBus,
replayed at the model's own measured pace (each chunk re-emitted after its
recorded inter-chunk delay). What the viewer sees is the real model output
with real model timing — but it is a paced REPLAY of an already-screened
buffer, not the moment of generation itself. Blocked content emits a
BLOCKED_BY_GUARDRAIL event and raises; zero tokens leave the buffer.

Credential gates (BUILD-STATE.md): ClickHouse event log + causal query (B2),
Senso precedents (B6), GLiGuard screen (B4), Anthropic claude-fable-5 (B8).
Each raises NotConfiguredError naming its blocker — no mocks, no fake data.
Every external call is Langfuse-traced via libs.tracing.call_traced.

Test isolation (NOT runtime mocks): like IncidentAgent, generate_postmortem
accepts step callables so unit tests run the REAL pipeline against in-process
fakes-by-injection; every default is the real client.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from libs.errors import NotConfiguredError
from libs.pioneer.gliguard import ScreenResult
from libs.resilience import DegradedError, with_retries
from libs.senso.retrieve import CitedDocument, NoDocumentFoundError
from libs.tracing import call_traced

logger = logging.getLogger("incidentsherpa.postmortem")

# Postmortem drafting is the ONE frontier-LLM call in the pipeline
# (CLAUDE.md: small models first; Claude for postmortem drafting only).
ANTHROPIC_MODEL = "claude-fable-5"
_MAX_OUTPUT_TOKENS = 16000

# Cap on a single replayed inter-chunk delay: pathological stalls in the
# recorded stream (network hiccups) are not worth replaying verbatim. Within
# the cap, pacing IS the measured model pacing.
_MAX_REPLAY_DELAY_SECONDS = 1.0

REQUIRED_SECTIONS = ("Timeline", "Root Cause", "Impact", "Action Items")

LOG_BEGIN_SENTINEL = "=== BEGIN TYPED EVENT LOG (verbatim) ==="
LOG_END_SENTINEL = "=== END TYPED EVENT LOG ==="

FALLBACK_HTML_PATH = Path(__file__).resolve().parents[2] / (
    "demo_assets/fallback_postmortem.html"
)


class EmptyEventLogError(ValueError):
    """The incident has no typed events — there is nothing honest to write.

    A postmortem 'generated' without an event log would be reconstruction,
    the exact failure mode this product exists to kill. Refuse loudly.
    """


class PostmortemBlockedError(RuntimeError):
    """GLiGuard refused the complete postmortem text — nothing was streamed."""

    def __init__(self, categories: tuple[str, ...]) -> None:
        super().__init__(
            "GLiGuard blocked the postmortem (categories: "
            f"{', '.join(categories) or 'unspecified'}) — no token was released"
        )
        self.categories = categories


class GuardrailBypassError(RuntimeError):
    """The screener did not produce a real ScreenResult — streaming is refused.

    No screen verdict means NO stream, ever (same self-defense rule as the
    Composio choke point).
    """


class ModelRefusalError(RuntimeError):
    """claude-fable-5 returned stop_reason=refusal — surfaced, never papered over."""


@dataclass(frozen=True)
class LogEvent:
    """One row of the ClickHouse `events` table, payload parsed."""

    ts: str
    event_type: str
    payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Inputs — every default is the real, credential-gated client.
# ---------------------------------------------------------------------------

_EVENT_LOG_SQL = """
SELECT ts, event_type, payload
FROM events
WHERE incident_id = {incident_id:String}
ORDER BY ts
"""


def fetch_event_log(incident_id: str) -> list[LogEvent]:
    """Read the FULL typed event log for one incident from ClickHouse (B2-gated)."""
    from libs.clickhouse import get_client

    client = get_client()  # raises NotConfiguredError (B2) while blocked

    def _query() -> Any:
        return client.query(_EVENT_LOG_SQL, parameters={"incident_id": incident_id})

    result = call_traced("clickhouse.fetch_event_log", _query, logger=logger)
    events: list[LogEvent] = []
    for row in result.result_rows:
        ts, event_type, raw_payload = row[0], row[1], row[2]
        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except (TypeError, json.JSONDecodeError):
            # The log is the source of truth — an unparseable payload is
            # carried as its raw string, never dropped or prettified.
            payload = {"raw": str(raw_payload)}
        events.append(
            LogEvent(
                ts=ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                event_type=str(event_type),
                payload=payload,
            )
        )
    return events


def _default_run_causal_query() -> list[Any]:
    from libs.clickhouse import get_client
    from libs.clickhouse.causal import find_causal_chains

    return find_causal_chains(get_client())  # B2-gated


def _default_get_precedents(symptom_query: str) -> list[CitedDocument]:
    """Senso past-postmortem retrieval (B6-gated). Empty result is honest."""
    from libs.senso.retrieve import get_precedents

    try:
        return [get_precedents(symptom_query)]
    except NoDocumentFoundError:
        return []  # honest empty — noted as such in the prompt, never faked


def _default_screener(text: str) -> ScreenResult:
    """GLiGuard moderation under with_retries (B4-gated). Never an implicit pass."""
    from libs.pioneer.gliguard import screen

    return with_retries(partial(screen, text), service="pioneer-gliguard")


def _default_publish(item: dict[str, Any]) -> None:
    """Publish to the API's in-process EventBus so /events SSE streams live."""
    from apps.api.main import bus  # imported lazily; apps.api.main imports us

    bus.publish(item)


# ---------------------------------------------------------------------------
# Prompt — strictly from the log.
# ---------------------------------------------------------------------------


def format_event_log(events: list[LogEvent]) -> str:
    """Serialize the typed event log, one deterministic JSON line per event.

    This exact block is embedded VERBATIM in the prompt — tests assert on it.
    """
    return "\n".join(
        json.dumps(
            {"ts": event.ts, "event_type": event.event_type, "payload": event.payload},
            sort_keys=True,
            default=str,
        )
        for event in events
    )


def build_postmortem_prompt(
    incident_id: str,
    events: list[LogEvent],
    causal_edges: list[Any],
    precedents: list[CitedDocument],
) -> str:
    """Build the stenographer prompt: instructions + the VERBATIM event log.

    Raises EmptyEventLogError when there are no events — a postmortem
    without a log would be reconstruction, which this product refuses.
    """
    if not events:
        raise EmptyEventLogError(
            f"incident {incident_id!r} has no typed events — refusing to generate a "
            "postmortem from nothing (the event log IS the product)"
        )

    edge_lines = (
        "\n".join(
            f"- {edge.cause_service} precedes {edge.effect_service} "
            f"by {edge.lag_seconds} seconds (detected anomaly-onset lag)"
            for edge in causal_edges
        )
        or "- no causal edge detected"
    )
    if precedents:
        precedent_block = "\n\n".join(
            f"[citation: {doc.citation}]\n{doc.content}" for doc in precedents
        )
    else:
        precedent_block = "(no precedent documents were found — say so if relevant)"

    sections = "\n".join(f"## {name}" for name in REQUIRED_SECTIONS)
    return f"""You are the incident stenographer for incident {incident_id}. You watched this \
incident live and recorded every action as a typed event. Write the postmortem now, \
exclusively from your own notes.

HARD RULES — claim integrity:
- You may ONLY reference facts present in the typed event log below. If a fact \
(a timestamp, a latency, a name, a number, an action) is not in the log, it did not \
happen and MUST NOT appear in the postmortem.
- Never invent timestamps, durations, latencies, owners, ticket IDs, or metrics.
- The precedent documents are CITED institutional memory: you may reference them only \
with their citation in square brackets, and only as past context — never as fact about \
THIS incident.
- Where the log is silent (e.g. a step was SKIPPED_NOT_CONFIGURED or DEGRADED), say so \
honestly; do not fill gaps.

Write these four sections, in this order, as Markdown:
{sections}

Detected causal edges (from the ClickHouse window-function query, also present in the log):
{edge_lines}

Precedent documents (cite as [citation: ...] when referenced):
{precedent_block}

{LOG_BEGIN_SENTINEL}
{format_event_log(events)}
{LOG_END_SENTINEL}
"""


# ---------------------------------------------------------------------------
# Anthropic streaming (B8) — buffered with measured per-chunk arrival deltas.
# ---------------------------------------------------------------------------


def stream_anthropic_completion(prompt: str) -> list[tuple[str, float]]:
    """Stream claude-fable-5 and buffer (chunk, measured_arrival_delay_s) pairs.

    Raises NotConfiguredError naming B8 while ANTHROPIC_API_KEY is unset.
    Raises ModelRefusalError on stop_reason == "refusal" — an empty or
    partial refused output is never passed off as a postmortem.
    Langfuse-traced. claude-fable-5: thinking is always on — no `thinking`
    param, no sampling params (both would 400).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise NotConfiguredError(
            "Anthropic not configured: set ANTHROPIC_API_KEY — see BUILD-STATE.md B8"
        )
    # Imported lazily so the unconfigured path has zero side effects.
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    def _call() -> list[tuple[str, float]]:
        buffered: list[tuple[str, float]] = []
        last = time.perf_counter()
        with client.messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=_MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for chunk in stream.text_stream:
                now = time.perf_counter()
                buffered.append((chunk, now - last))  # MEASURED arrival delay
                last = now
            final = stream.get_final_message()
        if final.stop_reason == "refusal":
            raise ModelRefusalError(
                "claude-fable-5 declined the postmortem request "
                f"(stop_details: {getattr(final, 'stop_details', None)!r}) — "
                "discarding any partial output, nothing is streamed"
            )
        return buffered

    return call_traced("anthropic.postmortem.stream", _call, logger=logger)


# ---------------------------------------------------------------------------
# generate_postmortem — the wow moment.
# ---------------------------------------------------------------------------


async def generate_postmortem(
    incident_id: str,
    *,
    fetch_events: Callable[[str], list[LogEvent]] = fetch_event_log,
    run_causal_query: Callable[[], list[Any]] = _default_run_causal_query,
    get_precedents: Callable[[str], list[CitedDocument]] = _default_get_precedents,
    stream_completion: Callable[[str], list[tuple[str, float]]] = stream_anthropic_completion,
    screener: Callable[[str], ScreenResult] = _default_screener,
    publish: Callable[[dict[str, Any]], None] = _default_publish,
    sleep: Callable[[float], Any] = asyncio.sleep,
    now_iso: Callable[[], str] | None = None,
) -> AsyncIterator[str]:
    """Generate the postmortem: read the log, draft, screen, THEN stream.

    Yields token chunks AND publishes each as a postmortem_token event on the
    EventBus; the final postmortem_complete event carries the MEASURED
    elapsed_ms (wall clock from log fetch to last token emitted) plus the
    measured GLiGuard screen latency. See the module docstring for the
    buffer-then-stream honesty contract.
    """
    from datetime import UTC, datetime

    _now_iso = now_iso or (lambda: datetime.now(UTC).isoformat())

    def _event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ts": _now_iso(),
            "incident_id": incident_id,
            "event_type": event_type,
            "payload": payload,
        }

    start = time.perf_counter()

    # (1) The FULL typed event log — the single source of truth (B2).
    events = await asyncio.to_thread(fetch_events, incident_id)
    if not events:
        raise EmptyEventLogError(
            f"incident {incident_id!r} has no typed events — refusing to generate a "
            "postmortem from nothing (the event log IS the product)"
        )

    # (2) Causal result (B2) + cited Senso precedents (B6).
    causal_edges = await asyncio.to_thread(run_causal_query)
    symptom_query = " ".join(
        sorted({event.event_type for event in events} | {incident_id})
    )
    precedents = await asyncio.to_thread(get_precedents, symptom_query)

    # (3) Strictly-from-the-log prompt; (4) buffered claude-fable-5 stream (B8).
    prompt = build_postmortem_prompt(incident_id, events, causal_edges, precedents)
    buffered = await asyncio.to_thread(stream_completion, prompt)
    full_text = "".join(chunk for chunk, _ in buffered)

    # (5) GLiGuard screens the COMPLETE text BEFORE any token is released (B4).
    screen_result = await asyncio.to_thread(screener, full_text)
    if not isinstance(screen_result, ScreenResult):
        raise GuardrailBypassError(
            f"screener returned {type(screen_result).__name__!r} instead of a "
            "ScreenResult — no screen verdict means NO stream"
        )
    if not screen_result.allowed:
        publish(
            _event(
                "BLOCKED_BY_GUARDRAIL",
                {
                    "step": "postmortem",
                    "categories": list(screen_result.categories),
                    "screen_latency_ms": screen_result.latency_ms,  # MEASURED
                },
            )
        )
        raise PostmortemBlockedError(screen_result.categories)

    # (6) Release tokens from the screened buffer at the model's measured pace.
    for index, (chunk, delay) in enumerate(buffered):
        if delay > 0:
            await sleep(min(delay, _MAX_REPLAY_DELAY_SECONDS))
        publish(_event("postmortem_token", {"token": chunk, "index": index}))
        yield chunk

    elapsed_ms = (time.perf_counter() - start) * 1000.0  # MEASURED
    publish(
        _event(
            "postmortem_complete",
            {
                "elapsed_ms": elapsed_ms,
                "token_count": len(buffered),
                "char_count": len(full_text),
                "model": ANTHROPIC_MODEL,
                "screen_latency_ms": screen_result.latency_ms,  # MEASURED
            },
        )
    )
    # Persist the completion record to the event log (the product). The log
    # write must never retro-invalidate an already-streamed postmortem, so a
    # degraded sink is reported as a DEGRADED event, not raised.
    try:
        from libs.clickhouse import record_event

        await asyncio.to_thread(
            with_retries,
            partial(
                record_event,
                datetime.now(UTC),
                incident_id,
                "postmortem_complete",
                {"elapsed_ms": elapsed_ms, "model": ANTHROPIC_MODEL},
            ),
            service="clickhouse",
        )
    except (DegradedError, NotConfiguredError) as exc:
        publish(
            _event(
                "DEGRADED",
                {"service": "clickhouse", "step": "record_postmortem_complete",
                 "error": str(exc)},
            )
        )


# ---------------------------------------------------------------------------
# F2 fallback artifact — a cached REAL run, written only after live success.
# ---------------------------------------------------------------------------


def write_fallback_html(incident_id: str, text: str, *, path: Path | None = None) -> Path:
    """Save a REAL completed postmortem as the F2 static fallback artifact.

    CALL THIS ONLY AFTER A LIVE RUN SUCCEEDS (the resolve endpoint does so
    after generate_postmortem finishes cleanly). Until a real run exists the
    file must NOT exist — the frontend's F2 feature stays disabled on 404.
    Refuses empty text: an empty fallback would be a fake artifact.
    """
    if not text.strip():
        raise ValueError(
            "refusing to write an empty fallback postmortem — the F2 artifact must be "
            "the cached output of a REAL completed run"
        )
    target = path or FALLBACK_HTML_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    from datetime import UTC, datetime

    written_at = datetime.now(UTC).isoformat()
    target.write_text(
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        f"<title>Postmortem (cached real run) — {html.escape(incident_id)}</title>"
        "<style>body{background:#0b0e14;color:#d6deeb;font-family:ui-monospace,"
        "SFMono-Regular,Menlo,monospace;padding:2rem;max-width:72ch;margin:auto}"
        "pre{white-space:pre-wrap}.banner{color:#8a93a5;border:1px solid #2a3040;"
        "padding:.5rem .75rem;border-radius:6px;margin-bottom:1rem}</style></head><body>"
        f'<p class="banner">Cached output of a REAL completed postmortem run for '
        f"incident {html.escape(incident_id)} (generated {written_at}). "
        "Shown via F2 fallback because the live stream is unavailable.</p>"
        f"<pre>{html.escape(text)}</pre>"
        "</body></html>\n",
        encoding="utf-8",
    )
    logger.info("wrote F2 fallback postmortem artifact: %s", target)
    return target


__all__ = [
    "ANTHROPIC_MODEL",
    "FALLBACK_HTML_PATH",
    "LOG_BEGIN_SENTINEL",
    "LOG_END_SENTINEL",
    "REQUIRED_SECTIONS",
    "EmptyEventLogError",
    "GuardrailBypassError",
    "LogEvent",
    "ModelRefusalError",
    "PostmortemBlockedError",
    "build_postmortem_prompt",
    "fetch_event_log",
    "format_event_log",
    "generate_postmortem",
    "stream_anthropic_completion",
    "write_fallback_html",
]
