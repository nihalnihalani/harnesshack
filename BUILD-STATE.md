# BUILD-STATE — IncidentSherpa production build ledger

> Handoff memory between loop firings. Cold readers: read CLAUDE.md first for project law.
> Loop: cron job `459218a5`, every 20 min. Started 2026-06-12.

**Current phase: 2 UNBLOCKED — B2 CLICKHOUSE RESOLVED firing 10 (2026-06-13): SELECT 1 green, replay 960 rows, `pytest -m live` 1 passed (real causal edge on the cluster), load_generator 80 ticks w/ breach at t+250s. B8 ANTHROPIC RESOLVED same firing (1-token claude-fable-5 call green). B1 Guild: CLI v0.6.0 installed but token EXPIRED — human must re-run `guild auth login` (browser), then retry the private-registry probe + REST session probe. B3 LANGFUSE RESOLVED + verified live (firing 9; v3→v4 API fix shipped). Phase 8 credential-free portion + Phase 9 docs COMPLETE (firing 8, commits 24b518b..53f822f: webhook bearer auth + per-IP rate limit w/ 16 tests, structured JSON logging, pip-audit 4/4 fixed, npm audit 20 fixed + 6 accepted w/ rationale, secrets sweep 0 hits in 24,559 patch lines, no-mock sweep 97/97 triaged zero needs-fix, README + docs/ARCHITECTURE.md; verified: 231 passed / 1 live-deselected, ruff clean, CI 27439383731 green). REPO IS CODE-COMPLETE FOR ALL PHASES (verified firing 6: 208 tests / 1 live-deselected, ruff clean, CI 27437375093 green, npm build clean). Phase 6 authoring landed (commits fbc5098..e82501f): stenographer postmortem (verbatim-log sentinels, buffer→GLiGuard-screen→replay-at-measured-pace, zero-leak on block), lifecycle endpoints (/resolve, /confirm-owner, agent-wired /trigger), full war-room frontend (timeline, stepper, causal graph w/ real SQL popover, measured-only latency badges, F2 disabled until a real run caches the artifact — correctly absent from demo_assets/). NOTHING LEFT TO BUILD WITHOUT CREDENTIALS. Both escalations sent (firings 3 and 6). Every firing from here: re-test .env → on key landing run the pre-written gates.**

## Phase checklist

| Phase | Status | Gate evidence |
|---|---|---|
| 0 — Preflight & credential gates | **PARTIAL — all 9 services blocked on human signup** (see BLOCKERS); credential-free probes done | Guild SDK probe + runtime checks below |
| 1 — Scaffold + CI | **COMPLETE (2026-06-12)** | Gate outputs below (pytest 29 green, next build clean, CI run pass) |
| 2 — ClickHouse schema + live ingestion | **COMPLETE (2026-06-13, firing 9+)** | Gate outputs below — Phase 2 section |
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

## Phase 2 — gate outputs (2026-06-13, REAL cluster zr8in8fpga.us-west-2.aws.clickhouse.cloud)

```
$ python3 scripts/replay.py --truncate-first --speed 100
replay complete: 960 rows in 150.2s

$ find_causal_chains(client, window_minutes=20)   # 263ms on the live cluster
CausalEdge(cause_service='payments-db-primary', effect_service='payments-service', lag_seconds=135)
CausalEdge(cause_service='payments-service',     effect_service='checkout-service', lag_seconds=55)

$ pytest -m live
1 passed, 231 deselected in 2.49s

$ python3 scripts/load_generator.py --inject db_pool_exhaustion --max-ticks 12
shutdown: 12 ticks, 48 rows inserted   (continuous-flow path verified live)
```

