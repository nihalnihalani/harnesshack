# Project Rules for Claude Code

## Project Overview

**IncidentSherpa** — An active incident-commander agent for the Harness Engineering Hack (June 2026). A Guild-managed persistent agent watches a live P0, writes every alert, metric anomaly, and human action into a typed event log *as they happen*, and streams a complete postmortem the moment you click Resolve. The pitch: **it was the stenographer in the room, not a journalist reconstructing from Slack two days later.**

Won the war-room debate 7/7/7/8 (feasibility/novelty/prize-fit/demo) after 4 adversarial rounds. Targets ~$5,250+ in stacked sponsor prizes. Reference artifacts in this repo: `final-plan.md` (build plan, prize math, risks), `demo-scripts.md` (3-min script), `ideas.md` (full Rev 2.1 spec), `debate-log.md` (why every decision was made), `sponsors.md` (verified sponsor intel + install commands).

### Architecture

- **Agent core**: Python — single `IncidentAgent` class with a state machine (Investigating → Mitigating → Resolved); every state transition emits a typed event to ClickHouse AND the Guild session audit log
- **Control plane**: Guild.ai — session per incident, credential scoping for Slack/Jira, append-only audit trail. Primary path: REST session API; upgrade path: `@guildai/agents-sdk` if confirmed on npm at T+0 (see Go/No-Go Gates)
- **Analytics**: ClickHouse Cloud (`clickhouse-connect`) — `metrics` + `events` tables; LAG/LEAD window-function SQL computes cross-service causal chains ("DB pool exhaustion preceded payments latency by 4m10s")
- **Observability**: Langfuse (`langfuse`, `@observe` decorator) — traces EVERY LLM call, tool call, and ClickHouse/Senso/Airbyte query with latency + token cost; runs on ClickHouse Cloud (claims the $350 bonus)
- **Small-model hot path**: Pioneer (Fastino) REST — **GLiNER2** schema-conditioned extraction (`severity: P0|P1|P2|P3`, `affected_services` spans) at alert ingestion, BEFORE any frontier-LLM call; **GLiGuard** screens all outbound text (Slack, Jira, postmortem). Never call these by the wrong name: GLiNER2 = extraction/classification, GLiGuard = safety moderation. This distinction killed a debate round — see debate-log.md Round 3
- **Data layer**: Airbyte Agent Engine (`airbyte-agent-sdk`, MCP interface as fallback) — (1) LIVE Context Store semantic query during the incident (related Jira tickets/PRs, <500ms, latency badge on the timeline); (2) GitHub + Jira connectors batch-pull 90-day history into ClickHouse for the ownership baseline
- **Knowledge base**: Senso.ai REST (`X-API-Key`) — service runbooks, ownership maps, past postmortem summaries; all retrievals must surface citations
- **Actions**: Composio (`composio`, `session.link()` — NEVER deprecated `initiate()`) — SLACK_SEND_MESSAGE structured updates + JIRA_CREATE_ISSUE follow-ups with "Suggested owner — awaiting confirmation" (never "assigned")
- **Frontend**: Next.js + OpenUI (`@openuidev/react-lang`, `@openuidev/react-headless`, `@openuidev/react-ui`) — streaming incident timeline, causal-chain highlight, Guild state stepper, token-by-token postmortem panel via SSE
- **Reasoning LLM**: Claude (claude-fable-5) — postmortem drafting and runbook synthesis ONLY; everything classifiable goes to GLiNER2 first (the small-model-first economics are a judge talking point)
- **Deploy**: Render — ONE `render.yaml` Blueprint, THREE services: `webhook-api` (FastAPI web service), `agent-worker` (Python background worker), `frontend` (Next.js web service). Skeleton deployed at T+0:25, not at the end

### Project Status

