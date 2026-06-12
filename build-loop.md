# IncidentSherpa Build Loop — copy-paste /loop prompt

**How to run:**

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1   # enables agent teams per CLAUDE.md
claude
```

Then paste the entire prompt below as one command. `/loop 20m` re-fires it every 20 minutes; each firing advances the build and the loop self-terminates when every production gate passes. (Alternative: `/loop <prompt without interval>` for self-paced dynamic mode.)

---

/loop 20m # INCIDENTSHERPA BUILD LOOP — pre-build → LIVE PRODUCTION. No mocks. Ever.

You are the LEAD ENGINEER-ORCHESTRATOR building IncidentSherpa in /Users/nihalnihalani/Desktop/Github/harnes. Read these files FIRST, in order, every firing: BUILD-STATE.md (if it exists — it is the ledger of where you are), CLAUDE.md (project law: architecture, gates, team strategy, claim integrity), final-plan.md (hour-by-hour plan + prize mapping), demo-scripts.md (the 3-minute demo every feature must serve). Then advance the build by AT MOST ONE PHASE per firing, verify it with real commands, update BUILD-STATE.md, and commit+push (Conventional Commits, per the auto-push rule in CLAUDE.md).

## ABSOLUTE RULES (violating any of these is a failed iteration)

1. **NO MOCKS, NO STUBS, NO FAKE PATHS.** Every external call hits the real service: real ClickHouse Cloud, real Langfuse Cloud, real Pioneer API (GLiNER2 + GLiGuard), real Senso, real Airbyte connectors, real Composio OAuth to a real Slack workspace and real Jira project, real Render deploy. If a credential is missing, you do NOT write a stub — you record a BLOCKER (protocol below) and build something else that is unblocked. The replay script is NOT a mock: it bulk-inserts real recorded metrics into real ClickHouse and the causal SQL runs live against them — and you will ALSO build a continuous load generator so the system runs on flowing data, not a one-shot CSV.
2. **CLAIM INTEGRITY.** Every number that will appear on screen (GLiNER2 latency, Context Store latency, costs) must be MEASURED by you and recorded in BUILD-STATE.md with the command that produced it. GLiNER2 = schema-conditioned extraction/classification; GLiGuard = safety moderation on outbound text. Never swap their roles.
3. **LANGFUSE EVERYTHING.** Any function that calls an LLM, a sponsor API, or ClickHouse gets a Langfuse span via libs/tracing.py. A call without a trace is a bug.
4. **VERIFY BEFORE DONE.** A phase is complete only when its named verification commands pass and their output is pasted into BUILD-STATE.md. Never mark done on "should work."
5. **COMMIT + PUSH after every logical change.** Never commit .env (the .gitignore guards this — never weaken it). Never force push.
6. **USE AGENT TEAMS** for parallelizable phases per CLAUDE.md's module map (3–5 teammates; lead coordinates; Devil's Advocate teammate audits claim integrity and demo fragility). Do NOT use teams for Phase 0 (sequential gate-checking).

## BLOCKER PROTOCOL (credentials need a human)

Account signups and browser OAuth (Guild, ClickHouse Cloud, Langfuse, Pioneer, Airbyte, Senso, Composio→Slack/Jira, Render, Anthropic) cannot be done by you. When you hit a missing credential: (a) append it to the `## BLOCKERS` table in BUILD-STATE.md with the EXACT signup URL, the exact env var name(s) from .env.example, and the exact verification command you will run once it lands; (b) send the user a concise message listing ONLY the new blockers; (c) continue with unblocked work — never idle, never stub. At the start of every firing, re-test every blocker (the user may have filled .env) and promote resolved ones to the measured-numbers table.

## STATE LEDGER — BUILD-STATE.md

If missing, create it on the first firing with: current phase; per-phase checklists (copied from the phases below); `## BLOCKERS` table; `## MEASURED NUMBERS` table (metric, value, command, date); `## DECISIONS` log (e.g., Guild SDK vs REST outcome). Every firing updates it. It is committed like any other file — it is also your handoff memory between firings, so write it for a cold reader.

## PHASES (advance max one per firing; each lists deliverable → verification gate)

**PHASE 0 — Preflight & live-credential gates (sequential, no team).**
Copy .env.example→.env if absent. For each credential present, run the REAL test call: Guild `npm view @guildai/agents-sdk` + REST session probe (record SDK-vs-REST decision in DECISIONS); ClickHouse `clickhouse-connect` SELECT 1; Langfuse test span visible in cloud dashboard; Pioneer GLiNER2 call with the severity schema (`severity: [P0,P1,P2,P3]`, `affected_services` spans) — RECORD MEASURED LATENCY; GLiGuard screen on a sample string; Senso whoami/doc-list; Airbyte workspace + GitHub/Jira connector visibility (>20 min friction → record MCP-path decision); Composio `session.link()` status for Slack chat:write + Jira create; Render `render whoami`. Missing ones → BLOCKER protocol. GATE: every available credential has a passing live call logged in BUILD-STATE.md.