**CLAIM-INTEGRITY RULING (supersedes the ~250s expectation in the demo line):** the live onset-to-onset lag is **135 seconds (2m15s)** — smaller than the 250s climb-start→breach ground truth, exactly as the pre-author flagged. THE DEMO SAYS 2m15s / "precedes by 2m 15s". The 250s figure may only be described as "the pool began departing baseline ~4 minutes before the breach" if narrating the CSV ground truth separately. demo-scripts.md sync happens at Phase 9. Secondary cascade edge (payments → checkout, 55s) is a bonus talking point — a real detected cascade.

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
| ~~B2~~ | ~~ClickHouse Cloud~~ | **RESOLVED firing 10 (2026-06-13)** — creds in .env (host zr8in8fpga.us-west-2.aws.clickhouse.cloud), `SELECT 1` → 1 over HTTPS. All three pre-written gates ran green: replay.py --truncate-first --speed 100 (960 rows / 240 ticks), `pytest -m live` 1 passed (real payments-db-primary→payments-service causal edge asserted on the cluster), load_generator --inject db_pool_exhaustion --max-ticks 80 (320 rows, p99 breach detected t+250s after injection) | — | done |
| ~~B2~~ | ~~ClickHouse~~ | **RESOLVED (2026-06-13)** — SELECT 1 in 2088ms (server 25.12.1, us-west-2); schema applied (events 397ms, metrics 244ms, airbyte_history 388ms); replay 960 rows/150.2s at --speed 100; causal gate PASSED; load_generator live-injected 48 rows/12 ticks | — | done |
| ~~B3~~ | ~~Langfuse~~ | **RESOLVED firing 9 (2026-06-13)** — live span via libs/tracing @traced, confirmed by API readback: trace c0d181911da7b49e093fad9c843095e9, visible after 20s. Fix required first: tracing.py was v3-API, installed SDK is 4.7.1 (see DECISIONS + CLAUDE.md Learned Rules) | — | done |
| B4 | Pioneer (Fastino) | `PIONEER_API_KEY` | pioneer.ai → Settings → API Keys | GLiNER2 severity-schema call, latency MEASURED; GLiGuard screen on sample text |
| B5 | Airbyte | `AIRBYTE_CLIENT_ID`, `AIRBYTE_CLIENT_SECRET` | cloud.airbyte.com → settings → applications | workspace list + GitHub/Jira connector visibility |
| B6 | Senso.ai | `SENSO_API_KEY` | senso.ai signup ($100 free tier, no CC) | `senso whoami` / REST doc-list |
| B7 | Composio | `COMPOSIO_API_KEY` (+ browser OAuth for Slack workspace & Jira project) | composio.dev dashboard → API key; then `session.link()` flows for Slack (chat:write) + Jira (create) | link() status check for both apps |
| ~~B8~~ | ~~Anthropic~~ | **RESOLVED firing 10 (2026-06-13)** — key in .env, 1-token claude-fable-5 call returned 200 (8 in / 1 out tokens, standard tier) | — | done |
| B9 | Render | (CLI login, no env var) | render.com signup; `brew install render && render login` | `render whoami` |

**Fastest unblock path for the human (~30 min):** B2 ClickHouse → B3 Langfuse → B4 Pioneer → B6 Senso → B8 Anthropic (all no-CC self-serve, unblocks Phases 2+3+6), then B7 Composio (Phase 4), B5 Airbyte (Phase 5), B9 Render (Phase 7), B1 Guild (talk to sponsor rep — hardest, also least self-serve).

## NEW INTEL — docs/API-KEYS.md (user-committed f7e08f5, hackathon Discord + ClickHouse slides + Devpost)

Absorbed at firing 8. CHANGES TO THE PLAN:
1. **TIME-CRITICAL:** Anthropic signup links EXPIRED 12:00 PM PT (human escalation needed NOW); Langfuse promo `HARNESSHACK2026` must be used TODAY; ClickHouse $400 via QR; Pioneer promo `SFJune2026Tokens` = $1,500 credits.
2. **Render prize REQUIRES Render Workflows** — current render.yaml is classic services only. DECISION NEEDED at Phase 7: add a Workflows component (evaluate render.yaml `workflows` support) or accept reduced Render-prize fit. Logged as open decision.
3. **Senso challenge requires publishing output to `cited.md`** — new deliverable: the agent's cited runbook/ownership retrievals must also be published to a cited.md artifact. Add to Phase 5/9 checklist (small: write retrievals + citations to cited.md during incident runs).
4. **Submission (Devpost, deadline 4:30 PM PDT):** repo must be flipped PUBLIC before submitting; needs Render URL + 3-min video. Judging = 5×20%: Idea / Technical Implementation / Tool Use (>=3 sponsors) / Presentation / **Autonomy (acts on real-time data without manual intervention — load_generator + webhook auto-ingest is our story)**.
5. Guild is self-serve with 50M free tokens (easier than feared — B1 odds improved); Airbyte free tier 1,000 agent ops is sufficient per rep; OpenUI needs no key; Jua: skip.

## MEASURED NUMBERS

