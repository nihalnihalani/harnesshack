# API Keys & Credits — Acquisition Guide

Harness Engineering Hack, June 12 2026. Sources: hackathon Discord (per-sponsor channels), the ClickHouse slide deck (`AI Hackathon 2026.pdf`), harness-hack.devpost.com, and `sponsors.md` (verified research, 2026-06-12). Every key lands in `.env` (repo root) — `curl localhost:8000/health` shows per-dependency `blocked`/`configured` and works as the live checklist.

## Priority order (do top to bottom)

| # | Service | Status | Why this rank | Time |
|---|---|---|---|---|
| 1 | Anthropic credits | ⏳ form submitted ~12:45 PM, awaiting email | Signup links EXPIRED 12:00 PM PT — escalate via #anthropic rep if no reply by ~1:15 | 5 min + wait |
| 2 | Langfuse promo | ✅ **DONE 12:55 PM** — keys in `.env`, test span verified | Code `HARNESSHACK2026` "needs to be used TODAY" per ClickHouse slides | 10 min |
| 3 | ClickHouse Cloud | ✅ **DONE 1:10 PM** — creds in `.env`, SELECT 1 verified, schema applied (events/metrics/airbyte_history) | $400 credits via QR — **QR not yet redeemed, account on 30-day trial; scan slide 9 to stack the credits** | 10 min |
| 4 | Pioneer promo | ❌ | Code `SFJune2026Tokens` = Pro plan with $1,500 inference credits; blocks GLiNER2 hot path | 10 min |
| 5 | Render credits | ❌ | $100 claim link live now; **prize requires Render Workflows** (see below) | 5 min |
| 6 | Senso | ❌ | Challenge requires publishing output to cited.md; $100 free tier, no CC | 10 min |
| 7 | Guild | ❌ | 50M free tokens on signup, self-serve (easier than feared); REST path confirmed | 15 min |
| 8 | Composio | ❌ | API key + browser OAuth for Slack/Jira — OAuth takes minutes, do before crunch | 15 min |
| 9 | Airbyte | ❌ | Free tier 1,000 agent ops/month is "enough" per their rep; MCP fallback exists | 15 min |
| — | OpenUI | n/a | NO API key needed (BYO LLM key) | 0 |
| — | TrueFoundry | skip | Free to use; only if we add it — not in current architecture | 15 min |
| — | Jua | skip | SKIP — no prize, forces paid subscription | — |

## Submission requirements (deadline 4:30 PM PDT, harness-hack.devpost.com)