**PHASE 1 — Scaffold + CI (team OK).**
Build the exact tree in CLAUDE.md "Project Structure (build target)": apps/api (FastAPI: POST /trigger with payload validation + idempotency key, GET /events SSE, GET /health returning dependency statuses), apps/worker, apps/frontend (`cd apps && npx @openuidev/cli@latest create --name frontend`), libs/{clickhouse,guild,pioneer,senso,airbyte,composio_actions}, libs/tracing.py, scripts/, demo_assets/, render.yaml (THREE services: webhook-api web, agent-worker background worker, frontend web + a cron service hitting /health every 5 min for cold-start mitigation), pytest + ruff config, and .github/workflows/ci.yml (pytest + `next build` on push). GATE: `pytest` green (even if few tests), `cd apps/frontend && npm run build` clean, CI workflow passes on GitHub (check with `gh run list`).

**PHASE 2 — ClickHouse schema + LIVE ingestion (needs ClickHouse cred).**
libs/clickhouse/schema.py creates `metrics`, `events`, `airbyte_history` on the real cluster. scripts/replay.py bulk-inserts demo_assets/incident_metrics.csv (author this CSV: payments-service p99 + payments-db-primary pool_used, pool exhaustion beginning exactly 4m10s before the latency breach) at 10× via HTTP. ALSO build scripts/load_generator.py — a long-running process emitting realistic baseline metrics for all 3 services every 5s with injectable anomalies (`--inject db_pool_exhaustion`), so production runs on continuously flowing data. libs/clickhouse/causal.py: LAG/LEAD window SQL returning (cause_service, effect_service, lag_seconds). GATE: run replay + causal query against the REAL cluster; output names payments-db-primary preceding payments-service by ~250s; paste query + result into BUILD-STATE.md.

**PHASE 3 — Agent core (needs Guild/Pioneer/Senso creds; team OK after state-machine lands).**
apps/worker/agent.py IncidentAgent: state machine Investigating→Mitigating→Resolved; EVERY transition and action emits a typed event to ClickHouse `events` AND the Guild session audit log (REST or SDK per Phase 0 decision; session per incident; Slack/Jira credential scoping through Guild). On alert ingest: GLiNER2 severity+blast-radius extraction FIRST (before any frontier call), then Senso runbook+ownership retrieval (must return citations — reject uncited responses), then ClickHouse causal query, then Airbyte Context Store live query (Phase 5 wires this; leave a named integration point, not a stub — raise NotConfigured until Phase 5). GLiGuard screens every outbound string. Langfuse spans on all of it. scripts/seed_senso.py seeds 3 runbooks + 2 postmortems + ownership map. GATE: `python scripts/trigger.py --payload demo_assets/incident_payload.json` against local API → BUILD-STATE.md shows: extracted severity, cited runbook excerpt, causal result, Guild session ID with ≥6 audit events, Langfuse trace ID with ≥4 spans. All real.

**PHASE 4 — Live actions (needs Composio creds).**
libs/composio_actions: SLACK_SEND_MESSAGE structured incident update (causal summary, suggested owner — wording is ALWAYS "Suggested owner — awaiting confirmation", never "assigned") and JIRA_CREATE_ISSUE follow-up. Idempotent per incident+state (re-firing a webhook must not double-post). GLiGuard screen enforced in the single choke-point send function — make it impossible to send unscreened text. GATE: real Slack message visible in the workspace and real Jira ticket in the project, both reachable from links pasted into BUILD-STATE.md; replaying the same trigger does NOT duplicate them.

**PHASE 5 — Airbyte data layer (needs Airbyte creds).**
Run GitHub + Jira connectors syncing 90 days of real history (use this repo + a Jira project with seeded-but-real tickets) into ClickHouse `airbyte_history` via scripts/seed_history.py. Wire the LIVE Context Store semantic query into the agent's Investigating step — related tickets/PRs in <500ms, MEASURED latency recorded, result + latency written to the timeline event and traced in Langfuse. Ownership suggestion query: "N of last M incidents on <service> resolved by <person>" from real synced rows. MCP interface is the documented fallback if SDK friction exceeds the cap. GATE: live Context Store call returns ≥1 real ticket with measured latency; ownership query returns a real name with real counts; both in BUILD-STATE.md.

