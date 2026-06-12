# IncidentSherpa — System Architecture (for judges)

Three Render services, one FastAPI webhook surface, one strict state
machine, nine load-bearing sponsor integrations. This document explains the
five design decisions that make the demo trustworthy, with pointers to the
exact code.

## 1. The event log IS the product

Every agent action — alert received, severity extracted, causal edge found,
runbook cited, Slack message sent, owner confirmed, state transition —
becomes one **typed event** (`apps/worker/agent.py::TypedEvent`): timestamp,
incident id, event type, JSON payload. The incident lifecycle is a strict
forward-only state machine (`INVESTIGATING → MITIGATING → RESOLVED`, no
skips, no backwards moves, `RESOLVED` terminal — `LEGAL_TRANSITIONS` in
`apps/worker/agent.py`, 409 on violation at the API).

The payoff is the wow moment: the postmortem is **emitted from that log,
never reconstructed**. `apps/worker/postmortem.py` reads the full event log
back from ClickHouse, embeds it *verbatim* between sentinel markers
(`=== BEGIN TYPED EVENT LOG (verbatim) ===` / `=== END ... ===`), and
instructs claude-fable-5 that it may only reference facts present between
them. An empty log raises `EmptyEventLogError` — a postmortem without an
event log would be reconstruction, the exact failure mode this product
exists to kill. Past Senso postmortems are supplied as **cited context
only**, never paraphrased as fact about the current incident.

## 2. Dual-sink audit design

Each event is written to **two sinks** (`IncidentAgent._emit`): the
ClickHouse `events` table (queryable — the causal SQL and the postmortem
read it) and the Guild session audit log (append-only control-plane record,
one session per incident, credential scoping for Slack/Jira). Both writes
are wrapped in `libs/resilience.with_retries` (exponential backoff +
per-service circuit breaker).

Failure policy is graded and honest:

- **One sink fails** → the event still lands in the other, plus an explicit
  `DEGRADED` event naming the failed service. Never silent.
- **Both sinks fail** → `EventLogFatalError`. With no event log there is no
  product; the pipeline stops loudly rather than running unauditable.
- **A sink is unconfigured** (missing credentials) → `NotConfiguredError`
  propagates and surfaces as a visible `SKIPPED_NOT_CONFIGURED` event on the
  SSE timeline. An open blocker is a blocker, not a degradation — and never
  fake data (`libs/errors.py`, every client in `libs/`).

## 3. GLiNER2 vs GLiGuard — two small models, two distinct roles

Both are Pioneer (Fastino) models; they are **never interchangeable** (this
distinction killed a debate round — debate-log.md Round 3):

- **GLiNER2** (`libs/pioneer/gliner2.py`) — schema-conditioned *extraction/
  classification*. At alert ingest it extracts `severity: P0|P1|P2|P3` and
  `affected_services` spans, **before any frontier-LLM call**, returning its
  measured `latency_ms` (the UI latency badge shows only measured numbers).
  Small-model-first is the cost story: Claude is invoked exactly once per
  incident, for postmortem drafting.
- **GLiGuard** (`libs/pioneer/gliguard.py`) — *safety moderation* of
  outbound text (Slack updates, Jira tickets, the postmortem). It classifies
  safety categories; it never classifies severity. An ambiguous verdict is
  never treated as a pass.

Enforcement is structural, not conventional: every Composio send goes
through a single choke point (`libs/composio_actions/send.py::_screened_send`)
that demands a real `ScreenResult` — absence raises `GuardrailBypassError`,
a refusal emits a `BLOCKED_BY_GUARDRAIL` event. Unscreened sends are
impossible by construction (asserted in `tests/test_choke_point.py`).

## 4. Causal SQL — and the onset-to-onset honesty note

Causal-chain detection (`libs/clickhouse/causal.py`) runs **entirely inside
ClickHouse** — judges can read the SQL in the UI popover; no pandas, no
client-side post-processing:

1. Window functions compute a rolling baseline (mean/stddev over up to 60
   *preceding* samples, minimum 12) per (service, metric) and a z-score for
   each sample.
2. Per service, the first timestamp whose z-score exceeds the threshold is
   that service's **onset** (constant series are excluded).