**PRE-BUILD.** This repo currently contains only the planning artifacts (CLAUDE.md, final-plan.md, demo-scripts.md, ideas.md, debate-log.md, sponsors.md, README.md). No application code exists yet — the structure below is the BUILD TARGET, created during the hackathon starting at T+0. Do not reference `apps/`, `libs/`, or `scripts/` paths as if they exist until the scaffold commit lands. First build actions: the T+0 auth sprint (Go/No-Go Gates below), then the scaffold + ClickHouse schema.

### Project Structure (build target)

```text
harnes/
├── .gitignore                     # Secrets/venv/node_modules — load-bearing given the auto-push rule
├── README.md
├── CLAUDE.md                      # This file — project rules
├── render.yaml                    # 3-service Render Blueprint (webhook-api, agent-worker, frontend)
├── final-plan.md                  # War-room output: build plan, prize mapping, risks
├── demo-scripts.md                # Beat-by-beat 3-min demo script + fallbacks + pre-staging
├── ideas.md / debate-log.md / sponsors.md   # Decision record — read before changing architecture
├── apps/
│   ├── api/                       # FastAPI webhook receiver + SSE endpoint
│   │   ├── main.py                # POST /trigger (alert ingest), GET /events (SSE), GET /health
│   │   └── requirements.txt
│   ├── worker/                    # Incident agent background worker
│   │   ├── agent.py               # IncidentAgent class — state machine, typed event log
│   │   ├── postmortem.py          # Postmortem generation from the event log (the wow moment)
│   │   └── requirements.txt
│   └── frontend/                  # Next.js + OpenUI timeline
│       ├── app/
│       │   ├── page.tsx           # Incident timeline (OpenUI streaming component)
│       │   └── layout.tsx
│       └── components/
│           ├── timeline.tsx       # Scrolling typed event log
│           ├── causal-graph.tsx   # Dependency graph w/ "precedes by 4m10s" edges
│           ├── guild-stepper.tsx  # Investigating/Mitigating/Resolved state badges
│           └── postmortem-panel.tsx  # Token-by-token streaming panel + F2 static fallback
├── libs/
│   ├── clickhouse/                # Tables, causal LAG/LEAD SQL, bulk insert
│   │   ├── schema.py              # metrics, events, airbyte_history tables
│   │   └── causal.py              # Window-function causal correlation queries
│   ├── guild/                     # Guild session REST client (+ SDK adapter if available)
│   │   ├── session.py             # create session, append audit events, credential scoping
│   │   └── descope.md             # The written descope path — read before touching this lib
│   ├── pioneer/                   # GLiNER2 extraction + GLiGuard guardrail clients
│   │   ├── gliner2.py             # Schema-conditioned severity/blast-radius extraction
│   │   └── gliguard.py            # Outbound-text safety screen (Slack/Jira/postmortem)
│   ├── senso/                     # Knowledge base client — runbooks, ownership, postmortems
│   ├── airbyte/                   # Context Store live query + connector history sync
│   ├── composio_actions/          # Slack + Jira actions (link(), never initiate())
│   └── tracing.py                 # Langfuse init — import this EVERYWHERE that calls anything
├── scripts/
│   ├── replay.py                  # Bulk-inserts incident_metrics.csv into ClickHouse at 10x
│   ├── trigger.py                 # Fires the demo alert payload at the webhook
│   ├── seed_senso.py              # 3 runbooks, 2 postmortems, ownership map
│   └── seed_history.py            # Airbyte GitHub+Jira pull → ClickHouse
├── demo_assets/
│   ├── incident_metrics.csv       # Pre-recorded metrics: DB pool exhaustion 4m10s before latency
│   ├── incident_payload.json      # The demo alert
│   └── fallback_postmortem.html   # F2 static fallback if SSE streaming dies on stage
└── docs/
    └── ARCHITECTURE.md            # System architecture for judges
```

### The Incident State Machine (core domain model)

