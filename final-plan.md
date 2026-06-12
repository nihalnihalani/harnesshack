# FINAL PLAN — Harness Engineering Hack (2026-06-12)

Converged after 4 debate rounds (see debate-log.md). Two ideas cleared all four Devil's-Advocate axes at ≥7/10.

## The recommendation: BUILD IncidentSherpa (Rev 2.1)

**Final DA scores: Feasibility 7 / Novelty 7 / Prize-fit 7 / Demo-ability 8** — the only idea to score 8 on any axis.

**One-line pitch:** An active incident-commander agent that opens mid-P0, streams a complete postmortem the moment you click Resolve, and suggests the likely owner for every remediation action — because it was the stenographer in the room, not a journalist reconstructing from Slack.

**Why this wins (the sentence a CTO judge respects):** The postmortem-from-structured-event-log is an architectural insight, not a workflow automation — you cannot replicate it by bolting GPT onto PagerDuty, and the ClickHouse lag/lead causal SQL survives a hostile CTO asking "show me the query."

**30-second pitch:** Of course your postmortem is incomplete — you wrote it from memory 48 hours later, while the only accurate record, the agent's own typed event log, was sitting there the whole time. PagerDuty, Incident.io, and FireHydrant are journalists reconstructing from Slack tweets after the fire; IncidentSherpa is the stenographer who was in the room. Click Resolve, and a complete postmortem with causal chain and owner names streams to your screen in 20 seconds — because the draft was never "written," it was emitted.

Full spec: ideas.md "IncidentSherpa (Rev 2.1)". Full 3-min demo script: demo-scripts.md (inverted arc — wow moment at 0:12–0:30).

## Runner-up: ContractCopilot (Rev 2)

**Final DA scores: 7/7/7/7** — build-ready as specified; no further revision required.
**Promote to primary IF:** Guild auth fails at T+0 AND the team judges the Guild moat too broken to carry — ContractCopilot's five targeted categories (ClickHouse+Langfuse, Senso, TrueFoundry, Composio, Render) are all achievable without Guild. Full spec in ideas.md; full demo script in demo-scripts.md (wow moment at 0:35–0:42, one-click Accept).

## Hour-by-hour build plan — IncidentSherpa (T+0 → T+5:30)

| Time | Work | Gate / checkpoint |
|---|---|---|
| T+0:00–0:25 | **Auth sprint (all six platforms in parallel-ish):** T+0:00 Guild login + `npm view @guildai/agents-sdk` **GO/NO-GO** (15-min hard cap → REST-session descope → LangGraph last resort, drop only the Guild prize claim); T+0:05 Airbyte Cloud auth, confirm GitHub+Jira connectors (>20 min → MCP path); T+0:10 Composio `link()` Slack + Jira OAuth; T+0:15 Pioneer key + **GLiNER2 test call with severity schema — RECORD measured latency for the demo badge** + GLiGuard guardrail test (402 → run Apache-2.0 models locally via transformers); T+0:20 Langfuse keys + test span; T+0:25 Render `render.yaml` skeleton deploy ("hello world" before domain code) | Skeleton live on Render; every API answered once |
| T+0:25–1:25 | **ClickHouse core:** metrics + events tables; replay script bulk-inserting pre-recorded incident_metrics.csv at 10× (DEFAULT path, not fallback); LAG/LEAD causal SQL; Langfuse spans on queries | Causal query names DB-pool exhaustion as the 4m10s precursor |
| T+1:25–2:40 | **Agent core:** seed Senso (3 runbooks, 2 postmortems, ownership map); Guild incident agent state machine (Investigating→Mitigating→Resolved) writing typed events to ClickHouse + Guild audit log; GLiNER2 severity/blast-radius schema extraction at ingestion; GLiGuard screen on outbound text; Senso retrieval; Langfuse `@observe` on every LLM call | Test alert → P-level + services extracted → cited runbook returned |
| T+2:40–3:30 | **Actions + postmortem:** Composio SLACK_SEND_MESSAGE (causal summary) + JIRA_CREATE_ISSUE ("Suggested owner — awaiting confirmation"); postmortem generated from the typed event log + causal SQL + Senso precedents | E2E: alert → Slack post → Resolve → postmortem streams |
| T+3:30–4:10 | **OpenUI timeline:** `npx @openuidev/cli@latest create`; streaming event log, causal-chain highlight, owner-confirm buttons, postmortem panel via SSE | Timeline renders live events; postmortem streams in panel |
| T+4:10–4:50 | **Deploy + history:** 3-service render.yaml green; Airbyte GitHub+Jira 90-day pull into ClickHouse; ownership query wired ("9 of last 12 incidents resolved by @dana-chen"); PagerDuty connector ONLY if ahead of schedule | All services green at public URL |
| T+4:50–5:30 | **Rehearsal gate:** full demo arc ×3 (postmortem complete by 0:30 each run; ≥7 Langfuse waterfall rows; rewind <4s); static-HTML postmortem fallback armed on F2; pre-stage all tabs per demo-scripts.md checklist | 3 clean runs or fallback path re-rehearsed |