**PHASE 6 — Postmortem + frontend (team OK).**
apps/worker/postmortem.py: on Resolve, read the FULL typed event log from ClickHouse + causal SQL result + Senso precedents → claude-fable-5 drafts Timeline/Root Cause/Impact/Action Items → GLiGuard screen → stream token-by-token over SSE. Frontend per demo-scripts.md: scrolling typed-event timeline, Guild state stepper, causal dependency graph with "precedes by Xm Ys" edge + SQL popover, suggested-owner confirm button, streaming postmortem panel, Langfuse/Airbyte/Pioneer latency badges using MEASURED numbers only, F2 reveal of demo_assets/fallback_postmortem.html (generated from a real prior run — a cached real artifact, not a mock). GATE: full local run: trigger → timeline populates live → click Resolve → postmortem streams to完 in ≤30s; `npm run build` clean.

**PHASE 7 — Render production deploy (needs Render cred).**
`render blueprint launch` with all env vars set via `render env` (NEVER committed). All three services + warm-ping cron green. SSE works through Render's proxy (verify buffering doesn't break streaming; fix with proper headers if it does). GATE: `curl https://<app>.onrender.com/health` returns all-dependencies-OK JSON; full E2E (trigger → Slack → Jira → Resolve → streamed postmortem) executed against the PRODUCTION URL, evidence (URLs, trace IDs, timestamps) in BUILD-STATE.md.

**PHASE 8 — Production hardening (team OK; Devil's Advocate leads review).**
Retries with exponential backoff + circuit-breaker behavior on every sponsor client (a Senso 500 must not kill the incident loop — degrade with an explicit DEGRADED event in the log, never silent, never fake data); webhook input validation + auth token + per-IP rate limit; structured JSON logging; graceful SSE reconnect on the frontend; pytest suite covering the state machine, causal SQL (against real ClickHouse using a test table), GLiGuard choke-point (assert unscreened sends are impossible), idempotency, and payload validation; `pip-audit`/`npm audit` clean or findings triaged; secrets audit (`git log -p | grep -iE 'api[_-]?key|secret|token'` style sweep + confirm .env never entered history); load sanity: load_generator at 10× while the UI streams — no dropped events. GATE: all of the above pass with outputs in BUILD-STATE.md; Devil's Advocate teammate signs off in writing with any remaining risks listed.

**PHASE 9 — E2E evidence + docs + demo readiness.**
THREE consecutive clean E2E runs against PRODUCTION, each logged with: trigger timestamp, Langfuse trace ID (≥7 spans incl. GLiNER2, Context Store, Senso, causal SQL, postmortem, GLiGuard, Composio), Slack/Jira links, postmortem time-to-complete (≤30s), and every on-screen number cross-checked against its measured source. Write README.md (what it is, architecture diagram, run-it-yourself, env setup) and docs/ARCHITECTURE.md for judges. Walk demo-scripts.md beat-by-beat against the live system and update any line that no longer matches reality (timestamps, numbers, tab order) — the script must describe the REAL system. GATE: 3/3 clean runs evidenced; an adversarial subagent re-audits the repo for any mock/stub/fabricated number (`grep -rniE 'mock|stub|fake|lorem|TODO|FIXME' --exclude-dir=node_modules .` triaged to zero unexplained hits) and for consistency between demo script claims and measured reality.

## STOPPING CONDITIONS (halt the loop ONLY when ALL true — then summarize and delete the cron job via CronList+CronDelete)

- BUILD-STATE.md shows Phases 0–9 complete, each with pasted verification output
- Production URL serves the frontend; /health is all-green; CI is green on main
- 3/3 production E2E runs evidenced with Langfuse trace IDs and real Slack/Jira links
- Zero open BLOCKERS (or the user has explicitly waived the remaining ones in writing)
- Adversarial no-mock audit passed; secrets audit passed; demo script matches measured reality
- Everything committed and pushed; `git status` clean

## GUARDRAILS

- Max ONE phase per firing; if a firing is consumed by blockers, do hardening/tests/docs work from later phases that needs no credentials — never idle, never skip a gate to "make progress"
- If the same BLOCKER is open for 3 consecutive firings, escalate to the user with a louder, consolidated message and continue
- If a verification gate fails, fix it in THIS firing or roll the phase back to in-progress; never leave a phase marked done with a failing gate
- Re-read CLAUDE.md's Learned Rules every firing; append new ones after any correction
- Never modify the war-room artifacts (ideas.md, debate-log.md, sponsors.md, final-plan.md) except the demo-script reality-sync in Phase 9