| State | Entered when | What the agent does | Sponsor touchpoints |
| --- | --- | --- | --- |
| INVESTIGATING | Alert POST hits webhook | GLiNER2 extracts severity + blast radius (<200ms, before any LLM); ClickHouse causal SQL runs; Airbyte Context Store live query for related tickets/PRs; Senso runbook + owner retrieval | Pioneer, ClickHouse, Airbyte, Senso |
| MITIGATING | Runbook step selected | Composio posts structured Slack update (GLiGuard-screened); Jira ticket created with suggested owner; every action appended to Guild audit log + ClickHouse events | Composio, Guild, Pioneer |
| RESOLVED | Human clicks Resolve | Postmortem generated FROM THE TYPED EVENT LOG (not from chat history) by Claude; streams token-by-token to the OpenUI panel; full Langfuse waterfall available | Claude, OpenUI, Langfuse |

Every state transition writes a typed event to BOTH ClickHouse `events` and the Guild session audit log. The event log IS the product — if an action isn't in the log, it didn't happen, and the postmortem can't mention it.

### Go/No-Go Gates (T+0 auth sprint — hard time caps)

These are non-negotiable. Overrunning a gate cascades into the OpenUI block and kills the demo. Full detail in `final-plan.md`.

1. **T+0:00 Guild (15-min HARD CAP):** `npm view @guildai/agents-sdk`. Resolves → SDK path. 404 → REST descope (`libs/guild/descope.md`): single Python agent, Guild sessions/credentials/audit via REST — Guild stays load-bearing. REST also dead → escalate to sponsor rep; last resort LangGraph state + drop ONLY the Guild prize claim. Do not burn minute 16 on this.
2. **T+0:05 Airbyte (20-min cap):** Cloud auth + confirm GitHub/Jira connectors. Overrun → switch to the MCP interface (read-only ops are approval-free since 06-05; still counts as Agent Engine use).
3. **T+0:10 Composio:** `session.link()` for Slack (chat:write) + Jira (create). Pre-authorize NOW, not at demo time.
4. **T+0:15 Pioneer:** GLiNER2 test call with the severity schema. **RECORD the measured latency — that number goes in the demo badge.** 402 error → run the Apache-2.0 models locally via `transformers`, keep the Pioneer labeling honest ("local inference").
5. **T+0:20 Langfuse:** keys + one test span visible in the dashboard. 5 minutes.
6. **T+0:25 Render:** skeleton "hello world" Blueprint deploy BEFORE any domain code. If the build pipeline is broken, find out now.

## Auto-Commit and Push Rule

**MANDATORY**: After every change you make to any file in this repository, you MUST:

1. Stage the changed files: `git add <specific files you changed>`
2. Commit with a clear message describing what changed: `git commit -m "description of change"`
3. Push to remote: `git push origin main`

This applies to EVERY change — no exceptions. Do not batch changes. Commit and push immediately after each logical change.

- Never force push
- Use descriptive commit messages that explain the "why"
- If a pre-commit hook fails, fix the issue and create a NEW commit (never amend)

## Branching & Commit Conventions

- **Main branch**: `main`
- **Commit format**: Conventional Commits
  - `feat:` / `feat(scope):` — new feature
  - `fix:` / `fix(scope):` — bug fix
  - `docs:` — documentation
  - `refactor:` — code refactoring
  - `chore:` — build/tooling changes
  - `test:` — test changes
- **Scopes**: `agent`, `clickhouse`, `guild`, `pioneer`, `senso`, `airbyte`, `composio`, `frontend`, `api`, `tracing`, `deploy`, `demo`

## Build & Test Commands

