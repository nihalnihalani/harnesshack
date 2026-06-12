# BUILD-STATE — IncidentSherpa production build ledger

> Handoff memory between loop firings. Cold readers: read CLAUDE.md first for project law.
> Loop: cron job `459218a5`, every 20 min. Started 2026-06-12.

**Current phase: 2 (blocked on B2 ClickHouse) — Phase 2/3 code pre-authored; firing 4 pre-authors Phase 3 agent core + sponsor clients + Phase 4 choke-point + Phase 8 resilience. All gates still credential-blocked.**

## Phase checklist

| Phase | Status | Gate evidence |
|---|---|---|
| 0 — Preflight & credential gates | **PARTIAL — all 9 services blocked on human signup** (see BLOCKERS); credential-free probes done | Guild SDK probe + runtime checks below |
| 1 — Scaffold + CI | **COMPLETE (2026-06-12)** | Gate outputs below (pytest 29 green, next build clean, CI run pass) |
| 2 — ClickHouse schema + live ingestion | not started (needs CLICKHOUSE_*); DDL strings already in libs/clickhouse/schema.py | — |
| 3 — Agent core | not started (needs GUILD_PAT, PIONEER_API_KEY, SENSO_API_KEY, ANTHROPIC_API_KEY) | — |
| 4 — Live actions | not started (needs COMPOSIO_API_KEY + Slack/Jira OAuth) | — |
| 5 — Airbyte data layer | not started (needs AIRBYTE_CLIENT_ID/SECRET) | — |
| 6 — Postmortem + frontend | not started | — |
| 7 — Render production deploy | not started (needs render login) | — |
| 8 — Production hardening | not started | — |
| 9 — E2E evidence + docs | not started | — |

## Phase 0 — probe results (2026-06-12)

```
$ npm view @guildai/agents-sdk version
npm error 401 Unauthorized - GET https://app.guild.ai/npm/@guildai%2fagents-sdk
$ which render
render not found
$ gh auth status        → Logged in (nihalnihalani) ✅ (CI gate dependency OK)
$ python3 --version     → Python 3.14.3 ✅
$ node --version        → v25.2.1 ✅
$ cp -n .env.example .env → created; 13 empty credential slots
```

## Phase 1 — gate outputs (2026-06-12)

```
$ pytest
29 passed, 1 warning in 0.04s

$ cd apps/frontend && npm run build
✓ Compiled successfully in 1013.6ms      (Next.js 16.1.6, Turbopack; routes / and /_not-found prerendered static)

$ gh run list --limit 1
completed  success  fix(frontend): regenerate package-lock — npm ci failed in CI on missi…  CI  main  push  27433963394  44s  2026-06-12T18:07:10Z
  (jobs: "ruff + pytest" success, "next build" success)
```

CI note: first CI run (27433870656) failed in the frontend job — `npm ci` hit a
package-lock missing optional `@emnapi/*` entries (npm lockfile-desync bug with
platform-optional deps). Fixed by full lockfile regeneration (commit 9956a18);
python job (ruff+pytest) passed on every run.

What shipped: apps/api (POST /trigger idempotent ingest, GET /events SSE,
GET /health per-dep configured/blocked), apps/worker (TypedEvent + strict
state machine), libs (tracing, clickhouse DDL+record_event, 5 honest
NotConfiguredError sponsor factories), apps/frontend (OpenUI scaffold + live
SSE list), render.yaml (3 services + health cron, env-group refs only),
tests/ (29), .github/workflows/ci.yml. /trigger returns honest 503 while B2
is open; idempotency keys register at receipt (durable dedupe → Phase 2).

## DECISIONS

| Date | Decision | Basis |
|---|---|---|
| 2026-06-12 | **Frontend scaffold = OpenUI CLI primary path** — `cd apps && npx @openuidev/cli@latest create --name frontend` succeeded on attempt 1 (no create-next-app fallback needed). Removed the template's OpenAI chat route (`src/app/api/chat`) + `openai` dep: wrong provider for this stack (Claude only) and `new OpenAI()` at module scope breaks keyless builds. Kept `@openuidev/react-{lang,headless,ui}` for Phase 6 components. | CLI output; CLAUDE.md architecture (Claude-only reasoning LLM) |
| 2026-06-12 | **Guild path = REST descope (primary).** `@guildai/agents-sdk` lives on Guild's PRIVATE npm registry (app.guild.ai/npm, 401 without auth) — not public npm. libs/guild will be built REST-first per CLAUDE.md's descope spec. If a Guild PAT later grants registry access, SDK becomes an optional upgrade, not a rewrite. | `npm view` 401 output above |
| 2026-06-12 | Phase 1 scaffold proceeds during Phase 0 blockage per the never-idle guardrail (scaffold needs no credentials). | Loop guardrails |

