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
| 3 — Agent core | **COMPLETE (2026-06-13, firing 20)** — full gate met live | gate evidence below |
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

## 2026-06-12 ~15:35–15:55 (interactive session) — Slack + Jira DEMO WORKSPACES SEEDED ⚠️ RE-INSERTED after a concurrent BUILD-STATE overwrite (commit a0e46ad clobbered bbdf7c1's section — loop firings: pull before rewriting this file)

- **Jira (incidentsherpa.atlassian.net): project PLAT created + 16 issues seeded** via the ACTIVE Composio connection (`scripts/seed_jira_history.py`, idempotent): 12 payments-service incidents Jan–May 2026 — 9 "Resolved by: dana-chen", 3 miguel-santos — the literal Senso 9-of-12 ownership source; INC-2417 mirror (PLAT-5) + INC-2289 mirror (PLAT-13) consistent with seed_senso.py verbatim; 14 issues transitioned Done; 2 deliberately open follow-ups for the Context Store to surface live: PLAT-14 (settlement-batch → read replica) and PLAT-16 (pool_used > 60 alert). Labels + ADF descriptions verified by readback.
- **`JIRA_PROJECT_KEY` switched SCRUM → PLAT in .env** so the live JIRA_CREATE_ISSUE lands in the seeded project. demo-scripts.md still says "PLAT-4417" — the live ticket will be PLAT-17+; sync on-screen copy at Phase 9.
- **Slack ("Sherpa" workspace): #incidents seeded** (`scripts/seed_slack_history.py`, idempotent) — prior SHERPA INC-2417 update in the exact build_slack_update_text shape, PINNED; chatter cross-linking PLAT-16; topic set; #eng-payments + #deploys created. Satisfies the demo-scripts.md "#incidents has one prior SHERPA message" pre-staging line. Fallback screenshots committed to demo_assets/ (slack #incidents, PLAT board, PLAT list).
- **B5-connectors HALF-UNBLOCKED:** the "real Jira project with seeded incident tickets" now exists. Remaining HUMAN step (~3 min): Atlassian API token (id.atlassian.com → Security → API tokens) + GitHub PAT (`gh auth token`), then provision Airbyte Jira+GitHub sources against domain `incidentsherpa.atlassian.net`, project PLAT.
- **.env DRIFT + RESIDUAL (FIXED ~15:55):** a 15:18 rewrite dropped the four Composio lines; restored 15:25 from docs/composio-b7-slack-jira-session.md. The rewrite had also left an EMPTY `COMPOSIO_API_KEY=` line ABOVE the restored one — composio_link.py's .env loader is first-occurrence-wins, so the empty line shadowed the real key (--check said "unset" while shell-exported runs worked). Empty duplicate deleted. Verified after fix: `--check` green from .env alone (slack ACTIVE, jira ACTIVE), 15 choke-point tests pass. Watch for empty duplicate lines on any .env rewrite.
- **SECURITY — MUST FIX BEFORE PUBLIC FLIP:** the real `COMPOSIO_API_KEY` is committed in docs/composio-b7-slack-jira-session.md (commit d2fc007). The Devpost submission requires flipping this repo PUBLIC — rotate the Composio key, update .env, and redact the doc BEFORE the flip. Key in git history = burned at flip time.

## FIRING-18 — Senso ROOT-CAUSED + fixed; Guild path confirmed via docs.guild.ai
**SENSO (was "key rejected" — actually WRONG HOST/PATHS in our code):** the tgr_ key is VALID (CLI `senso whoami` → org "nihals org"). Our code used host `sdk.senso.ai` and path `/search`; the real API is **`https://apiv2.senso.ai/api/v1`** with **POST `/org/search`** and a two-step S3 KB upload (`POST /org/kb/upload` + presigned PUT). Verified live end-to-end: uploaded a runbook, search returned a grounded `answer` + results[{content_id,chunk_text,title,score}] in <10s. Client+seeder rewrite running (agent af2cef9d). This UNBLOCKS Phase 3.
**GUILD (per user hint docs.guild.ai):** Guild is **SDK/CLI-first — there is NO raw REST sessions/audit API.** Sessions are created via `guild session create --agent <name> --workspace <id>` (CLI) or the `@guildai/agents-sdk` (TS). Our Python REST descope assumption (`POST /v1/sessions`) was the bug — those endpoints never existed. Real path = Option B: a Node sidecar using @guildai/agents-sdk OR the `guild` CLI via subprocess. Sessions require a defined AGENT + WORKSPACE. DECISION: pursue B (CLI/SDK) or C (local audit log, drop the $2,800 claim).