3. `lagInFrame` (ClickHouse's LAG) pairs consecutive onsets in time order
   into `(cause_service, effect_service, lag_seconds)` edges — "DB pool
   exhaustion preceded payments latency by N seconds".

Tunable parameters are bound server-side (`{threshold_z:Float64}`), never
string-interpolated. The pure-Python `detect_onset_index` is a unit-tested
reference implementation of the same math; the SQL itself runs against real
ClickHouse in the live-marked test.

**Honesty note (from BUILD-STATE.md):** the recorded demo incident's ground
truth is a 250s gap between the pool metric departing baseline and the p99
breach. The causal query reports **detected onset-to-onset lag**, which is
generally *smaller* than the climb-start→breach figure. Whichever number the
live query produces is the number the demo says — the two are never
conflated, and no number ships to the UI without a row in BUILD-STATE.md's
measured-numbers table.

## 5. Buffer-then-screen postmortem streaming

A token-by-token stream that is also guardrail-screened poses a problem:
screening token-by-token can leak the prefix of blocked content.
`apps/worker/postmortem.py` resolves it without faking anything:

1. The live claude-fable-5 stream is **fully buffered**, recording each
   chunk's measured arrival delay.
2. GLiGuard screens the **complete** text. Blocked → `PostmortemBlockedError`
   + a `BLOCKED_BY_GUARDRAIL` event; **zero tokens leave the buffer**.
3. On a pass, tokens are emitted to the SSE bus **replayed at the model's
   own measured pace** (each chunk after its recorded inter-chunk delay,
   stalls capped at 1s).

What the viewer sees is the real model output with real model timing — a
paced replay of an already-screened buffer, and the demo script says so.
A clean finish caches the full text as `demo_assets/fallback_postmortem.html`
(the F2 stage fallback) — that file can **only** come from a real completed
run; there is no placeholder on any path (`GET /fallback/postmortem` is 404
until then).

## Claim-integrity rules (enforced in code, not just prose)

- **Measured numbers only.** Latency badges render from measured fields
  (e.g. GLiNER2's `latency_ms`, Senso retrieval latency) — never constants.
- **"Suggested owner — awaiting confirmation"** — exact wording
  (`OWNER_SUGGESTION_WORDING`, `apps/worker/agent.py`); the agent suggests,
  a human confirms via `POST /incidents/{id}/confirm-owner`, and the
  confirmation is logged as a human action. Never "assigned".
- **Citations or refusal.** Senso retrieval (`libs/senso/retrieve.py`)
  raises `UncitedResponseError` on uncited content.
- **Disclosed replay.** `scripts/replay.py` bulk-inserts a *recorded*
  incident into real ClickHouse at 10× — the causal SQL still runs live, and
  the stage script discloses the replay. `scripts/load_generator.py` exists
  so the system also runs on continuously flowing data.
- **Traced or it didn't happen.** `libs/tracing.py` wraps every external
  call in a Langfuse span; while Langfuse is unconfigured it proceeds with a
  loud warning, never a silent no-op.

## Operational hardening (Phase 8)

- **Webhook auth:** `WEBHOOK_AUTH_TOKEN` set ⇒ `POST /trigger` and
  `/incidents/*` require `Authorization: Bearer <token>` (constant-time
  compare, 401 otherwise); unset ⇒ a loud structured startup warning so the
  keyless state is always a visible choice.
- **Rate limiting:** per-IP token bucket on the POST endpoints
  (`RATE_LIMIT_PER_MINUTE`, default 60; 429 + `Retry-After`).
- **Structured logging:** JSON-lines (`libs/logging_config.py`, stdlib only)
  across api/worker/scripts.
- **Resilience:** retries + circuit breakers (`libs/resilience.py`) on every
  sponsor client; idempotent ingest via `Idempotency-Key` or payload hash.
- **Audits:** [SECURITY-AUDIT.md](SECURITY-AUDIT.md) (dependencies +
  git-history secrets sweep), [NO-MOCK-AUDIT.md](NO-MOCK-AUDIT.md)
  (adversarial sweep, 64/64 hits triaged, zero TODO/FIXME).
