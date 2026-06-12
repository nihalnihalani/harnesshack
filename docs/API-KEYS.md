# API Keys & Credits — Acquisition Guide

Harness Engineering Hack, June 12 2026. Sources: hackathon Discord (per-sponsor channels), the ClickHouse slide deck (`AI Hackathon 2026.pdf`), harness-hack.devpost.com, and `sponsors.md` (verified research, 2026-06-12). Every key lands in `.env` (repo root) — `curl localhost:8000/health` shows per-dependency `blocked`/`configured` and works as the live checklist.

## Priority order (do top to bottom)

| # | Service | Status | Why this rank | Time |
|---|---|---|---|---|
| 1 | Anthropic credits | ✅ **DONE 1:30 PM** — key in `.env`, claude-fable-5 call verified (end_turn) | Signup links EXPIRED 12:00 PM PT — credits landed via the form anyway | 5 min + wait |
| 2 | Langfuse promo | ✅ **DONE 12:58 PM** — keys in `.env`, test span verified | Code `HARNESSHACK2026` "needs to be used TODAY" per ClickHouse slides | 10 min |
| 3 | ClickHouse Cloud | ✅ **DONE 1:19 PM** — creds in `.env`, SELECT 1 verified, schema applied (events/metrics/airbyte_history) | $400 credits via QR — **QR not yet redeemed, account on 30-day trial; scan slide 9 to stack the credits** | 10 min |
| 4 | Pioneer promo | ✅ **DONE 2:08 PM** — Pro active via promo ($0.00 invoice), GLiNER2 **134–180ms measured**, GLiGuard verified | Code `SFJune2026Tokens` = Pro plan with $1,500 inference credits; blocks GLiNER2 hot path | 10 min |
| 5 | Render credits | ✅ **DONE 2:14 PM** — $100 promo `HTHON100-847F12` redeemed (valid → May 31 2027); CLI logged in, workspace `Charlie's workspace` set, `render whoami` ✓ | $100 claim link live now; **prize requires Render Workflows** (see below) | 5 min |
| 6 | Senso | ✅ **DONE 2:25 PM** — key in `.env`, org `0612hack` (Free tier) verified via `senso whoami`/`org get` | Challenge requires publishing output to cited.md; $100 free tier, no CC | 10 min |
| 7 | Guild | ✅ **DONE 1:23 PM** — PAT in `.env`, workspace `0612hack` selected, session API probed | 50M free tokens on signup, self-serve (easier than feared); REST path confirmed | 15 min |
| 8 | Composio | ✅ **DONE 2:58 PM** — key in `.env`, Slack + Jira OAuth both ACTIVE, real Slack post + Jira `SCRUM-1` sent live | API key + browser OAuth for Slack/Jira — OAuth takes minutes, do before crunch | 15 min |
| 9 | Airbyte | ✅ **DONE 2:19 PM** — app `0612hack` creds in `.env`, agent-API token grant ✓, 575 connectors listed | Free tier 1,000 agent ops/month is "enough" per their rep; MCP fallback exists | 15 min |
| — | OpenUI | n/a | NO API key needed (BYO LLM key) | 0 |
| — | TrueFoundry | skip | Free to use; only if we add it — not in current architecture | 15 min |
| — | Jua | skip | SKIP — no prize, forces paid subscription | — |

## Submission requirements (deadline 4:30 PM PDT, harness-hack.devpost.com)