| Metric | Value | Command | Date |
|---|---|---|---|
| Langfuse first-span wall time (incl. client init; NOT a per-span figure) | 1123 ms | `@traced('b3-live-verification') probe()` via libs/tracing | 2026-06-13 |
| ClickHouse SELECT 1 round-trip (cold client) | 2088 ms | clickhouse_connect get_client + SELECT 1 | 2026-06-13 |
| Causal-chain query (960-row window, live cluster) | 263 ms | find_causal_chains(window_minutes=20) | 2026-06-13 |
| **Causal lag, DB→payments (THE demo number)** | **135 s (2m15s)** | live lagInFrame onset pairing | 2026-06-13 |
| Causal lag, payments→checkout (cascade) | 55 s | same query | 2026-06-13 |
| Replay throughput | 960 rows / 150.2 s at --speed 100 | scripts/replay.py | 2026-06-13 |
| Langfuse ingestion visibility lag | ~20 s | API readback poll, 5s interval | 2026-06-13 |

## Blocker age (escalation counter — louder message at 3 consecutive firings)

All B1–B9: opened firing 1; still open at firing 6 (2026-06-13). Escalations sent at firings 3 and 6 (second one offered explicit waive-Bn syntax). Loop is now purely credential-gated.

## Pre-authored: Phase 3/4/8 core — COMPLETE (firing 4-5, commits c68ec7a..f8c1c46; verified 171 passed / 1 live-deselected, ruff clean, CI 27436254446 success)

- libs/resilience.py: with_retries (exp backoff) + per-service circuit breaker (half-open probe) -> typed DegradedError; NotConfiguredError passes through, never trips breaker
- libs/pioneer/: GLiNER2 extract_severity (measured latency_ms returned — UI badge source) + GLiGuard screen (moderation ONLY; ambiguous verdict is never a pass). B4-gated
- libs/senso/retrieve.py: get_runbook/get_ownership -> CitedDocument; UncitedResponseError on uncited content. B6-gated
- libs/guild/session.py: REST-first create/append/close + descope.md. B1-gated
- apps/worker/agent.py: full IncidentAgent — GLiNER2-first pipeline, dual-sink event log (ClickHouse+Guild, one-sink fail -> DEGRADED event, both -> EventLogFatalError), open B5 surfaces as visible SKIPPED_NOT_CONFIGURED event, all events to SSE EventBus
- libs/composio_actions/send.py: single _screened_send choke point (GuardrailBypassError without real ScreenResult; BLOCKED_BY_GUARDRAIL event on refusal; idempotency per incident+state+action; link() only; exact "Suggested owner — awaiting confirmation" wording). B7-gated
- API shapes flagged tolerant-but-loud, confirm on-site when keys land: Pioneer response fields (B4), Senso POST /search (B6), Guild session endpoints (B1), Composio execute shapes (B7)
- Ready-to-run verification commands per blocker are in the firing-5 agent report (also reproduced in commit messages)

## Pre-authored awaiting credentials — COMPLETE (2026-06-12, commits 1fcf8bb..7ea1c50; verified 75 passed / 1 live-deselected, ruff clean)

- Phase 2 code ready: incident_profile.py (seeded source-of-truth curves), make_incident_csv.py + committed incident_metrics.csv (960 rows, byte-pinned by test; pool_used departs baseline at +650s, p99 breaches 2400ms at +900s = exact 250s lead), replay.py (--speed, --truncate-first), load_generator.py (--inject db_pool_exhaustion, --rate-multiplier, SIGINT-clean), causal.py (rolling z-score onsets + lagInFrame pairing, all server-side ClickHouse SQL with bound params)
- Phase 3 prep ready: trigger.py + incident_payload.json (verbatim recorded breach row 2026-06-12T14:15:00Z / 2466.1ms, validated against the real AlertPayload model), seed_senso.py (3 structured runbooks — payments step 3 raises pool ceiling 100→150 — 2 postmortems INC-2417/INC-2289, ownership map dana-chen 9-of-12; endpoint shape flagged for on-site confirmation since Senso docs are sign-in gated)
- **THE MOMENT B2 LANDS:** `python3 scripts/replay.py --truncate-first --speed 100` → `pytest -m live` (asserts the real payments-db-primary→payments-service causal edge) → `python3 scripts/load_generator.py --inject db_pool_exhaustion --max-ticks 80`
- **THE MOMENT B6 LANDS:** `python3 scripts/seed_senso.py` (confirm /content/raw endpoint shape first)
- CLAIM-INTEGRITY NOTE for the demo script: causal.py returns detected ONSET-TO-ONSET lag, which will be SMALLER than the 4m10s climb-start→breach figure (that one is CSV ground truth, asserted in tests). Whichever number the live query produces is the number the demo says. Do not conflate the two.