## BLOCKERS (all need the human — signup/OAuth in a browser)

| # | Service | Env var(s) | Where to get it | Verification command (runs automatically next firing) |
|---|---|---|---|---|
| B1 | Guild.ai | `GUILD_PAT`, `GUILD_API_BASE` | guild.ai → open beta signup → `npm i @guildai/cli -g && guild auth login` (account may need a Guild contact / hackathon rep) | REST session create probe + retry `npm view` with registry auth |
| B2 | ClickHouse Cloud | `CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` | clickhouse.cloud → free trial (no credit card) | `python3 -c "import clickhouse_connect; print(clickhouse_connect.get_client(...).query('SELECT 1').result_rows)"` |
| B3 | Langfuse | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | cloud.langfuse.com → new project → API keys | test span emitted + visible via API |
| B4 | Pioneer (Fastino) | `PIONEER_API_KEY` | pioneer.ai → Settings → API Keys | GLiNER2 severity-schema call, latency MEASURED; GLiGuard screen on sample text |
| B5 | Airbyte | `AIRBYTE_CLIENT_ID`, `AIRBYTE_CLIENT_SECRET` | cloud.airbyte.com → settings → applications | workspace list + GitHub/Jira connector visibility |
| B6 | Senso.ai | `SENSO_API_KEY` | senso.ai signup ($100 free tier, no CC) | `senso whoami` / REST doc-list |
| B7 | Composio | `COMPOSIO_API_KEY` (+ browser OAuth for Slack workspace & Jira project) | composio.dev dashboard → API key; then `session.link()` flows for Slack (chat:write) + Jira (create) | link() status check for both apps |
| B8 | Anthropic | `ANTHROPIC_API_KEY` | console.anthropic.com → API keys | 1-token claude-fable-5 message call |
| B9 | Render | (CLI login, no env var) | render.com signup; `brew install render && render login` | `render whoami` |

**Fastest unblock path for the human (~30 min):** B2 ClickHouse → B3 Langfuse → B4 Pioneer → B6 Senso → B8 Anthropic (all no-CC self-serve, unblocks Phases 2+3+6), then B7 Composio (Phase 4), B5 Airbyte (Phase 5), B9 Render (Phase 7), B1 Guild (talk to sponsor rep — hardest, also least self-serve).

## MEASURED NUMBERS

| Metric | Value | Command | Date |
|---|---|---|---|
| *(empty — populated as credentials land; no number ships to the UI without a row here)* | | | |

## Blocker age (escalation counter — louder message at 3 consecutive firings)

All B1–B9: opened firing 1; still open at firing 4 (2026-06-13). Escalation sent at firing 3; next at firing 6 if unchanged.

## Pre-authored awaiting credentials — COMPLETE (2026-06-12, commits 1fcf8bb..7ea1c50; verified 75 passed / 1 live-deselected, ruff clean)

- Phase 2 code ready: incident_profile.py (seeded source-of-truth curves), make_incident_csv.py + committed incident_metrics.csv (960 rows, byte-pinned by test; pool_used departs baseline at +650s, p99 breaches 2400ms at +900s = exact 250s lead), replay.py (--speed, --truncate-first), load_generator.py (--inject db_pool_exhaustion, --rate-multiplier, SIGINT-clean), causal.py (rolling z-score onsets + lagInFrame pairing, all server-side ClickHouse SQL with bound params)
- Phase 3 prep ready: trigger.py + incident_payload.json (verbatim recorded breach row 2026-06-12T14:15:00Z / 2466.1ms, validated against the real AlertPayload model), seed_senso.py (3 structured runbooks — payments step 3 raises pool ceiling 100→150 — 2 postmortems INC-2417/INC-2289, ownership map dana-chen 9-of-12; endpoint shape flagged for on-site confirmation since Senso docs are sign-in gated)
- **THE MOMENT B2 LANDS:** `python3 scripts/replay.py --truncate-first --speed 100` → `pytest -m live` (asserts the real payments-db-primary→payments-service causal edge) → `python3 scripts/load_generator.py --inject db_pool_exhaustion --max-ticks 80`
- **THE MOMENT B6 LANDS:** `python3 scripts/seed_senso.py` (confirm /content/raw endpoint shape first)
- CLAIM-INTEGRITY NOTE for the demo script: causal.py returns detected ONSET-TO-ONSET lag, which will be SMALLER than the 4m10s climb-start→breach figure (that one is CSV ground truth, asserted in tests). Whichever number the live query produces is the number the demo says. Do not conflate the two.