```bash
# Python (api + worker + libs) — one venv at repo root
python3 -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements.txt -r apps/worker/requirements.txt
# Core deps: fastapi uvicorn httpx clickhouse-connect langfuse composio airbyte-agent-sdk sentence-transformers

# Frontend (scaffolded once via OpenUI CLI — CLI creates ./frontend at cwd, move it into apps/)
cd apps && npx @openuidev/cli@latest create --name frontend   # first time only
cd apps/frontend && npm install && npm run dev                 # port 3000

# Run locally
uvicorn apps.api.main:app --reload --port 8000      # webhook + SSE
python apps/worker/agent.py                          # agent worker

# Demo data
python scripts/seed_senso.py                         # runbooks + ownership into Senso
python scripts/seed_history.py                       # Airbyte GitHub+Jira → ClickHouse
python scripts/replay.py --speed 10                  # metric CSV → ClickHouse (DEFAULT ingest path)
python scripts/trigger.py --payload demo_assets/incident_payload.json   # fire the demo alert

# Deploy (Render Blueprint — all 3 services)
render login
render blueprint launch                              # first deploy
git push origin main                                 # auto-deploys after that

# Verify
pytest                                               # unit tests (causal SQL, state machine, GLiGuard screen)
curl https://incidentsherpa.onrender.com/health      # all services green
```

## Environment Variables

Required in `.env` (Python) and `apps/frontend/.env.local` (Next.js). NEVER commit these.

```bash
# Guild.ai (control plane)
GUILD_PAT=                       # Personal access token (from guild auth login)
GUILD_API_BASE=                  # REST base if on the descope path

# ClickHouse Cloud
CLICKHOUSE_HOST=
CLICKHOUSE_USER=
CLICKHOUSE_PASSWORD=

# Langfuse (observability — runs on ClickHouse)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# Pioneer / Fastino (GLiNER2 + GLiGuard)
PIONEER_API_KEY=                 # X-API-Key header; 402 → local transformers fallback

# Airbyte Agent Engine
AIRBYTE_CLIENT_ID=
AIRBYTE_CLIENT_SECRET=

# Senso.ai (knowledge base)
SENSO_API_KEY=                   # X-API-Key against https://sdk.senso.ai/api/v1

# Composio (Slack + Jira actions — OAuth handled by Composio, no raw Slack/Jira keys here)
COMPOSIO_API_KEY=

# Anthropic (postmortem drafting only)
ANTHROPIC_API_KEY=               # model: claude-fable-5

# Frontend
NEXT_PUBLIC_API_BASE=http://localhost:8000   # SSE endpoint; Render URL in prod
```

## Agent Team Strategy

Use agent teams for any task that benefits from parallel work across independent modules. Teams are enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.

### When to Use Teams

- The T+0:25→T+4:10 build window — the module map below is designed for parallel construction
- Multi-file features spanning the agent core, a sponsor lib, and the frontend
- Code review with competing perspectives (claim-integrity, demo-fragility, security)
- Debugging with competing hypotheses — teammates test different theories simultaneously

### When NOT to Use Teams

- The T+0 auth sprint — it's sequential gate-checking by ONE person with hard time caps
- Changes to `libs/guild/` while the go/no-go outcome is still unknown
- Simple bug fixes, single-file changes, demo-script copy edits

### Team Configuration

- Start with **3-5 teammates** for most workflows
- Aim for **5-6 tasks per teammate** to keep everyone productive
- Use **Opus/Fable for the lead** (reasoning/coordination), **Sonnet for teammates** (focused implementation)
- Use **delegate mode** (`Shift+Tab`) when the lead should only coordinate, not write code

### Team Communication Rules

- Use `SendMessage` (type: "message") for direct teammate communication — always refer to teammates by **name**
- Use `SendMessage` (type: "broadcast") **only** for critical blockers affecting everyone (e.g., the Guild gate result, a ClickHouse schema change)
- Use `TaskCreate`/`TaskUpdate`/`TaskList` for work coordination — teammates self-claim unblocked tasks
- When a teammate finishes, they check `TaskList` for the next available task (prefer lowest ID first)
- Mark tasks `completed` only after verification passes (see Verification Before Done)

### Task Dependencies

