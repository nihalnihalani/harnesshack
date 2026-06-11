# Harness Engineering Hack — Final 2 Ideas (EV-Maximizing)

> Mission: produce the 2 ideas with maximum expected prize money that **survived** brutal
> attack. Theme: "agents and AI systems, end to end on real infra." Event: June 12 2026.
> Method: Problem Bank (cited) → 10 ideas → kill 4 → 6 dossiers → debate bracket → Final 2.
>
> **EV = Σ_tracks(prize $ × P(win)) × P(ship a working demo by 3:45 PM, 2-person-days).**
> An idea that *locks* 2 tracks beats one that *gestures* at 6. Every extra track claimed is
> one more A1 (fake-integration) attack surface, not a virtue.
>
> The repo (`harnesshack`) is currently empty — a blank asset, **not** a vote for any idea.

---

## PHASE 0 — PROBLEM BANK (cited; practitioner/incident evidence prioritized)

| # | Problem (one line) | Evidence (link + date) | Who suffers | Why unsolved | Natural tracks |
|---|---|---|---|---|---|
| P1 | RAG/agent context goes stale — decisions made on yesterday's data | Gartner "60% of AI projects abandoned for lack of AI-ready data" via [ragaboutit.com, 2025](https://ragaboutit.com/the-rag-freshness-paradox-why-your-enterprise-agents-are-making-decisions-on-yesterdays-data/); [nexla.com, 2025](https://nexla.com/blog/real-time-context-ai-agents-batch-data-fails) (vendor) | Enterprise RAG pilots on batch ETL | Real-time indexing + freshness *monitoring* harder than periodic reindex; "retrieval accuracy" ≠ "decision currency" | Airbyte, ClickHouse, Senso |
| P2 | Ungoverned tool calls — agent deletes prod DB despite an explicit freeze | [The Register, 2025-07-21](https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/); [AI Incident DB #1152](https://incidentdatabase.ai/cite/1152/) — Replit agent ignored ALL-CAPS freeze, deleted ~1,200 records, fabricated ~4,000 fake users | Teams giving agents live creds, no human-in-loop | Guardrails are advisory prompt rules the model can override; real enforcement needs action interception *outside* the model | Guild, Composio, ClickHouse/Langfuse |
| P3 | Coding agent wiped prod + backups in 9 seconds, no confirmation | [NeuralTrust post-mortem, 2026](https://neuraltrust.ai/blog/pocketos-railway-agent) (vendor, forensic); [Zenity](https://zenity.io/blog/current-events/ai-agent-database-deletion-pocketos) — agent: "I ran a destructive action without being asked" | Startups w/ blanket-permission CLI tokens | Prompt-based rules don't bind at the infra/permission layer; backups in same blast radius | Guild, Composio |
| P4 | Cost blowup — 2 agents looped 11 days, $47,000 bill, nothing killed it | [agentcost.in, 2025-11](https://agentcost.in/docs/blog/ai-agent-cost-explosions-6-hours-governance/) (vendor): *"Observability tools record; they don't intercept"* | Teams running autonomous loops w/o hard budget caps | Runaway is driven by consumption, not unit price; no real-time pre-call budget gate in most frameworks | TrueFoundry, ClickHouse/Langfuse, Guild |
| P5 | Multi-step agents are black boxes — can't see which step caused a failure | [langchain.com, 2025](https://www.langchain.com/resources/llm-observability-tools) (vendor): error logs "don't flag hallucinations or drift"; [HN 45129237, 2025](https://news.ycombinator.com/item?id=45129237): "zero visibility into user behavior inside their agent" | Engineers triaging prod agent failures | Traces are huge/non-deterministic; tools render the tree but not *why* a step went wrong | ClickHouse, Langfuse, OpenUI |
| P6 | Agents silently regress — model swap drops accuracy 93%→71%, no test fails | [sentrial.com, 2025](https://www.sentrial.com/blog/ai-agent-regression-testing-that-catches-silent-failures) (vendor); AgentAssay [arXiv 2603.02601](https://arxiv.org/abs/2603.02601): "no principled methodology to verify an agent hasn't regressed" | Teams on unpinned hosted models, no CI eval gate | Non-determinism makes pass/fail statistically hard; eval datasets treated as overhead | ClickHouse, Langfuse, Composio |
| P7 | Agent benchmarks are gameable — near-100% scores without solving the task | [HN 44531697, ~379pts, 2025-07](https://news.ycombinator.com/item?id=44531697); [Berkeley RDI audit](https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/) — SWE-bench 100% via Pytest hooks, WebArena ~100% via DOM injection | Teams picking models off leaderboards | Goodhart's Law; agents can read/modify the test harness | Guild, OpenUI, ClickHouse |
| P8 | Non-determinism breaks CI — temp=0 still gives inconsistent output | [arXiv 2602.07150](https://arxiv.org/pdf/2602.07150); [arXiv 2506.09501, 2025-06](https://arxiv.org/pdf/2506.09501) — FP non-associativity, batch/hardware variance break greedy reproducibility | Anyone gating agent behavior in CI | Rooted in inference infra (batching, FP), outside app control; mitigation = average 3+ runs (slow) | ClickHouse, Langfuse |
| P9 | "Context rot" — quality degrades long before the token limit | Chroma 18-model study via [ZenML LLMOps DB, 2025](https://www.zenml.io/llmops-database/context-rot-evaluating-llm-performance-degradation-with-increasing-input-tokens) — all 18 monotonically decline, steepest 100k–500k | Long-running/long-conversation agents | It's a model property, not a bug; per-use-case compaction is hand-engineered | Senso, Airbyte, ClickHouse |
| P10 | Auth/credential sprawl — OAuth + token rot breaks agents mid-day | [truefoundry.com, 2025](https://www.truefoundry.com/blog/oauth-mcp-enterprise-token-management) (vendor); [thenewstack.io, 2025](https://thenewstack.io/why-agentic-llm-systems-fail-control-cost-and-reliability/) — "authentication rot" | Teams wiring agents to many SaaS/per-user identities | New MCP OAuth 2.1 specs outran IdP support; per-server auth doesn't compose w/o a gateway | Composio, Guild, TrueFoundry |
| P11 | Data-integration tax — eng time goes to connectors/auth, not agent behavior | IBM IBV 2025 (>½ execs missed goals on legacy integration) via [airbyte.com, 2025](https://airbyte.com/agentic-data/connect-ai-agents-to-existing-data-sources) (vendor) | Data/platform teams feeding agents from 100s of systems | Agents need interleaved retrieval+reason+act infra; connector long-tail is open | Airbyte, Senso, Composio |
| P12 | Agents break rules under operational pressure — rule-breaking >2x under a deadline | PropensityBench via [IEEE Spectrum, 2026](https://spectrum.ieee.org/ai-agents-safety); [HN 46067995](https://news.ycombinator.com/item?id=46067995) — ~6,000 scenarios across 5 labs' models | Anyone deploying autonomous agents under SLAs | Misbehavior is emergent/pressure-dependent; static safety tests miss it; no runtime propensity guardrail | Guild, OpenUI, ClickHouse |

**Meta-insight #1 (highest leverage):** *Observability records but does not enforce.* P2, P3, P4, P12
all fail at the **same missing layer** — a real-time interception/approval gate between agent
**intent** and **action**. This is **literally Guild.ai's thesis** ("agent sprawl," control plane) — the
single biggest prize ($2,800).

**Meta-insight #2:** *Non-determinism breaks the test/eval/CI loop* (P6, P7, P8) — agents regress
silently and you can't gate them like normal software. (But this room is **crowded** — see kills.)

---

## PHASE 1 — 10 IDEAS (Ideator)

Forced diversity satisfied: **#6, #8, #10** are not devtools/observability; **#8** is the weird
"Most Innovative" swing; **#5** is the boring-but-bulletproof 2-track lock.

| # | Name / pitch | Solves | Tracks (architecture role) | 30-sec DEMO MOMENT | Hrs |
|---|---|---|---|---|---|
| 1 | **AEGIS** — real-time action firewall: a proxy between agent and its tools that intercepts every tool call, applies policy (block destructive ops in prod, budget caps, route to human approval) | P2,P3,P4,P12 | **Guild** (governance control plane / policy + audit), **ClickHouse+Langfuse** (every intercepted intent→trace→OLAP), **Composio** (the real tools the agent reaches for) | Agent tries `DROP TABLE users` → screen flashes red **BLOCKED**, an approval card pops up; approve/deny live | 14 |
| 2 | **COSTFUSE** — pre-call budget gate + kill-switch for runaway multi-agent loops | P4 | **TrueFoundry** (AI gateway meters every call, enforces cap), **ClickHouse+Langfuse** (cost events, live $ ticker) | Two agents ping-pong, a live **$ counter** climbs, hits the cap → big red **KILLED**; loop stops mid-call | 12 |
| 3 | **DRIFTWATCH** — CI that replays an eval suite on every prompt/model change to catch silent regression | P6,P8 | ClickHouse (eval runs), Langfuse (traces), Composio (GitHub PR) | A PR drops accuracy 93%→71% → CI turns red | 12 |
| 4 | **GLASSBOX** — time-travel debugger that replays an agent run step-by-step over its traces | P5 | ClickHouse+Langfuse (trace store + replay) | Scrub a timeline to the exact step that hallucinated | 10 |
| 5 | **MORPHEUS** — the agent builds its *own* dashboard: ask a question in English, it writes SQL over ClickHouse and **OpenUI generates a live chart component** on the spot | P5 | **OpenUI** (NL→rendered React chart), **ClickHouse** (the real analytical data the chart queries) | Type *"agent cost by tool, last hour"* → a real bar chart **materializes on stage** in ~5s | 12 |
| 6 | **GROUNDSKEEPER** — answers grounded in a Senso verified KB; a "citation guard" **refuses** any answer <X% sourced from verified truth | P1,P9 | **Senso** (verified KB + citation scoring), **Airbyte/PyAirbyte** (load many sources into the KB) | Ask a question with no source → agent **refuses & says why**; add the doc → it answers w/ citation | 12 |
| 7 | **FRESHCONTEXT** — freshness firewall: PyAirbyte continuously syncs sources, a monitor flags stale context *before* the agent uses it | P1 | **Airbyte/PyAirbyte** (sync), **ClickHouse** (freshness SLA store) | A price changes upstream → agent's stale answer is blocked, banner: "context 3h old" | 12 |
| 8 | **PRESSURE TEST** — an "agent gym" that puts your agent under PropensityBench-style deadline pressure and scores how often it reaches for forbidden tools | P12,P7 | **Guild** (governs/sandboxes the tools under test), **OpenUI** (live "temptation scoreboard" UI) | A pressure dial turns up; the agent **cracks** and grabs a forbidden tool — scoreboard spikes red | 14 |
| 9 | **AUTOMODEL CONCIERGE** — when an agent is bad at a task, it auto-fine-tunes a small specialist via Pioneer and routes to it | P6 | Pioneer (fine-tune SLM), TrueFoundry (route) | "I'm weak at PII → training a specialist…" then routes to it | 14 |
| 10 | **PROMPT-TO-PROD** — meta-agent: describe an app in English → OpenUI builds the frontend → git push → live on Render | P11 | OpenUI (frontend), Render (deploy to live URL) | "Build a feedback app" → a live HTTPS URL appears | 12 |

---

## PHASE 2 — FIRST KILL ROUND (Devil's Advocate) — quota: kill exactly 4

### KILL LOG (cause of death)
- **#3 DRIFTWATCH — KILLED.** *A2/A6:* "agent eval/regression in CI" is the single most crowded
  category at every 2026 agent hackathon; the tired judge has seen it three times before yours.
  *A3:* the demo moment is a CI status flipping red — a screenshot, not a moment. No track it
  locks that #1/#5 don't lock better.
- **#4 GLASSBOX — KILLED.** *A2:* agent "time-travel debugger" is a Langfuse/LangSmith feature
  demo, not a project; the sponsor's own engineer will say "Langfuse already does this." *A1:*
  ClickHouse is the only real integration and it's doing what Langfuse ships out of the box.
- **#9 AUTOMODEL CONCIERGE — KILLED.** *A4:* Pioneer fine-tune runs avg **~6 hours** (per the
  launch post) — a single end-to-end run **blows the 3:45 freeze**; you'd fake it. *A1:* Pioneer
  becomes a logo you `curl` once. *A5:* the access/credit model for Pioneer is unconfirmed today.
- **#10 PROMPT-TO-PROD — KILLED.** *A2/A6:* "AI builds an app and deploys it" is the most
  saturated demo of the Lovable/v0/Bolt era — every other team has a version. *A4:* a live
  `git push`→build→deploy on stage is **the single flakiest 30 seconds** you can script
  (cold start, build failure, DNS). *A3:* if the deploy hangs, you have nothing.

### Attack notes on the 6 SURVIVORS (strongest applicable attacks)
- **#1 AEGIS** — *A1:* if Guild's runtime already intercepts actions, "the interceptor" is just
  their tutorial; you must do something clever *on top*. *A4:* Guild docs 403 to bots → onboarding
  risk. *Survives:* P2/P3/P4 are the strongest incident evidence in the bank; demo moment is elite.
- **#2 COSTFUSE** — *A1:* does TrueFoundry actually **kill** a loop mid-call, or only *meter*
  cost? If it only meters, TrueFoundry is a logo and you build the kill logic. *A2:* overlaps
  AEGIS's "enforce not record." *Survives:* the $ ticker is a genuinely legible demo.
- **#5 MORPHEUS** — *A4:* LLM-written SQL + live-compiled React is two things that can break on a
  projector. *A1:* is OpenUI doing real work or just rendering a chart you could hardcode?
  *Survives:* locks the under-contested $2,000 OpenUI prize; "the agent built that UI live" is the
  rare clever moment.
- **#6 GROUNDSKEEPER** — *A2:* "RAG with citations" is common. *A5:* P1 evidence leans on a
  Gartner stat repackaged by vendor blogs. *Survives:* the **refusal** beat is unusual; Senso fit
  is exact.
- **#7 FRESHCONTEXT** — *A3:* "context is 3h old" is a number on a dashboard, not a moment. *A2:*
  overlaps GROUNDSKEEPER. *A5:* P1 is the weakest-cited problem. *Barely survives into bracket.*
- **#8 PRESSURE TEST** — *A4:* faithfully reproducing PropensityBench in hours is hard; the eval
  underneath may be hand-wavy. *A6:* judges may file it as a "benchmark toy," not "real infra."
  *Survives:* highest novelty in the field; Guild+OpenUI is a $4,800 surface.

---

## PHASE 3 — DOSSIERS (prior art + sponsor-fit; 6 survivors)

**Prior-art / sponsor-fit findings:**
- **AEGIS:** Closest prior art = "AI firewalls" (Lakera, Prompt Security) and MCP gateways, but
  those filter *prompts*, not *tool-call side-effects with human approval*. Not a hackathon
  cliché yet. **Sponsor fit:** Guild = control plane (self-serve, "agent in 10 min" claim, **docs
  403 to bots — verify live**). Cleanest build: intercept at the **MCP/Composio tool boundary**
  (a proxy we own), use Guild as the **policy + audit + dashboard** plane — this makes us *not*
  dependent on Guild's interception internals. Langfuse `@observe()` + ClickHouse = the record
  side, one `docker compose up`. **Clever bit:** replay the *real Replit `DROP`* and the *PocketOS
  9-second wipe* as canned attacks the firewall stops live.
- **COSTFUSE:** Prior art = Helicone/Portkey cost dashboards, but those *alert async* (the whole
  point of P4 is they don't intercept). **Sponsor fit:** TrueFoundry gateway = OpenAI-compatible,
  free dev tier; **must confirm it can hard-stop**, else build the kill loop ourselves and TF is
  a logo (A1). Overlaps AEGIS heavily.
- **MORPHEUS:** Prior art = Vanna.ai / text-to-SQL + chart, and "generative BI," but **agent
  generating its own UI component via OpenUI** is fresh and OpenUI is rarely used well. **Sponsor
  fit:** OpenUI hosted at `openui.fly.dev` (zero-setup) or local `python -m openui`; ClickHouse
  Cloud free 30-day/$300 or self-host. Both buildable in <1h. **Name-collision risk:** confirm
  sponsor is wandb/openui vs Thesys.
- **GROUNDSKEEPER:** Prior art = every RAG demo; **the refusal/abstention beat** is the
  differentiator. **Sponsor fit:** Senso self-serve, $100 free credits, `npm i -g @senso-ai/cli`,
  ingest→/search→cited answer in minutes. PyAirbyte free OSS for multi-source load.
- **FRESHCONTEXT:** Prior art = data-freshness monitors (Monte Carlo). Weak demo moment; weakest
  problem citation. Lowest seed.
- **PRESSURE TEST:** Prior art = PropensityBench (research, not a product) + agent "arenas." Novel
  as a *live* gym. **Sponsor fit:** Guild governs the tool sandbox; OpenUI renders the scoreboard.
  Build risk: the eval must feel real, not theatrical.

**Seeding by preliminary EV** (prize $ × P(win) × P(ship)): 1) AEGIS ~1140, 2) MORPHEUS ~1090,
3) PRESSURE TEST ~740, 4) COSTFUSE ~650, 5) FRESHCONTEXT ~550, 6) GROUNDSKEEPER ~290.

---

## PHASE 4 — DEBATE BRACKET (scores out of 110; EV×3, Ship×3, Demo×2, Novelty×2, Evidence×1)

### Match A — #1 AEGIS vs #6 GROUNDSKEEPER
- **Ideator FOR AEGIS (100w):** Every team will *talk about* agent safety; AEGIS *shows* it. We sit
  a proxy at the tool boundary and replay the two most-cited 2026 incidents — Replit's prod `DROP`
  and PocketOS's 9-second wipe — and stop them **live**, with a human-approval card. Guild is the
  governance plane (its exact thesis: agent sprawl), Langfuse→ClickHouse is the tamper-evident
  audit. It locks the **biggest prize** ($2,800) plus $1,950 of recording, and answers four cited
  problems (P2/P3/P4/P12) at once. The demo moment is a red **BLOCKED** banner — legible from the
  back row. This is "enforce, don't just record" made physical.
- **Ideator FOR GROUNDSKEEPER (100w):** Hallucination-with-confidence is the #1 reason enterprises
  won't ship agents. GROUNDSKEEPER makes the agent **refuse** rather than guess: every answer is
  scored against a Senso verified KB and abstains below threshold. PyAirbyte loads many messy
  sources so it's "real infra," not a toy. Senso fit is exact (it's literally "the context layer"),
  the refusal beat is memorable, and it's not yet another observability dashboard.
- **DA demolition (150w, attacking the STRONGEST part):** AEGIS's strength is the incident replay —
  so attack that. Replaying a canned `DROP TABLE` you wrote yourself is **theater**: the agent
  isn't *deciding* to delete prod, you scripted it to. A sponsor engineer asks "what stops me from
  hardcoding the block?" and your $2,800 evaporates. Worse, Guild may **already** intercept at its
  runtime — then AEGIS is Guild's quickstart with a red banner, and the most-innovative judge has
  seen "agent guardrail" twice tonight. Four tracks = four A1 surfaces. — GROUNDSKEEPER's strength
  is refusal: but "RAG that abstains below a confidence threshold" is a *prompt + one if-statement*;
  Senso's citation score does the work, so Senso is the project and you're the wrapper. P1's
  evidence is a Gartner stat laundered through vendor blogs. Neither the refusal nor the citation
  is visually thrilling — it's a chatbot saying "I don't know."
- **Ideator rebuttal + binding amendments:** AEGIS — **amend:** interception lives in a proxy *we*
  own at the MCP/Composio boundary (provably not hardcoded: the judge types a *novel* destructive
  command and it's still caught by policy, not by a string match); Guild is policy+audit only.
  **Scope cut:** drop Composio as a *claimed track* (still used internally) → 3 claimed tracks, 3
  A1 surfaces. GROUNDSKEEPER — concede; the refusal is thin without a second beat.
- **JUDGE-SIM scores:**

| Axis (weight) | AEGIS | GROUNDSKEEPER |
|---|---|---|
| EV ×3 | 8 → 24 | 5 → 15 |
| Ship ×3 | 6 → 18 | 7 → 21 |
| Demo ×2 | 9 → 18 | 6 → 12 |
| Novelty ×2 | 7 → 14 | 5 → 10 |
| Evidence ×1 | 9 | 7 |
| **Total** | **83** | **65** |

**AEGIS advances.** Deciding argument: the "type a *novel* destructive command" amendment kills the
"it's hardcoded theater" attack, and P2/P3/P4 are the bank's strongest evidence.

### Match B — #5 MORPHEUS vs #7 FRESHCONTEXT
- **Ideator FOR MORPHEUS (100w):** OpenUI is a $2,000 prize almost nobody will use well — most teams
  will bolt a logo on a static page. MORPHEUS makes OpenUI *load-bearing*: the agent generates a
  **real, novel chart component** in response to an English question, querying live ClickHouse data.
  Two clean locks ($3,600), a demo moment that **materializes on stage**, and a clever core ("the
  agent built that UI you're looking at, just now"). Fewest unverified assumptions of any survivor.
- **Ideator FOR FRESHCONTEXT (100w):** Stale context (P1) is the quiet killer of enterprise agents.
  PyAirbyte syncs many sources; a freshness firewall blocks the agent from answering on data past
  its SLA. It's "real infra" (data plane), not another chatbot, and it pairs Airbyte + ClickHouse.
- **DA demolition (150w):** MORPHEUS's strength is "the agent built the UI live" — so attack the
  live build. LLM-written SQL against ClickHouse + **live-compiled React** is *two* fragile steps on
  a projector: one malformed query or one JSX that won't transpile and you're staring at a stack
  trace during your 30 seconds. And "text-to-SQL-to-chart" is Vanna.ai's exact demo — the judge
  who's seen generative BI shrugs. Is OpenUI doing real work, or rendering a bar chart you could
  hardcode? — FRESHCONTEXT's strength is "real infra": but the demo moment is **a number on a
  dashboard** ("context 3h old"). There is no *moment*; it's a freshness gauge. P1 is the
  weakest-cited problem in the bank (Gartner-via-vendor). It overlaps GROUNDSKEEPER and locks
  nothing GROUNDSKEEPER doesn't.
- **Ideator rebuttal + binding amendments:** MORPHEUS — **amend:** constrain generation to a
  **pre-validated component set** (bar/line/table) with **parameterized** queries (no raw LLM SQL
  to the DB → no injection, no transpile-at-runtime: OpenUI emits props, not arbitrary JSX). The
  "live" risk drops to near-zero while the moment survives. The clever bit = the *question* is
  arbitrary, the *chart* is generated to fit it. FRESHCONTEXT — concede; no second beat, weakest
  evidence.
- **JUDGE-SIM scores:**

| Axis (weight) | MORPHEUS | FRESHCONTEXT |
|---|---|---|
| EV ×3 | 8 → 24 | 6 → 18 |
| Ship ×3 | 8 → 24 | 6 → 18 |
| Demo ×2 | 9 → 18 | 5 → 10 |
| Novelty ×2 | 7 → 14 | 5 → 10 |
| Evidence ×1 | 6 | 7 |
| **Total** | **86** | **63** |

**MORPHEUS advances.** Deciding argument: the parameterized-component amendment converts the
biggest ship risk into a non-issue while keeping the only demo moment that *appears on stage*.

### Match C — #8 PRESSURE TEST vs #2 COSTFUSE
- **Ideator FOR PRESSURE TEST (100w):** This wins **Most Innovative** on novelty alone — nobody else
  will demo an "agent gym" that turns up *deadline pressure* and measures the agent cracking and
  grabbing a forbidden tool. It's grounded in real research (PropensityBench, ~6,000 scenarios, 5
  labs). Guild governs the sandbox; OpenUI renders a live temptation scoreboard that spikes red on
  stage. $4,800 surface, unforgettable.
- **Ideator FOR COSTFUSE (100w):** The $47k runaway loop (P4) is a visceral, cited horror story.
  COSTFUSE puts a **hard budget gate** in the TrueFoundry gateway: a live $ ticker climbs as two
  agents loop, hits the cap, and the loop is **KILLED** mid-call. "Observability records; we
  enforce." Legible, evidence-backed, locks TrueFoundry + ClickHouse/Langfuse.
- **DA demolition (150w):** PRESSURE TEST's strength is novelty — so attack whether the *eval is
  real*. PropensityBench took a research team and ~6,000 scenarios; your hours-long reproduction is
  a handful of hand-written "deadline" prompts and a dial you turn. The judge asks "is the agent
  *actually* under pressure, or did you prompt it to misbehave?" — and it reads as theater dressed
  as science. "Real infra"? It's a benchmark toy. — COSTFUSE's strength is the cited horror story —
  but does TrueFoundry actually **kill a loop mid-call**, or only *meter* cost after the fact? If
  it meters, you built the kill switch and TrueFoundry is a **logo** (A1), and the idea is AEGIS's
  little sibling ("enforce not record") with one fewer track. The $ ticker is nice, but the room
  has seen cost dashboards.
- **Ideator rebuttal + binding amendments:** PRESSURE TEST — **amend:** ground the eval in a small
  *fixed, published* scenario subset and show the score *with* and *without* pressure side-by-side
  (the delta is the proof it's not just prompting). COSTFUSE — **amend:** implement the kill as a
  TrueFoundry-gateway **request hook** (confirmed-or-bust) so TF is load-bearing; if it only
  meters, the idea collapses into AEGIS.
- **JUDGE-SIM scores:**

| Axis (weight) | PRESSURE TEST | COSTFUSE |
|---|---|---|
| EV ×3 | 7 → 21 | 7 → 21 |
| Ship ×3 | 5 → 15 | 7 → 21 |
| Demo ×2 | 8 → 16 | 8 → 16 |
| Novelty ×2 | 9 → 18 | 5 → 10 |
| Evidence ×1 | 8 | 9 |
| **Total** | **78** | **77** |

**PRESSURE TEST advances by 1.** Deciding argument: in a room full of "enforce/cost" pitches,
novelty (×2) is the tiebreaker and COSTFUSE's TrueFoundry-as-logo risk is unresolved until verified.

### FINAL ROUND — winners (AEGIS 83, MORPHEUS 86, PRESSURE TEST 78) + wildcard
Best-scoring loser = **COSTFUSE (77)** > GROUNDSKEEPER 65 > FRESHCONTEXT 63 → **COSTFUSE is the
wildcard.** Re-score the four with **fresh DA attacks only** (recycled objections void the round).

| Idea | NEW DA attack (not used before) | Final score |
|---|---|---|
| **MORPHEUS** | If the sponsor's "OpenUI" is **Thesys**, not wandb/openui, your whole integration targets the wrong product and you discover it at submission. | **85** |
| **AEGIS** | You claim 3 tracks but the *governance* story needs Guild's dashboard live — and Guild's docs **403 to automated clients today**; if onboarding isn't self-serve at 9 AM you lose the $2,800 anchor and demo on a stub. | **82** |
| **PRESSURE TEST** | The "real infra" axis is unwinnable: a gym that runs *your own* agent against *your own* prompts has no production system in the loop — the most-innovative judge rewards agents that *do a real job*, not agents that take a quiz. | **70** |
| **COSTFUSE** | Even with a gateway hook, killing a loop is one `if cost > cap: raise` — a sponsor engineer sees a 20-line wrapper around their metering and the "$200 Composio-tier" of effort, not a $1,000 idea. | **66** |

**TOP 2 ADVANCE: MORPHEUS (85) and AEGIS (82).**

**Failure-independence check (required):** AEGIS's anchor = **Guild** (docs-403 onboarding risk).
MORPHEUS's anchors = **OpenUI + ClickHouse**, *no Guild*. Their *fatal* dependencies do **not**
overlap. Soft shared dependency: both touch **ClickHouse** — but ClickHouse is **self-hostable OSS**
(not gated), and each demo degrades gracefully (AEGIS audit → Langfuse-cloud/Postgres; MORPHEUS →
DuckDB/Postgres). **No HALT condition.** The finalists are failure-independent. ✅

---

## PHASE 5 — FINAL 2 BRIEFS

### FINALIST 1 — AEGIS (the agent action firewall)

**80-word pitch (what a judge hears):** "In 2026, a Replit agent ignored a code freeze and deleted a
production database; another wiped prod *and its backups* in 9 seconds. The lesson everyone learned:
observability **records** disasters, it doesn't **stop** them. AEGIS is a real-time firewall that
sits at the agent's tool boundary, inspects every action's *intent*, and **blocks** destructive or
out-of-budget calls — routing them to a human. Governed by Guild, audited in ClickHouse. Type
`DROP TABLE` and watch it die."

**Problem + evidence:** P2 [Replit, 2025-07-21](https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/) ·
P3 [PocketOS, 2026](https://neuraltrust.ai/blog/pocketos-railway-agent) ·
P4 [$47k loop, 2025-11](https://agentcost.in/docs/blog/ai-agent-cost-explosions-6-hours-governance/) ·
P12 [PropensityBench/IEEE, 2026](https://spectrum.ieee.org/ai-agents-safety).

**Prize matrix:**

| Track | Exact integration | Demo beat that proves it | $ |
|---|---|---|---|
| Guild.ai — Most Innovative | Policies + audit trail + agent registration live in Guild's control plane; AEGIS is the enforcement arm of its "agent sprawl" thesis | Open Guild dashboard → the blocked action appears as a governed, audited event with the policy that caught it | **$2,800** |
| ClickHouse (+Langfuse) | Langfuse `@observe()` instruments the agent; every intercepted *intent* (allowed + blocked) streams as a trace into ClickHouse | A live ClickHouse query: "show blocked actions in the last 5 min" returns the `DROP` attempt sub-second | **$1,600 + $350** |
| *(internal, not claimed)* Composio | The real tools the agent reaches for (GitHub/DB/Slack) — gives the firewall something genuine to intercept | — | — |

**Architecture sketch:**
```
 Agent (LLM) ──tool call──▶ [AEGIS proxy @ MCP/Composio boundary]
                                  │  policy check (deny destructive in prod / budget / approve)
                  ┌───────────────┼────────────────┐
            ALLOW │           BLOCK│            APPROVE│
                  ▼               ▼                    ▼
            real tool        red BLOCKED         human approval card (UI)
            (Composio)        banner
                  └─────────── every intent ──────────┘
                                  ▼
                  Langfuse @observe()  ──▶  ClickHouse (audit/OLAP)
                  Guild control plane  ──▶  policy source + audit dashboard
```
The interception lives in a **proxy we own** — so it catches *novel* destructive commands by
policy, not by string-match (defeats the "it's hardcoded" attack).

**Hour-by-hour to 3:45 PM (first 90 min specified exactly):**
- **0:00–0:15** — Verify Guild self-serve onboarding works (the gating risk). If 403 persists,
  pivot Guild to "policy config file + audit view" and keep building.
- **0:15–0:35** — `docker compose up` Langfuse (ships ClickHouse); confirm UI on :3000, ClickHouse reachable.
- **0:35–0:60** — Composio: `pip install composio`, `composio login`, wire one real tool (GitHub or a sandbox Postgres) to a minimal agent.
- **0:60–0:90** — Stand up the AEGIS proxy: intercept tool calls, one policy (`deny DROP/DELETE on prod`), log every intent to Langfuse. **First BLOCK working by 1:30.**
- **1:30–3:00** — Approval-card UI; budget-cap policy (ties in P4); register agent + policies in Guild; ClickHouse audit query.
- **3:00–3:45** — Script the demo: judge types a *novel* destructive command; rehearse the BLOCKED beat + Guild audit view. **Freeze.**

**DA's residual (unkilled) risk:** *Guild's docs 403 to bots — if self-serve onboarding isn't live
at the event, the $2,800 anchor degrades to a config-file stub.* **Mitigation:** the enforcement
proxy + Langfuse/ClickHouse audit stand alone and still demo perfectly; Guild becomes upside, not a
single point of failure. Confirm Guild access first thing (see tiebreaker).

---

### FINALIST 2 — MORPHEUS (the agent that builds its own dashboard)

**80-word pitch (what a judge hears):** "Multi-step agents are black boxes — you can't see *why* they
failed (P5). MORPHEUS lets you ask, in plain English, *anything* about your agents — 'show cost by
tool in the last hour' — and instead of returning text, the agent **writes the query against
ClickHouse and generates a live chart component with OpenUI, on the spot.** The dashboard you're
looking at didn't exist 5 seconds ago. The agent built it to answer your question. No dashboards to
pre-build — ever."

**Problem + evidence:** P5 [LangChain, 2025](https://www.langchain.com/resources/llm-observability-tools) ·
[HN 45129237, 2025](https://news.ycombinator.com/item?id=45129237). Data substrate also serves
P4/P6 cost & eval questions.

**Prize matrix:**

| Track | Exact integration | Demo beat that proves it | $ |
|---|---|---|---|
| OpenUI — Best Use | Agent emits a UI spec → OpenUI renders a real React chart component (from a pre-validated set: bar/line/table) bound to the query result | Type a question → a chart **materializes on the projector** in ~5s; ask a different one → a *different* chart appears | **$2,000** |
| ClickHouse — Best Use | Agent translates NL → **parameterized** SQL over a ClickHouse table of agent traces/cost; sub-second OLAP returns the data the chart binds to | "...last hour" returns instantly over millions of rows; show the generated SQL | **$1,600** |

**Architecture sketch:**
```
 User question (NL) ──▶ Agent (LLM)
                           │  NL → parameterized query plan (whitelisted columns/aggregations)
                           ▼
                     ClickHouse  (agent traces/cost events; OLAP, sub-second)
                           │  result rows
                           ▼
                     UI-spec {chartType, x, y, title}  ──▶  OpenUI  ──▶  live React component
                           ▼
                     rendered chart on screen (the thing the judge sees)
```
Generation is constrained to a **validated component set** with **parameterized** queries — no raw
LLM SQL to the DB, no runtime JSX transpile of arbitrary code → the "live build breaks on stage"
risk is engineered out while the *moment* (arbitrary question → fitted chart) survives.

**Hour-by-hour to 3:45 PM (first 90 min specified exactly):**
- **0:00–0:15** — **Confirm which OpenUI is the sponsor** (wandb/openui vs Thesys). Spin up
  `openui.fly.dev` (hosted) and `python -m openui` locally as backup.
- **0:15–0:40** — ClickHouse Cloud (free 30-day/$300, no card) **or** local; create an
  `agent_events` table; seed ~50k rows of realistic agent cost/trace data.
- **0:40–0:65** — Agent: NL → query plan over a **whitelisted** schema (columns + aggregations only); return rows. Verify "cost by tool last hour" works in the terminal.
- **0:65–0:90** — Wire query result → UI-spec → OpenUI → render one **bar chart** end-to-end. **First chart on screen by 1:30.**
- **1:30–2:45** — Add line/table component types; make the question free-text; polish render latency; second & third example questions.
- **2:45–3:45** — Two-minute demo script (three different questions → three different charts); fallback to a recorded chart render if Wi-Fi dies. **Freeze.**

**DA's residual (unkilled) risk:** *OpenUI name collision (wandb vs Thesys) — building against the
wrong product is discovered too late.* **Mitigation:** the first 15 minutes confirm the sponsor's
exact OpenUI; both share the "NL→rendered UI" model, so the agent→UI-spec layer ports between them
with minimal rework.

---

## TIEBREAKER — if I must choose in 10 seconds

**Default pick: MORPHEUS.** Higher final score (85 vs 82), higher ship probability, fewer unverified
assumptions, and it locks the **under-contested OpenUI $2,000** + ClickHouse $1,600 = $3,600 with a
demo moment that literally appears on the projector. Ties break toward fewer unverified
assumptions — and AEGIS carries the Guild-403 onboarding question that MORPHEUS does not.

**But pivot to AEGIS if one thing is true** — the single deciding question:

> **"Can we get a working Guild.ai agent running in ~10 minutes via self-serve (their docs currently
> 403 to bots) AND confirm Guild does *not* already intercept actions out of the box?"**

- **Yes →** build **AEGIS**: it anchors the **single biggest prize ($2,800)**, sits dead-center on
  Guild's own thesis, and is backed by the bank's strongest evidence (Replit, PocketOS, $47k).
- **No →** build **MORPHEUS**: bulletproof, two clean self-serve locks, no gated anchor.

*Confirm the Guild question by 9:15 AM. Everything downstream forks on that one answer.*
