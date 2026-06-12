# Sponsor Intel — Harness Engineering Hack (researched 2026-06-12)

Total prize pool targeted: $18,550+. One line per sponsor marked **NEWEST (last 30d)** per the war-room spec. Items marked UNVERIFIED need on-site confirmation.

---

## Guild.ai — "Most Innovative Use of Agents" — $2,800

- **What it is:** Control plane for AI agents — governance + orchestration layer: define what agents can do, manage access to external systems (GitHub, Jira, Slack, 20+ integrations), audit every run. Primitives: Workspaces, Sessions, Credentials, Triggers. Framework-agnostic (LangChain, CrewAI, OpenAI SDK, own TS SDK).
- **SDK/install:** `npm i @guildai/cli -g` → `guild auth login` → optional `guild setup` (injects Guild skills into Claude Code). Agent code uses `@guildai/agents-sdk` (`import { llmAgent } from "@guildai/agents-sdk"`). UNVERIFIED whether `@guildai/agents-sdk` is on public npm without auth.
- **NEWEST (last 30d):** Nothing verifiably shipped since 2026-05-13. Most recent dated: **2026-04-29 — open beta launch** of the full control plane (Workspaces, Sessions, Credentials, Triggers, Agent Hub, open-source TS SDK). UNVERIFIED whether anything shipped post-May 13.
- **Judging hints:** Likely rewards governance use (credential scoping, audit trails, session management), multi-integration agents, reusable Agent Hub patterns — not raw LLM calls.
- **Integration effort:** RISKY ~45–60 min. Account may need to be "provided by your Guild contact"; browser OAuth; SDK public availability unverified. ~20 min if accounts pre-provisioned at the event. **Flagged: >30 min auth/setup risk.**

## OpenUI by thesys.dev — "Best Use of OpenUI" — $2,000