- Use `addBlockedBy` to express task ordering
- Teammates skip blocked tasks and pick up unblocked work
- When a blocking task completes, dependent tasks auto-unblock

### Parallelizable Modules (zero file conflicts)

- `libs/pioneer/`, `libs/senso/`, `libs/airbyte/`, `libs/composio_actions/` — independent REST clients
- `apps/frontend/components/` — timeline, causal graph, stepper, postmortem panel are separate files
- `scripts/` — seed and replay scripts are independent
- `apps/api/` vs `apps/worker/` — talk only through ClickHouse events and SSE

### Sequential Dependencies (must happen in order)

1. T+0 auth sprint + Guild go/no-go (blocks `libs/guild/` and all credentialed work)
2. ClickHouse schema (`libs/clickhouse/schema.py`) — blocks the agent core, replay script, and causal SQL
3. `IncidentAgent` state machine — blocks postmortem generation and Composio wiring
4. SSE endpoint shape — blocks the OpenUI timeline wiring
5. Render skeleton deploy (T+0:25) — blocks nothing but MUST be first so deploy failures surface early

### Team Roles

- **Lead**: T+0 auth sprint, Guild go/no-go decision, ClickHouse schema, architecture calls
- **Agent-Core Dev**: `IncidentAgent` state machine, typed event log, postmortem generation
- **Data Dev**: causal LAG/LEAD SQL, replay script, Airbyte history sync + Context Store live query
- **Frontend Dev**: OpenUI timeline, causal graph, postmortem streaming panel, F2 fallbacks
- **Integrations Dev**: Pioneer clients, Senso seeding + retrieval, Composio actions, Langfuse spans
- **Devil's Advocate**: claim-integrity audit (every on-screen number traceable to a real measurement), demo-fragility testing, the 3× rehearsal gate

### Plan Approval for Risky Work

- For architectural changes or anything touching `libs/guild/` or the ClickHouse schema, require **plan approval** before implementation
- The teammate works in read-only mode, submits a plan, lead approves/rejects
- Only after approval does the teammate implement

### Shutdown Protocol

- When all tasks are complete, the lead sends `shutdown_request` to each teammate
- Teammates approve shutdown after confirming their work is committed AND pushed
- Lead calls `TeamDelete` to clean up team resources

## Workflow Orchestration

### 1. Plan Mode Default

- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- The hour-by-hour plan in `final-plan.md` is the master schedule; deviations >15 min require re-planning the remaining blocks

### 2. Subagent Strategy

- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- One task per subagent for focused execution

### 3. Verification Before Done

- Never mark a task complete without proving it works
- Python: `pytest` green; Frontend: `npm run build` clean
- The block-level gates in `final-plan.md` are the definition of done (e.g., agent core is done when: test alert → P-level extracted → cited runbook returned → Context Store hit with latency badge)
- Ask: "Would a hackathon judge be impressed by this?"

### 4. Demo-Driven Development

- Every feature must map to a timestamped beat in `demo-scripts.md` — if it isn't visible in the 3-minute recording, deprioritize it
- The wow moment (0:12–0:30, postmortem streaming) depends ONLY on the agent core + event log. Protect that path above everything else
- Every fragile dependency needs its fallback armed (F2 static cards, CLI trigger, pre-taken screenshots) BEFORE the rehearsal gate
- Rehearsal gate: 3 full clean runs; postmortem complete by 0:30 on every run; ≥7 Langfuse waterfall rows

### 5. Claim Integrity (non-negotiable — this killed a debate round)

- Every number shown on screen or spoken in the demo MUST be measured or cited. No fabricated latencies, no invented benchmarks
- GLiNER2 does extraction/classification; GLiGuard does safety moderation. Never swap or blur their roles
- The replay-CSV ingestion is the honest DEFAULT, disclosed as "replaying a recorded incident at 10× speed" — the causal SQL still runs live
- "Suggests likely owner," never "assigns." Humans confirm; the agent recommends