## Sponsor → prize mapping ($ estimates from BizDev Round 3, DA-adjusted)

| Prize | $ | Role in IncidentSherpa | Win est. | EV |
|---|---|---|---|---|
| Guild.ai — Most Innovative Use of Agents | $2,800 | Persistent session-scoped agent, typed event log, state machine, credential scoping, append-only audit trail — the strongest single-sponsor alignment in the field | 28% | $784 |
| ClickHouse — Best Use | $1,600 | LAG/LEAD causal-correlation SQL over replayed metrics — the literal "reason over data" judging hint | 42% | $672 |
| Langfuse bonus | $350 | First-class tracing of every LLM call with visible waterfall + costs — essentially uncontested | 72% | $252 |
| Airbyte — Best Use of Agent Engine | $1,750 | GitHub + Jira history → ClickHouse ownership baseline via Context Store | 26% | $455 |
| Pioneer — Best Use | $500 + $1,500 credits | GLiNER2 schema-conditioned severity/blast-radius extraction at the hot path + GLiGuard guardrail on outbound text — dual legitimate touchpoints | 38% | $190 cash |
| Composio — Best Agent Execution | $200 | Slack + Jira multi-app execution, managed OAuth | 40% | $80 |
| Render — Best Use | $1,000 credits | 3-service Blueprint (webhook + worker + frontend), live at T+0:25 | 25% | $250 |
| OpenUI | $2,000 | Load-bearing in the demo but honestly NOT contested as a primary claim | — | — |

**Total EV ≈ $2,683 · Best-case (Guild + ClickHouse + Langfuse + Pioneer) = $5,250 cash + credits.**

## Top 3 risks

1. **Guild SDK/REST availability (threatens the single largest prize, $2,800).** `@guildai/agents-sdk` public-npm availability is UNVERIFIED and the REST session-endpoint shapes are not publicly documented. Mitigation: hard 15-minute go/no-go at T+0:00 with sponsor-rep escalation; written descope path (single Python agent + Guild REST sessions/credentials/audit) keeps Guild load-bearing; LangGraph last resort drops only the Guild prize claim — the build plan and demo are otherwise unaffected.
2. **Demo-claim integrity under CTO Q&A.** Two near-misses were caught in debate (GLiGuard mislabeled as a severity classifier; a fabricated 87ms latency figure). Both fixed, but the pattern is the risk: every number and model-capability claim in the demo must be measured or cited. Mitigation: T+0:15 latency measurement recorded into the demo badge; rehearsal gate verifies every on-screen number against a real trace before recording.
3. **Auth-window compression cascading into the OpenUI block.** Six platform auths in 25 minutes is the plan's tightest assumption; if Guild or Airbyte overruns, the T+1:25–2:40 agent block starts late and squeezes the T+3:30 OpenUI window (the demo anchor). Mitigation: per-platform time caps with named fallbacks (Airbyte→MCP path; Pioneer→local transformers); OpenUI scaffold is `npx`-instant and the static-HTML fallback card means a partially-styled timeline still demos; the postmortem moment — the wow — depends only on the agent core, not the UI polish.

## Stopping conditions — all met (see debate-log.md Round 4)

- sponsors.md: 9/9 sponsors with dated last-30d feature + install command ✅
- ≥2 ideas with all DA axes ≥7: IncidentSherpa 7/7/7/8, ContractCopilot 7/7/7/7 ✅
- Complete 3-min demo scripts + Render deploy plans for both survivors ✅ (demo-scripts.md)
- This file ✅ — **convergence declared after 4 of 6 max rounds.**
