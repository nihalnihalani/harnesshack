# IncidentSherpa

**The stenographer in the war room — not a journalist reconstructing from
Slack two days later.** IncidentSherpa is an active incident-commander agent
(built for the [Harness Engineering Hack](https://luma.com/harnesshack),
June 2026): a persistent agent watches a live P0 and writes every alert,
metric anomaly, and human action into a **typed event log as it happens** —
to ClickHouse and to a Guild session audit log simultaneously. Severity and
blast radius are extracted by a small model (GLiNER2) before any frontier
LLM is touched; runbooks and owners come back **cited** from Senso or not at
all; every outbound Slack/Jira action passes a GLiGuard safety screen first.
The moment a human clicks Resolve, a complete postmortem streams
token-by-token — generated **from the event log**, never reconstructed from
chat scrollback. If an action isn't in the log, it didn't happen, and the
postmortem can't mention it.

## Architecture

Three Render services (one [`render.yaml`](render.yaml) Blueprint) and nine
load-bearing sponsor integrations — remove any one and a demo beat breaks:

```
  monitoring / scripts/trigger.py
        │  POST /trigger  (Bearer auth when WEBHOOK_AUTH_TOKEN set,
        ▼                  per-IP rate limit, idempotency keys)
┌─────────────────────┐      SSE /events       ┌─────────────────────────┐
│ webhook-api          │ ─────────────────────▶ │ frontend                │
│ FastAPI  (Render web)│  typed events +        │ Next.js + OpenUI        │
│ /trigger /resolve    │  postmortem tokens     │ timeline · causal graph │
│ /confirm-owner       │                        │ state stepper · panel   │
│ /health /events      │                        │ (Render web)            │
└─────────┬───────────┘                        └─────────────────────────┘
          │ IncidentAgent — INVESTIGATING → MITIGATING → RESOLVED
          │ (in-process behind /trigger today; agent-worker [Render
          ▼  worker] hosts the same domain model for the long-running loop)
┌────────────────────────── every action = one typed event ──────────────┐
│                                                                         │
│  dual-sink event log:   ClickHouse `events`  +  Guild session audit log │
│                                                                         │
└──┬───────┬─────────┬──────────┬──────────┬─────────┬─────────┬─────────┘
   ▼       ▼         ▼          ▼          ▼         ▼         ▼
 Pioneer  ClickHouse Senso    Airbyte   Composio  Anthropic  Langfuse
 GLiNER2  causal SQL runbooks Context   Slack +   Claude     traces EVERY
 extract; (z-score   + owners Store +   Jira via  postmortem LLM/tool/SQL
 GLiGuard onsets,    — cited  90-day    link()    drafting   call (runs on
 screens  lagInFrame or       history   only      only       ClickHouse)
 outbound pairing)   refused
```

Sponsors: **Guild** (session audit + credential scoping), **ClickHouse
Cloud** (event log + causal SQL), **Langfuse** (observability), **Pioneer/
Fastino** (GLiNER2 extraction, GLiGuard moderation — distinct roles),
**Airbyte** (Context Store + history sync), **Senso** (cited knowledge
base), **Composio** (Slack/Jira actions), **Anthropic** (Claude postmortem
drafting only), **Render** (deploy). Full rationale: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quickstart

```bash
# Python (api + worker + libs share one venv at repo root)
python3 -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements.txt -r apps/worker/requirements.txt -r requirements-dev.txt

# Frontend
cd apps/frontend && npm install && cd ../..

# Environment — copy the template, fill what you have. NEVER commit .env.
cp .env.example .env
```

Credentials are gated: with empty env vars every integration raises an
honest `NotConfiguredError` (visible as `SKIPPED_NOT_CONFIGURED` events and
`/health` "blocked" entries) — **no mocks, no fake "ok"**. The credential
blocker table (B1–B9, with signup URLs and verification commands) lives in
[BUILD-STATE.md](BUILD-STATE.md).

### T+0 go/no-go gates (hackathon auth sprint)

```bash
npm view @guildai/agents-sdk            # T+0:00 Guild — 401/404 ⇒ REST descope (libs/guild/descope.md)
# T+0:05 Airbyte cloud auth · T+0:10 Composio session.link() for Slack+Jira
# T+0:15 Pioneer GLiNER2 test call (RECORD the measured latency)
# T+0:20 Langfuse test span · T+0:25 `render blueprint launch` skeleton deploy
```

### Run it

```bash
uvicorn apps.api.main:app --reload --port 8000     # API + SSE
cd apps/frontend && npm run dev                     # timeline on :3000

# Demo flow (replay → trigger → resolve)
python scripts/replay.py --truncate-first --speed 10            # recorded metrics → ClickHouse (disclosed 10× replay)
python scripts/trigger.py --payload demo_assets/incident_payload.json
# watch the timeline populate; confirm the suggested owner; click Resolve →
# the postmortem streams token-by-token (or: POST /incidents/<id>/resolve)
python scripts/load_generator.py --inject db_pool_exhaustion    # continuous live data, optional
```

Production hardening: set `WEBHOOK_AUTH_TOKEN` (POST endpoints then require
`Authorization: Bearer <token>`; unset logs a loud startup warning) and tune
`RATE_LIMIT_PER_MINUTE` (default 60/IP).

## Tests & CI

```bash
ruff check .      # lint — clean
pytest            # 231 tests, in-process against the real app; 1 live-marked
                  # test (real ClickHouse) is deselected until credentials land
cd apps/frontend && npm run build   # Next.js production build — clean
```

GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs
ruff + pytest and the frontend build on every push. Dependency and secrets
audits: [docs/SECURITY-AUDIT.md](docs/SECURITY-AUDIT.md); adversarial
no-mock sweep: [docs/NO-MOCK-AUDIT.md](docs/NO-MOCK-AUDIT.md).

## Map of the repo

| File | What it is |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Project law — architecture, claim-integrity rules, build commands |
| [BUILD-STATE.md](BUILD-STATE.md) | Build ledger — phase status, credential blockers, measured numbers |
| [final-plan.md](final-plan.md) | War-room output: build plan, prize mapping, risks |
| [demo-scripts.md](demo-scripts.md) | Beat-by-beat 3-minute demo script + fallbacks |
| [ideas.md](ideas.md) / [debate-log.md](debate-log.md) / [sponsors.md](sponsors.md) | Decision record — read before changing architecture |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture for judges |
| [docs/SECURITY-AUDIT.md](docs/SECURITY-AUDIT.md) | Dependency + secrets audit (real command outputs) |
| [docs/NO-MOCK-AUDIT.md](docs/NO-MOCK-AUDIT.md) | Adversarial no-mock sweep, fully triaged |