### 6. Autonomous Bug Fixing

- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Check the Langfuse trace first — it usually shows exactly which span failed and why

### 7. Self-Improvement Loop

- After ANY correction from the user: capture the pattern
- Write rules for yourself in this file's Learned Rules section that prevent the same mistake
- Review lessons at session start for relevant context

## Learned Rules

<!-- Append corrections here. Format: date — rule — why. -->

- 2026-06-12 — GLiGuard is a safety-moderation model (safety/jailbreak/harm/refusal), NOT a severity classifier; severity extraction uses GLiNER2 schema-conditioned inference — a CTO judge reading the Fastino paper would have killed the Pioneer claim in Q&A (debate-log.md Round 3)
- 2026-06-12 — Never put an unmeasured latency number in demo material; use `[measured]ms` placeholders until the T+0:15 test call records the real value
- 2026-06-12 — Use Composio `session.link()`, never `initiate()` (deprecated, cutover 2026-07-03; legacy v1/v2 endpoints already return 410)
- 2026-06-13 — Pioneer /inference real contract (firing 11) differs from the authored guess on EVERY field: `model_id` not `model`, `text` not `input`, model id is `fastino/gliner2-base-v1` (not `gliner2`), and `schema` uses the unified grammar with keys among {classifications, entities, structures, relations} — NOT `{severity:{type:classification}}`. Response envelope is `result.data.{severity:{label,confidence}, entities:{<label>:[{text,confidence,start,end}]}}` and carries a server `latency_ms` (the model-speed badge number — 123–199ms measured). Discovered by fetching GET /openapi.json + reading the 400/422 error bodies. GLiGuard is NOT in the hosted /v1/models catalog (generative-only) — needs the local Apache-2.0 transformers fallback or the rep's hosted id. Rule reinforced: confirm the live API contract via its OpenAPI spec the moment a key lands; tolerant-but-loud parsers earned their keep here.
- 2026-06-13 — libs/tracing was authored against the Langfuse v3 API but 4.7.1 (v4 rewrite) is installed: `start_as_current_span` → `start_as_current_observation(name=..., as_type="span")`. Credential-free unit tests only exercised the unconfigured path, so the mismatch surfaced at the FIRST live call. Rule: when authoring against an SDK without credentials, introspect the INSTALLED version's API surface (dir/signature) — never assume from memory.

## Task Management

1. **Plan First**: Write plan with checkable items before starting
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Review what was built and what changed

## Core Principles

- **The Event Log Is the Product**: Every agent action becomes a typed event in ClickHouse + the Guild audit log. The postmortem is emitted from that log, never reconstructed. If it's not in the log, it didn't happen.
- **Small Models First**: GLiNER2 classifies before Claude reasons; GLiGuard screens before anything sends. Frontier-LLM calls are the exception, not the path — and the cost story is a judge talking point.
- **Langfuse Everything**: If a call isn't traced, it doesn't exist to the judges. Import `libs/tracing.py` in every module that talks to any API.
- **Every Sponsor Load-Bearing**: Remove ClickHouse → no causal chain. Remove Guild → no source of truth. Remove Senso → hallucinated runbooks. Remove Composio → a read-only agent. If a sponsor integration could be deleted without breaking the demo, it's logo-stacking — cut it or deepen it.
- **No Faking, Honest Framing**: Real API calls, real OAuth, real SQL judges can read. Where we control variables (replay CSV, pre-staged data), say so on stage — the DA verdict called honest mitigation "the only intellectually honest mitigation across all four ideas." Keep it that way.
- **Hackathon Speed**: Ship fast, iterate. Perfect is the enemy of done — but the go/no-go gates are sacred.
- **Demo-Driven**: If it doesn't show well in 3 minutes, cut it. Polish > breadth.
- **Simplicity First**: Make every change as simple as possible. Minimal code impact.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