- 3-minute demo recording + all Devpost fields
- **Public GitHub repo** (ours is currently PRIVATE — flip before submitting)
- Render URL (per #render: "Submissions: 1. Github URL/s, 2. Render URL, 3. Video demo")
- **⚠️ MUST explicitly SELECT each sponsor prize on Devpost to be considered for it** (organizer slide). Un-ticked tracks aren't judged — tick EVERY track we target: Guild, ClickHouse+Langfuse, Airbyte, OpenUI, Pioneer, Composio, Senso, Render. Missing a box = forfeiting that prize regardless of build quality.
- ONE submission per team; EVERY team member must be individually registered on Devpost. Submission questions → "Andy from Senso".

Judging: 5 criteria × 20% each — Idea, Technical Implementation, Tool Use (≥3 sponsor tools), Presentation (3-min demo), Autonomy (acts on real-time data without manual intervention).

---

## 1. Anthropic (`ANTHROPIC_API_KEY`) — ~$35 credits

**Status: ✅ DONE 1:30 PM June 12.** Credits landed despite the noon link expiry; key in `.env`. Verified with a live `claude-fable-5` Messages call (`stop_reason: end_turn`, 16 in / 16 out tokens). Note: credits are ~$35 and Fable 5 is $10/$50 per MTok — postmortem drafting only, GLiNER2 stays the hot path (which is the architecture anyway).

1. Form: https://forms.gle/gNGK5EBDYymUWxaGA → single-use claude.com/offers link emailed to the Google account you submit with. One link per person. **Links expired June 12, 12:00 PM PT.**
2. If expired/rejected: ping the Anthropic rep **bruh-moment** in #anthropic (he approved a rejected request in ~2 min at 11:54 AM) or email **gagan@anthropic.com**.
3. Rejection pitfalls: must provide a **Claude Console Organization ID** (console.anthropic.com → Settings), NOT a claude.ai account; use a company email if possible.
4. Credits cover Claude Code, Agent SDK, and 1P API. Key: console.anthropic.com → API keys.
5. Verify: 1-token `claude-fable-5` message call.

## 2. Langfuse (`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`) — prize now $500

**Status: ✅ DONE 12:58 PM June 12.** Project `0612hack` (Hobby plan) on charlie.gillet1@gmail.com; keys in `.env` (`LANGFUSE_HOST` + `LANGFUSE_BASE_URL` both set); `auth_check()` passed and a test span was emitted + flushed (trace `2c9acb03653ec591c8f4adf6c5b163d3`). NOT yet on paid tier — the `HARNESSHACK2026` promo applies only at Langfuse Core checkout (today-only); Hobby suffices for tracing and the prize, upgrade optional.

1. Promo code **`HARNESSHACK2026`** at the Langfuse Core subscription checkout (paid tier, unlimited seats) — ClickHouse slides say it **must be used today**.
2. cloud.langfuse.com → new org/project → Settings → API keys. `LANGFUSE_HOST=https://cloud.langfuse.com`.
3. "Most impressive use of Langfuse" prize was raised from $350 to **$500** (Andy Tran, 11:20 AM).
4. Verify: one test span visible in the dashboard (`libs/tracing.py` already wired).
5. SDK heads-up (v4.7.1, installed in `.venv`): span helper is `start_as_current_observation(name=..., as_type="span")` — `start_as_current_span` does NOT exist in v4.

## 3. ClickHouse Cloud (`CLICKHOUSE_HOST/USER/PASSWORD`) — $400 credits

**Status: ✅ DONE 1:19 PM June 12.** Service `0612hack`, AWS us-west-2, user `default`, creds in `.env` (password ends in a literal `.` — it's part of the password). Verified via curl AND `clickhouse_connect`; all three tables from `libs/clickhouse/schema.py` applied. Account is on the 30-day trial — the $400 QR credits (slide 9 of the PDF) have NOT been redeemed yet.

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
5. Reps: Dhruv, Thao. 402/403 error → local `transformers` fallback (GLiNER2/GLiGuard are Apache-2.0), label honestly as local inference.
6. Verify: GLiNER2 severity-schema call — **record the measured latency for the demo badge**.
7. **Gotchas found live (June 12):** account signup grants Partner-plan "$50/day free credits" in the UI, but ALL API calls (even `/v1/models`) return 403 `card_verification_required` until a Hobby/Pro plan is active — the promo code is entered at the Pro-plan Stripe checkout (agent.pioneer.ai/billing). Pro via promo invoices $0.00 and auto-cancels in one month.
8. **VERIFIED API shapes (June 12, 2:08 PM):** encoder models run on `POST https://api.pioneer.ai/inference` with `X-API-Key` (they are NOT in `/v1/models`, which lists 70 chat models behind the OpenAI-compatible router):
   - GLiNER2: `{"model_id": "fastino/gliner2-base-v1", "text": ..., "schema": {"entities": ["service"], "classifications": [{"task": "severity", "labels": ["P0","P1","P2","P3"]}]}}` → returns labeled spans + classification with confidences and server `latency_ms`. **Measured 134–180ms across 3 calls** (the demo-badge number).
   - GLiGuard: `{"model_id": "fastino/gliguard-LLMGuardrails-300M", "text": ..., "schema": {"classifications": [{"task": "prompt_safety", "labels": ["safe","unsafe"], "multi_label": false, "threshold": 0.5}]}}` → `safe` @ 0.9998 on a sample incident update; 426ms server-side on the cold first call (wall 13.7s — warm it before the demo).

## 5. Render (CLI login, no env var) — $100 credits, 3 prizes in Render credits

**Status: ✅ DONE 2:14 PM June 12.** Credits: promo `HTHON100-847F12` → $100 "Hackathon Participant" balance, valid until May 31, 2027. CLI v2.20.0 installed via brew, device-flow login approved, active workspace `Charlie's workspace` (`tea-d8m7c767r5hc73f1sb0g`), `render whoami` verified. Remaining for Phase 7: Blueprint deploy + the **Render Workflows** component for prize eligibility.

1. Claim credits: **https://credits-portal-mmdm.onrender.com/claim/harness-engineering-hack**
2. Signup: https://render.com/register?utm_source=partner&utm_medium=events&utm_campaign=2026_event_harness_hack
3. **MUST USE Render Workflows to win prizes** (rep Ojus, verbatim). Our Blueprint (web + worker + cron) is NOT a Workflow — we need to add one (see ARCHITECTURE DECISION below).
4. Coding-agent skills: https://render.com/docs/llm-support · Templates: https://render.com/templates
5. Prizes: $1000 / $600 / $400 in Render credits. Rep: Ojus (x.com/ojusave).
6. Verify: `render whoami`, then Blueprint deploy + public URL (the URL goes in the submission).

## 6. Senso (`SENSO_API_KEY`) — challenge-required via cited.md, 2k credits prize

**Status: ✅ DONE 2:25 PM June 12.** Key (`tgr_…` prefix) in `.env`; org `0612hack` (org_id `73c7ce83-…`, Free tier, website `https://incidentsherpa.onrender.com`). Verified with `senso whoami` + `senso org get` (CLI v0.11.1; auth via `SENSO_API_KEY` env var — the interactive `senso login` does NOT accept piped stdin). **Deliberately did NOT run the `senso-onboarding` skill** from their signup prompt: it's a marketing autopilot (researches a "company," generates brand kit + content drafts, publishes sample marketing citeables, starts GEO monitoring) and would pollute the KB. Our KB gets runbooks/ownership/postmortems via `scripts/seed_senso.py` at Phase 3.

1. senso.ai signup — $100 free tier, no credit card. Key is `X-API-Key` against `https://sdk.senso.ai/api/v1`.
2. Docs: https://docs.senso.ai/docs/introduction (ingest content, AI search, agent-ready output, **publish to cited.md**).
3. The challenge statement requires publishing agent output to cited.md — this is the integration that satisfies it.
4. Rep: Saroop. Verify: `senso whoami` / REST doc list.

## 7. Guild (`GUILD_PAT`, `GUILD_API_BASE`) — $2,800 top prize track

**Status: ✅ DONE 1:23 PM June 12.** Account `charliegillet`, workspace `0612hack` (set as CLI default). PAT (151-char `u.…` token from `guild auth token`) + `GUILD_API_BASE=https://app.guild.ai` in `.env`; authenticated `guild session list` succeeded.

1. app.guild.ai signup — **every new account gets 50M Guild tokens free**; rep **Cory** grants more on request (#guild-ai).
2. Docs: docs.guild.ai. PAT via `npm i @guildai/cli -g && guild auth login` (device flow), then `guild auth token`.
3. SDK finding (updated): login configured Guild's private registry in `~/.npmrc` under scopes `@guildai-agents`/`@guildai-services` — but `@guildai/agents-sdk` AND the obvious candidates under those scopes all 404 even authenticated. **REST/CLI descope path stands.** Ask rep Cory for the real SDK package name if we want the upgrade.
4. Phase-3 implementation options discovered in the CLI: full `guild session` group (create/get/events/tasks/send/interrupt), `guild credentials`, `guild trigger`, **`guild mcp`** (stdio MCP server — could be the cleanest agent integration), `guild setup` (injects Guild skills into Claude Code).
5. Verified: authenticated session-list probe against workspace `0612hack`.

## 8. Composio (`COMPOSIO_API_KEY`) — $200 prize

**Status: ✅ DONE 2:58 PM June 12.** Key in `.env` (`ak_…`), `COMPOSIO_USER_ID=incident-sherpa`. Slack + Jira connected accounts both ACTIVE; verified with a REAL live send each — Slack message to `#incidents` (ts returned) and Jira ticket `SCRUM-1` created on `incidentsherpa.atlassian.net`. Demo Slack workspace + Jira site are dedicated throwaways (honest: real OAuth, real API, real posts — just a clean stage).

**Live-API contract gotchas (cost an hour; the authored `composio_link.py` + `send.py` both had to be corrected):**
- `toolkits.authorize()` is DEAD — it routes through the retired `connected_accounts.initiate()` endpoint (HTTP 400, "no longer supported"). The working path is `connected_accounts.link(user_id, auth_config_id)` → returns a `redirect_url` the user approves → poll `connected_accounts.list` until `ACTIVE`. Composio-managed auth configs are created with `auth_configs.create(toolkit, options={"type": "use_composio_managed_auth"})`.
- Connect links (`connect.composio.dev/link/...`) expire in ~2 min — generate fresh right before the user clicks.
- `tools.execute(...)` for MANUAL execution needs `dangerously_skip_version_check=True` (else `ToolVersionRequiredError`; `"latest"` is rejected).
- `SLACK_SEND_MESSAGE` rejects `text` — use **`markdown_text`** (or `fallback_text` + blocks).
- `JIRA_CREATE_ISSUE` args that worked: `{project_key, issue_type: "Task", summary, description}`. The demo Jira is a SCRUM/software project → `JIRA_PROJECT_KEY=SCRUM`, issue types are Story/Task/Bug (Task exists).
- `send.py` fixes shipped (markdown_text + skip_version_check); 13 choke-point tests green.

1. composio.dev dashboard → API key. **No event credits — docs only** (Andy Tran confirmed).
2. Docs: https://docs.composio.dev/docs. Then authorize Slack (chat:write) + Jira (create) via `connected_accounts.link()` (NOT `authorize()`/`initiate()` — both dead).
3. Verify: `connected_accounts.list(user_ids=[uid])` shows both ACTIVE, then a real `tools.execute` send.

## 9. Airbyte (`AIRBYTE_CLIENT_ID/SECRET`) — $1,750 track

**Status: ✅ DONE 2:19 PM June 12.** Application `0612hack` (user-level settings, NOT workspace settings — cloud.airbyte.com/settings/applications). Verified: token grant at `POST https://api.airbyte.ai/api/v1/account/applications/token` (the **Agent-Engine** API host — note the `.ai` TLD; `api.airbyte.com/v1/applications/token_grant` 401s for these app creds, and the Keycloak endpoint at cloud.airbyte.com also works) → authenticated `GET /api/v1/integrations/definitions/sources` returned 575 connectors. The dashboard "Generate access token" button is unnecessary — tokens are minted programmatically from the ID+secret.

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