## FIRING-16 — COMPLETE END-TO-END RUN (without Airbyte/Senso/Composio/GLiGuard — all degrade honestly)
User asked "without Airbyte can you make it run completely?" — established that Airbyte was never the blocker (it already SKIPs gracefully). Drove the FULL flow against live ClickHouse + GLiNER2 + Anthropic:
- INGEST → MITIGATING, 16 events: GLiNER2 P3 (108ms live), causal 135s (live), Senso→DEGRADED (bad key 401s but degrades), Airbyte→SKIPPED, Guild→DEGRADED (circuit opens; ClickHouse sink carries the log), Composio steps→SKIPPED.
- RESOLVE → POSTMORTEM **STREAMED 54 chunks / 5923 chars** — a real postmortem written from the live event log by claude-fable-5.
TWO degrade fixes made so the postmortem completes when enrichment is unavailable (Phase 8-aligned, NOT mocks):
1. Senso precedents in postmortem now DEGRADE (event-log-only postmortem + explicit DEGRADED event) instead of propagating the 401. The event log is the source of truth; precedents are enrichment.
2. GLiGuard screen distinguishes BLOCKED (real refusal → still fails closed, no stream) from UNAVAILABLE (not hosted → streams to the operator's OWN UI with a loud DEGRADED event + `screened: false` on postmortem_complete). Composio EXTERNAL-send choke-point stays hard fail-closed (unchanged). Claim integrity: never claims a screen happened when it didn't.
GLiGuard local fallback checked: HF models gliguard-* return 401 (gated/need license+torch) — not a quick win; the explicit-degrade path is the honest interim.
3 regression tests added (TestDegradeNotDie). 230 tests green, ruff clean.
**FINDING (demo perf) — FIXED firing 17:** postmortem was 60.3s (>30s gate). Root cause split: ~21s claude-fable-5 generation (16000 max_tokens, no concision directive → 6000-char draft) + ~15s replay (1.0s/chunk cap too loose). Fixes: prompt now requests a ~350-word concise postmortem (stenographer HARD RULES unchanged); _MAX_OUTPUT_TOKENS 16000→1200; _MAX_REPLAY_DELAY_SECONDS 1.0→0.10. **Re-measured live: 22.3s for 2365 chars / 25 chunks — PASSES the ≤30s gate** (~8s margin; remaining time is honest model generation). 230 tests green.

## FIRING-15 — Phase 5 Airbyte agent-sdk probe (credential live, connectors missing)
- `pip install airbyte-agent-sdk` → v0.1.242 (pinned in apps/worker/requirements.txt). `a.configure(client_id, client_secret)` authenticates with no error against the verified workspace.
- Real API model confirmed: `connect(connector_name, client_id, client_secret) -> HostedExecutor` with `.execute/.check/.inspect_connector/.read_skill_docs`; Workspace has list/get/create_workflow/create_automation. The "Context Store" is the Agent-Engine connector-as-tools surface (the agent executes read actions against GitHub/Jira connectors).
- **BLOCKED: workspace has 0 connectors.** `connect("github")`/`connect("jira")` resolve the connector DEFINITION ids (github ef69ef6e…, jira 68e63de2…) but raise ConnectorNotFoundError — no CONFIGURED connector in workspace 097cb00d. **B5-connectors**: GitHub + a Jira project with seeded incident tickets must be authorized in the Airbyte workspace (browser OAuth + source creds — human setup). `gh auth token` could supply a GitHub PAT for this repo, but harnesshack has ~no issue/PR history, so it won't satisfy the "dana-chen resolved 9 of 12" ownership demo — that needs a real Jira project with seeded incident tickets per the Phase 5 spec.
- Phase 5 code path is ready to wire the moment connectors exist; until then airbyte_context_lookup() correctly raises NotConfigured (honest SKIPPED event), no fake data.

## FIRING-13 (verification-only, no new credentials; no code change)
- Confirmed the Senso degradable-vs-fatal split is DELIBERATE and correct (runtime 500 degrades per Phase 8; missing credential propagates loudly — /health covers the unconfigured case). Not a bug; documented in CLAUDE.md Learned Rules.
- Confirmed the API `/trigger` background ingest converts NotConfiguredError → visible SKIPPED_NOT_CONFIGURED event and any other exception → agent.error event (no silent timeline freeze) by code read (apps/api/main.py:265-280).
- TestClient + SSE + BackgroundTasks deadlock in one process — harness limit, NOT a product bug. Phase 6/7 live-UI verification must use a real uvicorn server. Learned-rule added.

## FIRING-12 LIVE-DRIVE FINDINGS (partial Phase 3 de-risking; GLiNER2+ClickHouse live, Senso/Guild pending)

Drove a REAL incident through IncidentAgent.ingest_alert with live ClickHouse + GLiNER2 defaults. Three findings, all real:
1. **FIXED — alert→text was a `key=value` blob** → GLiNER2 returned severity=None (parser correctly refused to guess). Added `_alert_to_text()` rendering a faithful natural-language sentence (no severity words injected). Re-verified: extraction.completed severity P3, service extracted, 154ms. Regression test added (TestAlertToText).
2. **CLAIM-INTEGRITY — GLiNER2 classifies this incident as P3, NOT the demo narrative's "P1".** Consistent across rich and minimal phrasings. The UI severity badge will say P3. **demo-scripts.md must sync P1→P3 at Phase 9** (cannot edit war-room artifacts before then per loop rule). Recorded here so it is not forgotten.
3. **CONFIRMED — Guild dual-sink degrades gracefully** (JSONDecodeError from app.guild.ai HTML → explicit DEGRADED event, agent continues; ClickHouse sink unaffected). The resilience layer works as designed; the event log/product is intact on the ClickHouse sink while B1 is undecided.

## GUILD REST API — REVERSE-ENGINEERED LIVE (2026-06-12 ~3:05 PM, interactive session)

The control-plane REST API DOES exist on app.guild.ai — our descope code's `/v1/sessions` guess was just the wrong path. Found the real contract in the CLI bundle and verified each call live with the fresh PAT (HTTP 400 "field required" = endpoint exists + authed, not 401/404):
- **Base:** `https://app.guild.ai/api` · **Auth:** `Authorization: Bearer $GUILD_PAT` · workspace_id `019ebd7d-a793-3bb9-0000-a78c98697748`
- **Create:** `POST /api/workspaces/{workspace_id}/sessions` (NOT `/v1/sessions`)
- **Append event:** `POST /api/sessions/{session_id}/events` · **Get:** `GET /api/sessions/{session_id}` · **Interrupt:** `POST /api/sessions/{session_id}/interrupt`
- **DEEPER FINDING (the real architectural snag):** session create requires `session_type ∈ {chat, agent_test, time, webhook}` — `chat` needs a `prompt`, `agent_test` needs an `agent_version_id`. **Guild sessions are agent-EXECUTION sessions, not generic audit containers.** Our plan ("one session per incident, append arbitrary typed events as an audit trail") doesn't map 1:1 — events under a session are that agent run's events, and you must first register the IncidentAgent as a Guild agent (to get an `agent_version_id`) OR run incidents as `chat` sessions seeded with a prompt. This is the precise thing to confirm with the rep: how to use Guild as a per-incident governance/audit layer given the session model is execution-shaped. libs/guild/session.py paths need updating regardless; the agent-registration question gates whether Guild becomes truly load-bearing (B-lite CLI fallback still works either way — ClickHouse remains the durable event-log sink).

## DECISIONS

| Date | Decision | Basis |
|---|---|---|
| 2026-06-13 (firing 10) | **GUILD PATH — DECISION NEEDED (escalated to user).** The Python REST descope assumed app.guild.ai exposes /v1/sessions; it does not (that host is the Agent Hub API + SPA). Three real options: **(A) Find the actual control-plane API base** — ask the sponsor rep for the Sessions/Credentials/audit REST host + auth (keeps the pure-Python architecture). **(B) Adopt `@guildai/agents-sdk@0.2.55` (TS, now installable via PAT)** in a small Node sidecar the Python worker calls for session create/append/close — real Guild SDK use, strongest prize fit, but adds a TS process to the 3-service deploy. **(C) Descope Guild to a local append-only audit log** (ClickHouse `events` already IS a dual sink) and drop/reduce the $2,800 Guild claim — fastest, weakest prize fit. NO FAKING either way: the agent's dual-sink already writes every event to ClickHouse, so the event log (the product) is intact regardless; only the Guild-audit second sink + prize is in question. Recorded, not yet chosen. | live API probing of app.guild.ai; PAT registry auth success |
| 2026-06-12 (interactive session, ~2:45 PM) | **GUILD FINDINGS toward the decision above.** (1) Auth token is VALID (the firing-10 "expired" read was stale): `guild auth status` ✓ as charliegillet, `guild session list` ✓ against workspace `0612hack`. (2) REST base is `https://app.guild.ai/api` (literal in CLI dist; no `/v1` prefix): `GET /api/workspaces` → **405 MethodNotAllowed** (path EXISTS, method/headers differ — CLI dist also references `/sessions/{id}/events/ws` and `/credentials/available`). (3) `@guildai/agents-sdk@0.2.55` confirmed installable via PAT-authed registry. (4) **Option B-lite exists and is VERIFIED TODAY: the worker can subprocess the `guild` CLI** — `guild session create/get/events/send/interrupt`, `guild credentials`, `guild workspace` all work under the current login; also `guild mcp` (stdio MCP server). Recommendation: B-lite now (real Guild control-plane usage, zero new deploy service; needs node in worker image for Render), upgrade to A if rep Cory provides the REST docs. Awaiting user pick. | live probes this session |


| Date | Decision | Basis |
|---|---|---|
| 2026-06-12 | **Frontend scaffold = OpenUI CLI primary path** — `cd apps && npx @openuidev/cli@latest create --name frontend` succeeded on attempt 1 (no create-next-app fallback needed). Removed the template's OpenAI chat route (`src/app/api/chat`) + `openai` dep: wrong provider for this stack (Claude only) and `new OpenAI()` at module scope breaks keyless builds. Kept `@openuidev/react-{lang,headless,ui}` for Phase 6 components. | CLI output; CLAUDE.md architecture (Claude-only reasoning LLM) |
| 2026-06-12 | **Guild path = REST descope (primary).** `@guildai/agents-sdk` lives on Guild's PRIVATE npm registry (app.guild.ai/npm, 401 without auth) — not public npm. libs/guild will be built REST-first per CLAUDE.md's descope spec. If a Guild PAT later grants registry access, SDK becomes an optional upgrade, not a rewrite. | `npm view` 401 output above |
| 2026-06-12 | Phase 1 scaffold proceeds during Phase 0 blockage per the never-idle guardrail (scaffold needs no credentials). | Loop guardrails |

## BLOCKERS (all need the human — signup/OAuth in a browser)

| # | Service | Env var(s) | Where to get it | Verification command (runs automatically next firing) |
|---|---|---|---|---|
| ~~B1~~ | ~~Guild.ai~~ | **RESOLVED firing 20 (Option B-CLI)** — user ran `guild auth login`; rewired libs/guild/session.py to the CLI's REST control-plane (app.guild.ai/api, token via `guild auth token` or GUILD_TOKEN, POST /workspaces/{ws}/sessions + /sessions/{id}/events). Live: created a session per incident, 50 audit entries. GUILD_WORKSPACE=home set. Render note: set GUILD_TOKEN env (no browser there). OLD: ~~PAT valid but decision needed (2026-06-13, firing 10).** `GUILD_API_BASE=https://app.guild.ai` is the **Agent Hub API** (`/api/me`→user charliegillet, `/api/agents`→hub listings); the assumed REST descope endpoints `/v1/sessions`,`/v1/sessions/{id}/events` return the SPA HTML (don't exist there); `/api/sessions` 404. The control-plane Sessions/Credentials/audit API is NOT on app.guild.ai. **HOWEVER the PAT now authenticates the private npm registry: `@guildai/agents-sdk@0.2.55` + `@guildai/cli@0.12.3` are installable** (.npmrc `//app.guild.ai/npm/:_authToken=$GUILD_PAT`). See DECISIONS for the 3 options. | resolved once a Guild path is chosen + a real session/audit call succeeds |
| ~~B2~~ | ~~ClickHouse Cloud~~ | **RESOLVED firing 10 (2026-06-13)** — creds in .env (host zr8in8fpga.us-west-2.aws.clickhouse.cloud), `SELECT 1` → 1 over HTTPS. All three pre-written gates ran green: replay.py --truncate-first --speed 100 (960 rows / 240 ticks), `pytest -m live` 1 passed (real payments-db-primary→payments-service causal edge asserted on the cluster), load_generator --inject db_pool_exhaustion --max-ticks 80 (320 rows, p99 breach detected t+250s after injection) | — | done |
| ~~B2~~ | ~~ClickHouse~~ | **RESOLVED (2026-06-13)** — SELECT 1 in 2088ms (server 25.12.1, us-west-2); schema applied (events 397ms, metrics 244ms, airbyte_history 388ms); replay 960 rows/150.2s at --speed 100; causal gate PASSED; load_generator live-injected 48 rows/12 ticks | — | done |
| ~~B3~~ | ~~Langfuse~~ | **RESOLVED firing 9 (2026-06-13)** — live span via libs/tracing @traced, confirmed by API readback: trace c0d181911da7b49e093fad9c843095e9, visible after 20s. Fix required first: tracing.py was v3-API, installed SDK is 4.7.1 (see DECISIONS + CLAUDE.md Learned Rules) | — | done |
| ~~B4-GLiNER2~~ | ~~Pioneer GLiNER2~~ | **RESOLVED (2026-06-13, firing 11)** — live extraction verified: severity P3 (conf 0.822), affected_services=(payments-service, payments-db-primary), server latency 123ms. Client REWRITTEN to the real contract (model_id/text + unified classifications/entities schema; result.data envelope); 18 Pioneer unit tests re-pinned to a captured live response. | — | done |
| B4-GLiGuard | Pioneer GLiGuard | **DECISION NEEDED** — GLiGuard is NOT in Pioneer's hosted /v1/models catalog (70 entries, all generative; even working gliner2-base isn't listed → catalog is generative-only). Two real paths: **(A)** local Apache-2.0 `transformers` inference (already the designed demo-script fallback; adds the model download + torch dep) or **(B)** ask the rep for the hosted GLiGuard model id / endpoint. Until resolved, the Composio choke-point fails CLOSED (no unscreened sends — honest, not a mock). | gliguard.screen() live call OR local-transformers screen succeeds |
| B5-connectors | Airbyte connectors | **NEW (firing 15)** — credential verified but workspace has 0 connectors; needs GitHub + a Jira project (seeded incident tickets) authorized in the Airbyte dashboard. | `connect('jira')` returns an executor; a read action returns ≥1 real ticket |
| ~~B5-auth~~ | ~~Airbyte~~ | **CREDENTIAL VERIFIED (2026-06-13, firing 14)** — client-credentials token (1503 chars) via POST api.airbyte.com/v1/applications/token; workspace 097cb00d-5739-47f5-bfab-87a67b9e2550 (charlie.gillet1@gmail.com) listed. Workspace is EMPTY (0 sources/0 connections) — Phase 5 must provision GitHub+Jira sources + ClickHouse destination + a 90-day sync, or use the agent-sdk Context Store surface. | Phase 5 build (connectors + live Context Store query) |
| ~~B6~~ | ~~Senso.ai~~ | **RESOLVED firing 18-20** — wrong host was the bug (apiv2.senso.ai/api/v1 + /org/search + 2-step KB upload); client+seeder rewritten; 6 docs seeded; live get_runbook returns cited content. OLD: ~~rejected (firing 14)** | The provided key `tgr_…` returns 401 "Invalid API key" against the confirmed base https://sdk.senso.ai/api/v1 with the correct X-API-Key scheme (base returns JSON 401 not 404, so base+scheme are right — only the VALUE is wrong). The `tgr_` prefix looks like a TRIGGER/webhook token, not the dashboard API key. NEEDS the real Senso API key from the dashboard (org 0612hack). | `httpx.get(sdk.senso.ai/api/v1/orgs/me, headers={X-API-Key:key})` → 200 |
| B7 | Composio | `COMPOSIO_API_KEY` (+ browser OAuth for Slack workspace & Jira project) | composio.dev dashboard → API key; then `python3 scripts/composio_link.py` (OAuth Slack+Jira), `--check` to verify | `python3 scripts/composio_link.py --check` → both ACTIVE. **CONTRACT VERIFIED 2026-06-12 (composio 0.13.1 installed): the authored `session.create()/session.tools.execute()/session.link()` was WRONG — real SDK has NO session; `client.tools.execute(slug, arguments, user_id=...)` + `connected_accounts.link()/toolkits.authorize()` off the Composio instance. send.py rewired (`_get_client`, user_id routing, COMPOSIO_CACHE_DIR guard for read-only homes); choke-point tests + full suite green. ONLY the key + browser OAuth remain.** |
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
| Anthropic claude-fable-5 round-trip (8 max_tokens) | 4335 ms | anthropic.messages.create | 2026-06-13 |
| GLiNER2 in-agent extraction (faithful alert sentence) | severity P3, conf 0.648, 154-164ms | IncidentAgent.ingest_alert live drive | 2026-06-13 |
| Full postmortem run (ingest→resolve→stream complete) | 22.3 s (was 60.3s) | generate_postmortem live, post-tuning | 2026-06-13 |
| claude-fable-5 postmortem generation (concise, ~350w) | ~21 s | stream_anthropic_completion | 2026-06-13 |
| Senso get_runbook (cited, live) | 3686 ms | live get_runbook() | 2026-06-13 |
| Guild session create + 50-event audit trail | live | create_session + append_audit_event + read_audit_events | 2026-06-13 |
| Phase-3 full ingest (dual-sink incl. Guild) | 25.0 s | IncidentAgent.ingest_alert | 2026-06-13 |
| **GLiNER2 severity-extraction inference (THE Pioneer badge number)** | **123–199 ms (server-reported)** | extract_severity() live, result.data.latency_ms | 2026-06-13 |
| GLiNER2 severity-classification confidence (demo text) | 0.822 (P3) | extract_severity() live | 2026-06-13 |
| **GLiNER2 verdict for THE demo incident** | **P3** (not the narrative's P1) | live, consistent across rich + minimal text | 2026-06-13 |
| Replay throughput | 960 rows / 150.2 s at --speed 100 | scripts/replay.py | 2026-06-13 |
| Langfuse ingestion visibility lag | ~20 s | API readback poll, 5s interval | 2026-06-13 |
| GLiNER2 severity+services extraction, server-reported latency_ms (3 calls: 176.1 / 180.1 / 133.9) | 134–180 ms | `POST api.pioneer.ai/inference` model `fastino/gliner2-base-v1`, X-API-Key, schema `{entities, classifications:[{task,labels}]}` | 2026-06-12 |
| GLiGuard prompt_safety screen, server-reported latency_ms (first call — cold start, wall 13.7 s) | 426 ms | `POST api.pioneer.ai/inference` model `fastino/gliguard-LLMGuardrails-300M`, task `prompt_safety` | 2026-06-12 |

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


## FIRING-20 — PHASE 3 COMPLETE (Senso live + Guild audit live)
**Gate met live** (`IncidentAgent.ingest_alert` against all real services):
```
ingest -> MITIGATING (25.0s)
GLiNER2 severity: P3 (live)
causal edges: 2 — payments-db-primary precedes payments-service by 135s (live ClickHouse)
runbook.retrieved: 1 — cited "payments-p99-runbook.md (6cff5947...)" (live Senso)
ownership.suggested: 1 (live Senso ownership map)
Guild DEGRADED: 0 — audit sink LIVE
Guild session id: 019ebe07-9ff8-351a-... with 50 audit-trail entries (>=6 required)
Langfuse: every call traced
```
ALL Phase-3 sponsors now live: GLiNER2, ClickHouse causal, Senso (cited), Guild (audit), Langfuse. Only Airbyte SKIPs (Phase 5) and GLiGuard degrades (not hosted). 231 tests green.
**Perf note:** ingest is 25s because the Guild audit sink does one HTTP append per event (~16). Fine for the demo (timeline opens mid-incident, pre-loaded); could make the Guild sink async/non-blocking later for snappier live ingest.

## FIRING-19 — Guild CLI path mapped (browser-auth required)
Installed @guildai/cli (0.6.0). Commands: auth/agent/workspace/session. **`guild auth login` is browser-OAuth ONLY** — no --token/env flag for non-interactive auth (tried GUILD_PAT/GUILD_TOKEN → "Not authenticated"). Confirms: Guild's session/audit integration needs either (a) the USER runs `guild auth login` in a browser (30s), then the Python worker shells `guild session create --agent X --workspace Y` + logs events, or (b) the `@guildai/agents-sdk` TS sidecar with the PAT. No raw REST sessions/audit API exists (firing-18). GUILD DECISION for user: **B-CLI** (you run `guild auth login`, we shell to CLI), **B-SDK** (Node sidecar), or **C** (local audit log, drop the $2,800 claim). Until decided, Guild degrades gracefully (ClickHouse sink carries the event log — product intact).


## FIRING-21 — SECURITY: leaked Composio key in git history (ACTION REQUIRED before public flip)
Phase-8 secrets sweep of FULL history found ONE live secret committed: the Composio key `ak_HbiwW6J33FR5q_LaorHN` in commit d2fc007 (docs/composio writeup). Commits b1c944f + bfca544 redacted it from HEAD, **but redaction does NOT remove it from history** — `git log -p --all | grep ak_HbiwW6J33...` still finds it at 4 locations. `.env` was NEVER committed (clean); no other live key (Pioneer/Anthropic/Langfuse/ClickHouse/Guild/Senso/Airbyte) is in history.
**REQUIRED before flipping the repo public for Devpost:** ROTATE the Composio key in the Composio dashboard (generate a new one → the leaked `ak_Hbiw...` becomes worthless → history exposure is moot). Optionally also scrub history (git filter-repo/BFG), but rotation is the real fix. Put the NEW key in `.env` (never in docs).
NOTE from commit log (user-side progress to sync): Render DONE ($100 promo, CLI authed); Composio HAD real Slack+Jira sends working (886350d) before the key was pulled; GLiGuard measured 426ms (a89a9fd) — may mean a working GLiGuard endpoint was found; Airbyte agent-API (api.airbyte.ai, 575 connectors) verified. Re-test these next firing.