- 3-minute demo recording + all Devpost fields
- **Public GitHub repo** (ours is currently PRIVATE — flip before submitting)
- Render URL (per #render: "Submissions: 1. Github URL/s, 2. Render URL, 3. Video demo")

Judging: 5 criteria × 20% each — Idea, Technical Implementation, Tool Use (≥3 sponsor tools), Presentation (3-min demo), Autonomy (acts on real-time data without manual intervention).

---

## 1. Anthropic (`ANTHROPIC_API_KEY`) — ~$35 credits

**Status: ⏳ form submitted ~12:45 PM June 12, no email yet.** If nothing by ~1:15 PM, ping **bruh-moment** in #anthropic and email gagan@anthropic.com in parallel. Backup: Nihal's credits were approved at 11:54 AM — a key from his Console unblocks the app meanwhile.

1. Form: https://forms.gle/gNGK5EBDYymUWxaGA → single-use claude.com/offers link emailed to the Google account you submit with. One link per person. **Links expired June 12, 12:00 PM PT.**
2. If expired/rejected: ping the Anthropic rep **bruh-moment** in #anthropic (he approved a rejected request in ~2 min at 11:54 AM) or email **gagan@anthropic.com**.
3. Rejection pitfalls: must provide a **Claude Console Organization ID** (console.anthropic.com → Settings), NOT a claude.ai account; use a company email if possible.
4. Credits cover Claude Code, Agent SDK, and 1P API. Key: console.anthropic.com → API keys.
5. Verify: 1-token `claude-fable-5` message call.

## 2. Langfuse (`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`) — prize now $500

**Status: ✅ DONE 12:55 PM June 12.** Project `0612hack` (Hobby plan) on charlie.gillet1@gmail.com; keys in `.env` (`LANGFUSE_HOST` + `LANGFUSE_BASE_URL` both set); `auth_check()` passed and a test span was emitted + flushed (trace `2c9acb03653ec591c8f4adf6c5b163d3`). NOT yet on paid tier — the `HARNESSHACK2026` promo applies only at Langfuse Core checkout (today-only); Hobby suffices for tracing and the prize, upgrade optional.

1. Promo code **`HARNESSHACK2026`** at the Langfuse Core subscription checkout (paid tier, unlimited seats) — ClickHouse slides say it **must be used today**.
2. cloud.langfuse.com → new org/project → Settings → API keys. `LANGFUSE_HOST=https://cloud.langfuse.com`.
3. "Most impressive use of Langfuse" prize was raised from $350 to **$500** (Andy Tran, 11:20 AM).
4. Verify: one test span visible in the dashboard (`libs/tracing.py` already wired).
5. SDK heads-up (v4.7.1, installed in `.venv`): span helper is `start_as_current_observation(name=..., as_type="span")` — `start_as_current_span` does NOT exist in v4.

## 3. ClickHouse Cloud (`CLICKHOUSE_HOST/USER/PASSWORD`) — $400 credits

**Status: ✅ DONE 1:10 PM June 12.** Service `0612hack`, AWS us-west-2, user `default`, creds in `.env` (password ends in a literal `.` — it's part of the password). Verified via curl AND `clickhouse_connect`; all three tables from `libs/clickhouse/schema.py` applied. Account is on the 30-day trial — the $400 QR credits (slide 9 of the PDF) have NOT been redeemed yet.

1. **$400 total credits via the QR code on slide 9 of `AI Hackathon 2026.pdf`** (in Downloads; scan with phone).
2. **Use a NEW email / fresh account** — slide explicitly says past cloud accounts don't get credits. GitHub account required for the OSS path.
3. Signup → service → host + user + password into `.env`.
4. Their prize lens (slide 8): "Impact in our community/World, improving lives — useful and impactful." Team #1 also gets to speak at ClickHouse demo AI night July 1st.
5. Reps on-site: Zoe, Sherry, Lotte — front by the podium. Docs AI assistant: clickhouse.com/docs (kapa.ai widget).
6. Verify: `SELECT 1` via `clickhouse_connect`.

## 4. Pioneer / Fastino (`PIONEER_API_KEY`) — Pro plan w/ $1,500 inference credits

1. Promo code **`SFJune2026Tokens`**: https://agent.pioneer.ai → **Get Pro plan** → Stripe checkout → enter promo code (rep Thao confirmed flow).
2. API key: pioneer.ai → Settings → API Keys. REST only — `POST https://api.pioneer.ai/inference`, `X-API-Key` header.
3. Claude Code / coding-agent integration + new model router (open beta): https://docs.pioneer.ai/claude-code
4. Onboarding Notion (prize details): https://wholesale-mackerel-22f.notion.site/EXT-Harness-Engineering-Hackathon-Onboarding-37c8413d474480909f4be6cee9c96ff9
5. Reps: Dhruv, Thao. 402 error → local `transformers` fallback (GLiNER2/GLiGuard are Apache-2.0), label honestly as local inference.
6. Verify: GLiNER2 severity-schema call — **record the measured latency for the demo badge**.

## 5. Render (CLI login, no env var) — $100 credits, 3 prizes in Render credits

1. Claim credits: **https://credits-portal-mmdm.onrender.com/claim/harness-engineering-hack**
2. Signup: https://render.com/register?utm_source=partner&utm_medium=events&utm_campaign=2026_event_harness_hack
3. **MUST USE Render Workflows to win prizes** (rep Ojus, verbatim). Our Blueprint (web + worker + cron) is NOT a Workflow — we need to add one (see ARCHITECTURE DECISION below).
4. Coding-agent skills: https://render.com/docs/llm-support · Templates: https://render.com/templates
5. Prizes: $1000 / $600 / $400 in Render credits. Rep: Ojus (x.com/ojusave).
6. Verify: `render whoami`, then Blueprint deploy + public URL (the URL goes in the submission).

## 6. Senso (`SENSO_API_KEY`) — challenge-required via cited.md, 2k credits prize

1. senso.ai signup — $100 free tier, no credit card. Key is `X-API-Key` against `https://sdk.senso.ai/api/v1`.
2. Docs: https://docs.senso.ai/docs/introduction (ingest content, AI search, agent-ready output, **publish to cited.md**).
3. The challenge statement requires publishing agent output to cited.md — this is the integration that satisfies it.
4. Rep: Saroop. Verify: `senso whoami` / REST doc list.

## 7. Guild (`GUILD_PAT`, `GUILD_API_BASE`) — $2,800 top prize track

1. app.guild.ai signup — **every new account gets 50M Guild tokens free**; rep **Cory** grants more on request (#guild-ai).
2. Docs: docs.guild.ai. PAT via `npm i @guildai/cli -g && guild auth login`.
3. `@guildai/agents-sdk` is on Guild's PRIVATE npm registry (401/404 publicly — verified twice). The REST descope path in `libs/guild/` stands; SDK is an optional upgrade if the PAT grants registry access.
4. Verify: REST session-create probe.

## 8. Composio (`COMPOSIO_API_KEY`) — $200 prize

1. composio.dev dashboard → API key. **No event credits — docs only** (Andy Tran confirmed).
2. Docs: https://docs.composio.dev/docs. Then run `session.link()` flows for Slack (chat:write) and Jira (create) — browser OAuth, do it before the crunch. Never `initiate()` (deprecated, 410).
3. Verify: link() status for both apps.

## 9. Airbyte (`AIRBYTE_CLIENT_ID/SECRET`) — $1,750 track

1. Free tier: **1,000 Agent Operations/month — "should be enough"** per rep Richelle; connectors are NOT tier-gated.
2. cloud.airbyte.com → Settings → Applications → client ID + secret.
3. Docs: https://docs.airbyte.com/ai-agents/ · SDK: /interfaces/sdk/ · API: /interfaces/api/ · Quickstart+skills: /get-started/developer-quickstart/ · GitHub: airbytehq/airbyte-agent-sdk
4. Reps: Richelle, Ian. Verify: workspace list + GitHub/Jira connector visibility. MCP fallback if cap overruns.

## OpenUI — no key; $2,000 prize, 2 winners + 5 honorable mentions

- **No separate API key** (rep Ritvik, verbatim). Works with any OpenAI-format provider; for Claude use Anthropic's OpenAI-compatible endpoint (platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk) or OpenRouter BYOK (openrouter.ai/docs/guides/overview/auth/byok).
- Prize criterion: **most unique use case** — anything beyond the stock examples (niche components, new modalities, new surfaces, MCP). Examples: github.com/thesysdev/openui/tree/main/docs · custom components: openui.com/docs/openui-lang/defining-components
- Reps: visharad, zahle(thesys), Ritvik (opposite the pantry, grey "thesys" shirt).

## TrueFoundry — optional; prize is $1k platform credits (not cash)

- Free to use; resources: https://linktr.ee/tfaigateway · gateway: truefoundry.com/docs/ai-gateway/openai · MCP: /ai-gateway/mcp/mcp-overview · agent harness: /ai-gateway/agent-harness/overview
- Out-of-credits fallback their rep suggests: build.nvidia.com open-source models. Rep: Sai.
- Not in our architecture; only add if a gateway layer becomes load-bearing.

## Jua — SKIP

No prize for best use of Jua (organizer, verbatim); `jua auth` forces a paid subscription; no promo code.

---

## ARCHITECTURE DECISION NEEDED: Render Workflows

The Render prize requires **Render Workflows** (their durable-execution product), which our 3-service Blueprint does not use. Cheapest honest integration: run a real pipeline step — e.g., postmortem generation or the seed/replay job — as a Render Workflow task instead of (or alongside) the background worker. Decide before Phase 7 (Render deploy).

## Prize table (devpost, $17,550+ cash total, 91 participants)

| Track | Pool | Structure |
|---|---|---|
| Most Innovative Use of Agents (Guild.ai) | $2,800 | Visa: 1×$1000, 2×$500, 4×$200 |
| Best Use of OpenUI | $2,000 | $1000, $500, 5×$100 HM |
| Conquer with Context (Airbyte Agent Engine) | $1,750 | $1000 / $500 / $250 Visa |
| Best Use of ClickHouse | $1,600 | T1: $1000 + $500 credits + July 1 demo-night talk; T2: $250 + $500 credits; Langfuse: $500 |
| Best Use of Render | credits | $1000 / $600 / $400 Render credits — Workflows required |
| Best Use of Pioneer | $500 | + Pro-plan promo ($1,500 inference credits) |
| Best Use of TrueFoundry | credits | $1k platform credits |
| Best Agent Execution (Composio) | $200 | Amazon gift card |
| Best use of Senso.ai | credits | 2k in credits |