- **What it is:** Open standard + full-stack framework for Generative UI. Core: OpenUI Lang — streaming-first, line-oriented language for LLMs to emit UIs (~67% more token-efficient than JSON). React runtime, component libraries, CLI scaffolder; integrates with Next.js, Vercel AI SDK, LangChain, CrewAI, Anthropic Agents SDK.
- **SDK/install:** `npx @openuidev/cli@latest create --name my-genui-app` (scaffolds `@openuidev/react-lang`, `@openuidev/react-headless`, `@openuidev/react-ui`). Verified via GitHub thesysdev/openui (6.9k stars).
- **NEWEST (last 30d):** **~2026-05-15 (PR #517) unified-codebase refactor + perf improvements**; ~May 11 JSON-render→OpenUI Lang migration skill; ~May 6 `@openuidev/plotly` viz package. Repo active through June 11. Dates inferred from PR activity — no formal changelog (UNVERIFIED as official releases).
- **Judging hints:** Reward actual OpenUI Lang streaming rendering (not a wrapped chat box), custom component libraries, progressive streaming UI. `@openuidev/plotly` is fresh and underused. Repo ships a SKILL.md for coding agents — they want end-to-end agentic integration.
- **Integration effort:** ~15–20 min. No account/API key for the framework itself (BYO LLM key).

## Senso.ai — "Best Use of Senso.ai" — $2,000 credits

- **What it is:** "Context OS" for agents: ingests raw docs (PDF/DOCX/spreadsheets/MD), normalizes into a verified knowledge base, exposes query endpoints returning cited, grounded answers. Also RAG-verification scoring and brand-representation monitoring across external AIs.
- **SDK/install:** `npm install -g @senso-ai/cli` → `senso whoami`. REST API at `https://sdk.senso.ai/api/v1`, auth via `X-API-Key` header (`SENSO_API_KEY`). No pip package found — use REST from Python (UNVERIFIED whether a Python SDK exists).
- **NEWEST (last 30d):** **No verified feature ship 2026-05-13→06-12.** Current product set per YC page: AI Discovery, Agentic Support, RAG Verification scoring. Confirm latest on-site.
- **Judging hints:** Reward agents that ingest a KB and return cited grounded answers; RAG-verification scoring for answer quality. Free $100 tier, no credit card.
- **Integration effort:** ~20–25 min. Friction: docs gated behind sign-in — confirm endpoint shapes on-site.

## Airbyte — "Best Use of Agent Engine" — $1,750

- **What it is:** Agent Engine = fully-managed data layer for agents: structured real-time access to Salesforce, HubSpot, GitHub, Jira, Slack, Gong, Zendesk, Stripe + 50+ connectors. Core primitive: **Context Store** — pre-indexed searchable layer, <500ms entity discovery, ~40% fewer tool calls / up to 80% fewer tokens (vendor claims).
- **SDK/install:** `pip install airbyte-agent-sdk` (PyPI verified; v0.1.221, 2026-04-29; Python ≥3.10). `from airbyte_agent_sdk import Workspace, connect`. Env: `AIRBYTE_CLIENT_ID`, `AIRBYTE_CLIENT_SECRET`. CLI: `curl -sSL https://get.airbyte.com/agent | bash` (URL pattern UNVERIFIED). MCP interface available.
- **NEWEST (last 30d):** **2026-06-11 — connector-metadata inspection API + CLI `connectors inspect` + improved semantic search precision**; 06-09 Gong speaker-turn transcript search + billing protection; 06-05 MCP workspace tools, read-only MCP ops approval-free; 06-03 Jira OAuth 2.0; 06-01 CLI launch (one-line installer, browser auth); 05-04 full Agents platform launch.
- **Judging hints:** Reward Context Store pre-indexed search (not live API fetch), multi-connector correlation workflows, the new MCP interface. June CLI + MCP tools are fresh and underused.
- **Integration effort:** RISKY ~30–45 min (Cloud account + client credentials provisioning). **Flagged: borderline >30 min auth/setup.** MCP path may be faster.

## ClickHouse — "Best Use of ClickHouse" — $1,600 (+ Langfuse bonus $350)

- **What it is:** Real-time columnar OLAP DB. For this hack: (1) **ClickHouse Agents** — managed agentic analytics on ClickHouse Cloud (Claude-powered, public beta since 2026-05-27, MCP-native, no-code builder, sandboxed code interpreter); (2) **Langfuse** — open-source LLM observability/tracing, acquired by ClickHouse Jan 2026, runs on ClickHouse Cloud.
- **SDK/install:** `pip install clickhouse-connect` (v1.3.0, 2026-06-11) / `pip install "clickhouse-connect[async]"`; CLI: `curl https://clickhouse.com/cli | sh` then `clickhousectl local install stable`; `pip install langfuse` (v4.7.1, 2026-05-29); `pip install mcp-clickhouse`.
- **NEWEST (last 30d):** **2026-05-27 — ClickHouse Agents public beta** (Open House Day 1; also clickhousectl in Cursor/Claude Code, Query API Endpoints with MCP tooling, MV pipeline visualization); 05-28 clickhouse-connect v1.0 GA native async, ClickStack AI Notebooks beta, ClickStack MCP server; 05-21 ClickHouse 26.5 (atomic `CREATE OR REPLACE MATERIALIZED VIEW`, Kafka2 SELECT, `/webterminal`); 05-29 Langfuse v4.7.1 (tool-call visibility, in-app agent tracing); 06-11 clickhouse-connect v1.3.0.
- **Judging hints (from their own hackathon writeups):** Agents that **reason over data** not just retrieve; tool-using agents over ClickHouse; "evaluated with Langfuse" explicitly called out; functional MVPs beat ambitious-but-broken. MCP tooling prioritized.
- **Integration effort:** ~20–30 min. Cloud free trial no-CC; Langfuse cloud free tier. Risk: ClickHouse Agents beta seat/quota — verify at event.

## TrueFoundry — "Best Use of TrueFoundry" — $1,000

- **What it is:** Enterprise AI Gateway + MCP Gateway: centralized access, routing, cost governance, guardrails, and observability across LLM providers and MCP servers, behind a unified OpenAI-compatible API (base-URL swap).
- **SDK/install:** Use standard `openai` SDK pointed at the gateway (`base_url` + PAT). MCP ops: `pip install fastmcp`. Platform/deploy SDK: `pip install truefoundry` (v latest 2026-05-08).
- **NEWEST (last 30d):** **2026-06-09 — Claude Fable 5 available through TrueFoundry AI Gateway** (unified API, cost governance, auto-failover; verified blog post); 05-22 v0.146.6 — Skills Registry for agents, agent max-execution-time auto-abort, guardrail metrics API, deterministic latency-based routing; 05-18 v0.144.0 SCIM/JIT provisioning.
- **Judging hints:** Reward gateway-as-control-layer: resilience (auto-fallback on provider/MCP failure), guardrails on tool-call inputs/outputs, cost budgets per virtual account. **Virtual MCP Server** (combine tools from multiple MCP servers into one curated endpoint) explicitly called out as underused.
- **Integration effort:** ~15 min (account + PAT; gateway UI pre-fills a code snippet).

## Render — "Best Use of Render" — $1,000 credits

- **What it is:** Cloud hosting: web services, background workers, cron jobs, managed Postgres; git-push-to-deploy; multi-service Blueprint YAML (`render.yaml`).
- **SDK/install:** `brew install render` (CLI v2.20.0, 2026-06-05). Python/TS SDKs exist at github.com/render-oss/sdk (package names UNVERIFIED).
- **NEWEST (last 30d):** **2026-06-11 — Docker build times cut 60% (median 87s→~32s)**; 06-05 CLI v2.20.0 with `render ea pg ...` Postgres management commands + OIDC for AWS auth (Pro, early access); 06-02 ephemeral SSH (`render ssh --ephemeral`). All verified via changelog.
- **Judging hints:** Actual deploy to Render (not localhost), multi-service Blueprint (web + worker + Postgres in one `render.yaml`), native features (cron jobs, private services).
- **Integration effort:** ~10 min first deploy via UI; ~20 min for Blueprint multi-service. Free tier, no CC.

## Pioneer by Fastino — "Best Use of Pioneer" — $500 + $1,500 credits

- **What it is:** Agentic fine-tuning + adaptive inference platform for small open models (Qwen, Gemma, Llama, Nemotron, GLiNER). Agent Mode: one prompt → synthetic data gen, hyperparameter selection, eval, deploy. Deep Research Mode: autonomous data gathering + parallel experiments.
- **SDK/install:** REST-only, no pip/npm. Account at pioneer.ai → API key → `export PIONEER_API_KEY=...`. Inference: `POST https://api.pioneer.ai/inference` with `X-API-Key` (e.g. `model_id: fastino/gliner2-base-v1` + schema). Fine-tune: `POST /felix/training-jobs`. Verified via docs.pioneer.ai.
- **NEWEST (last 30d):** **2026-05-14 — Fastino open-sourced GLiGuard (300M-param 4-task safety/jailbreak/harm/refusal moderation, 16–20× faster than prior SOTA) and GLiNER2-PII (300M-param multilingual PII detection, 42 entity types, 7 languages, top span-level F1)** — both on Hugging Face (Apache 2.0) and servable on Pioneer. Verified PR Newswire 2026-05-14. No June platform feature found.
- **Judging hints:** Reward task-specific fine-tune/small-model use over frontier-model calls; show accuracy/cost/latency win vs GPT-4-class. GLiGuard/GLiNER2-PII inference is the fast path.
- **Integration effort:** ~20–30 min first inference; ~45 min for a minimal fine-tune incl. data prep. **Flagged: fine-tune path >30 min; watch for 402 if no credits.**

## Composio — "Best Agent Execution" — $200

- **What it is:** 1,000+ pre-built tool integrations (GitHub, Slack, Gmail, Notion, Linear…) with managed OAuth so agents act on users' behalf; supports all major agent frameworks.
- **SDK/install:** `pip install composio` (v0.13.1, 2026-05-26) or `npm install @composio/core`; CLI `npm install -g @composio/cli` (v0.2.31, 2026-06-09). `COMPOSIO_API_KEY` env var. Pattern: `Composio().create(user_id=...)` → `session.tools()`. **Use `link()` not `initiate()`** (cutover 2026-07-03; legacy v1/v2 endpoints already 410).
- **NEWEST (last 30d):** **2026-06-04 — security/platform overhaul: scoped API keys, IP whitelisting, signed webhooks, MCP requests require auth, legacy endpoints removed**; 06-09 CLI v0.2.31; 05-26 SDK v0.13.1 with experimental Shared Connected Accounts; 05-12 programmatic OAuth token revocation.
- **Judging hints (prior hackathons):** Integration depth (multiple apps orchestrated together), creative workflow, practical usefulness. "Best Agent Execution" = agent must *execute* multi-step tasks across real tools, not just plan.
- **Integration effort:** ~10 min first tool call; +5–10 min browser OAuth per connected app. MCP usage needs API-key auth header (June 4 change).
