# Candidate Ideas — Round 1 (2026-06-12)

Constraint: one engineer, ~5.5h of coding, 3-minute demo, each idea must stack ≥5 sponsors in load-bearing roles. Status column updated by Orchestrator after each debate round.

| # | Idea | Sponsors stacked | Status |
|---|------|------------------|--------|
| 1 | BreachRadar | ClickHouse, Airbyte, Guild, Senso, OpenUI, TrueFoundry, Render (+Composio) | **CUT in Round 2** (feasibility 4, demo 4; 3 bolted-on sponsors) |
| 2 | DealPulse | Airbyte, ClickHouse, Pioneer, Guild, Senso, OpenUI, Composio, Render | **KILLED in Round 2** (feasibility 3; moat hostage to async fine-tune) |
| 3 | ContractCopilot | Composio, Airbyte, ClickHouse, Senso, Guild, OpenUI, TrueFoundry, Render | **SURVIVES → Round 3 revision** (runner-up; see debate-log for required fixes) |
| 4 | IncidentSherpa | Guild, ClickHouse, Airbyte, Senso, Composio, OpenUI, Pioneer, Render | **SURVIVES → Round 3 revision** (front-runner; unanimous #1) |

---

## Idea 1: BreachRadar

**One-line pitch:** A self-healing security posture agent that continuously ingests your cloud audit logs, detects anomalies in real-time, auto-drafts remediation runbooks, and renders them as interactive approval UIs — all without a human writing a single SQL query or dashboard config.

**The novel insight:** Security teams drown in alerts but starve for context. The moat is the loop: ClickHouse ingests raw events at sub-second latency, an agent fleet (Guild) decides which anomaly patterns warrant escalation, Senso holds institutional runbook knowledge so the agent doesn't hallucinate fixes, and OpenUI renders a one-click approval card so a tired on-call engineer can act in 10 seconds flat. The system gets smarter per-org because Senso's context layer accumulates resolved-incident knowledge as a feedback corpus.

**Real user & problem:** On-call DevSecOps engineer at a 50–500 person SaaS company. SIEM tools cost $50k+/yr and produce alert fatigue without actionable next steps. This replaces a Tier-1 SOC analyst for routine anomaly triage.

**Sponsor → role mapping:**

| Sponsor | Exact role | Why load-bearing |
|---|---|---|
| ClickHouse | Ingests streaming cloud audit events; sub-second anomaly SQL (Z-score on event frequency per IAM principal) | No real-time detection without it — Postgres can't window-aggregate 100k events/min |
| Airbyte Agent Engine | Pulls CloudTrail logs from S3/mock source into ClickHouse on 30s micro-batch | Without it, ingestion is a hardcoded script, not a composable pipeline |
| Guild.ai | Orchestrates Detector / Enricher / Drafter agents with observability traces | Without it, a monolithic chain with no governance or retry logic |
| Senso.ai | Resolved-incident knowledge base; Enricher queries "last time this IP hit prod, we did X" | Without it, runbooks are generic LLM hallucination |
| OpenUI | Generative remediation card: affected resource, risk score, one-click "Apply Fix", diff preview | Without it, output is a wall of terminal text; demo moment dies |
| TrueFoundry | Routes LLM calls across models for the Drafter; cost cap per incident type | No cost control when 500 anomalies fire at once |
| Render | Hosts backend + background worker polling ClickHouse every 30s | No live deployment |

**Demo arc:** Quiet dashboard → simulated brute-force IAM login → ClickHouse detects spike in 2s → Guild agent trio → Senso retrieves identical past incident → OpenUI renders "Block Principal + notify Slack" card → Approve click → Composio executes Slack notification. Under 20 seconds wall-clock.

**5.5h sketch:** (1h) Airbyte→ClickHouse ingestion + Z-score view; (1.5h) Guild agent trio + Senso seeding; (1.5h) OpenUI approval card + Composio Slack; (1h) Render deploy + smoke test; (30m) buffer.

**Biggest risk:** Airbyte Agent Engine connector setup with thin docs. Fallback: Airbyte REST trigger + Python writer to ClickHouse, keeping Airbyte's OAuth-managed source config load-bearing.

---

## Idea 2: DealPulse

**One-line pitch:** A revenue-intelligence agent that syncs your CRM, email, and call transcripts in real time, detects deals going cold using behavioral signals in ClickHouse, and surfaces a generative "deal rescue" briefing card with talking points — rendered as a live OpenUI component.

**The novel insight:** Every "AI CRM" is a chatbot on Salesforce. The moat is the signal layer: ClickHouse runs sliding-window queries over deal-touch frequency, email response latency, and call sentiment deltas. Guild governs per-deal agents each with their own Senso context slice. Pioneer fine-tunes a small classifier on your org's own won/lost deals to score churn risk — defensible IP.

**Real user & problem:** AE or VP of Sales at a B2B SaaS company. Deals slip not from lack of data but from signal-to-noise: no AE computes "no stakeholder email in 11 days AND sentiment dropped 2 points on the last call."

**Sponsor → role mapping:**

| Sponsor | Exact role | Why load-bearing |
|---|---|---|
| Airbyte Agent Engine | Syncs HubSpot/Salesforce deals, Gmail threads, Gong transcripts into ClickHouse | Without it, bespoke OAuth nightmare; the connector library IS the data layer |
| ClickHouse | Real-time sliding-window aggregations: days-since-touch, email-latency p50, sentiment trend per deal | Can't compute these at query time otherwise |
| Pioneer (Fastino) | Fine-tunes small won/churn classifier on historical deal data | Without it, risk score is an uncalibrated LLM guess |
| Guild.ai | Persistent agent per active deal, woken by ClickHouse alert triggers; fleet observability | No per-deal persistence or governance otherwise |
| Senso.ai | Per-deal context slice: account history, threads, competitor mentions, champion details | Brief becomes generic without org memory |
| OpenUI | Deal rescue card: risk gauge, top-3 talking points, one-click "Draft follow-up email" | Wall-of-text Slack message otherwise; the button is the demo hook |
| Composio | Executes the Gmail draft pre-populated with talking points via managed OAuth | Agent can suggest but not act otherwise |
| Render | Webhook receiver + agent runner + Next.js frontend | No live deployment |

**Demo arc:** Airbyte syncs a HubSpot sandbox with one deal at 12-day silence → ClickHouse fires cold-deal alert → Guild wakes deal agent → Senso supplies history → Pioneer scores 78% churn risk → OpenUI renders rescue card → click "Draft Email" → real Gmail draft appears in 4 seconds.

**5.5h sketch:** (1h) Airbyte connectors + ClickHouse signal views; (1h) Pioneer fine-tune kickoff + REST endpoint; (1.5h) Guild per-deal agent + Senso seeding; (1h) OpenUI card + Composio Gmail; (1h) Render deploy + rehearsal.

**Biggest risk:** Pioneer fine-tune turnaround unknown. Mitigation: kick off the job at T+0; use TrueFoundry-routed frontier model as drop-in until ready; swap at the end.

---

## Idea 3: ContractCopilot

**One-line pitch:** An agent that sits in your legal inbox, parses incoming vendor contracts, redlines risky clauses against your company's policy knowledge base, negotiates asynchronously via email, and renders every clause change as a tracked generative UI diff — collapsing a 3-day legal review cycle to 15 minutes.

**The novel insight:** Existing contract AI (Ironclad, Spellbook) requires manual upload and produces static reports. The moat is the closed-loop negotiation: Composio watches the Gmail inbox, ClickHouse runs clause-level analytics across all historical contracts ("we've accepted this clause 12 times before"), Senso holds the legal playbook so the agent knows your actual negotiating positions. OpenUI renders inline redlines a non-lawyer can approve in one click.

**Real user & problem:** Head of Legal/Ops at a 20–200 person startup. Every vendor contract takes 3+ days because legal is a bottleneck; standard playbook clauses (liability caps, IP ownership, auto-renewal) are reviewed identically every time — pure repetitive institutional-knowledge application.

**Sponsor → role mapping:**

| Sponsor | Exact role | Why load-bearing |
|---|---|---|
| Composio | Watches Gmail for contract attachments; sends negotiation response emails | No automated inbox watch or outbound action — loop breaks |
| Airbyte Agent Engine | Loads parsed clause text into ClickHouse alongside historical corpus | No historical clause analytics otherwise |
| ClickHouse | Clause embeddings + metadata; similarity search for precedent clauses | Precedent matching needs full LLM call per clause otherwise |
| Senso.ai | Legal playbook: acceptable liability caps, IP stances, jurisdictions, escalation rules | Generic legal advice instead of company policy — the compliance moat |
| Guild.ai | Parser / Redliner / Negotiator agents; state across async email round-trips; audit log per clause decision | Multi-round negotiation state lost otherwise; no audit trail |
| OpenUI | Redline diff UI: original vs proposed clause, risk badge, Accept/Reject/Escalate per clause | Markdown wall requiring legal expertise otherwise |
| TrueFoundry | Long-context analysis → frontier model, short clause checks → cheap model; per-contract cost budget | A 100-page MSA burns $8 in LLM calls without routing |
| Render | Webhook server + agent runner + frontend | No live deployment |

**Demo arc:** Vendor NDA PDF arrives in live Gmail → Composio triggers pipeline → clauses into ClickHouse, 3 precedent matches found → Senso supplies playbook → Guild trio redlines 2 risky clauses → OpenUI side-by-side diff → Accept one, Escalate one → Composio sends counter-proposal email. Under 90 seconds live.

**5.5h sketch:** (1h) Composio Gmail watch + PDF extraction + ClickHouse similarity view; (1.5h) Senso playbook seeding + Guild 3-agent pipeline; (1h) OpenUI diff component + TrueFoundry routing; (1h) Render deploy + E2E with real NDA; (1h) buffer.

**Biggest risk:** Composio Gmail OAuth rate-limit/scope issues in a sandbox. Mitigation: pre-authorize at T+0; fall back from webhooks to 60s polling — Composio still load-bearing for credentials.

---

## Idea 4: IncidentSherpa

**One-line pitch:** An incident commander agent that listens to your on-call Slack channel, correlates alerts across your observability stack in real time via ClickHouse, assigns remediation to the right engineers from ownership history in Senso, and generates a live incident-timeline UI that auto-publishes a postmortem draft the moment the incident resolves.

**The novel insight:** Incident tools (PagerDuty, FireHydrant) are passive — they wait for humans to update them. The moat is active coordination: Guild maintains a persistent incident-scoped agent tracking every Slack message, alert spike, and remediation action as structured state. ClickHouse computes causal chains ("CPU spike on A preceded latency on B by 4 minutes"). The postmortem writes itself from the agent's own event log — the only accurate source of truth, because humans under pressure don't document.

**Real user & problem:** SRE/EM at a microservices company. During a P0 the incident commander triages, coordinates, AND must write the postmortem from memory afterward. It's always late, incomplete, and the causal chain is lost.

**Sponsor → role mapping:**

| Sponsor | Exact role | Why load-bearing |
|---|---|---|
| Guild.ai | Persistent incident-scoped agent: event tracking, state machine (Investigating/Mitigating/Resolved), structured event log | Postmortem has no source of truth otherwise |
| ClickHouse | Real-time metric/log ingestion; cross-service causal correlation (lag/lead window functions) | The "4-minute causal chain" is the core value prop |
| Airbyte Agent Engine | Pulls PagerDuty + GitHub issues + Jira history into ClickHouse for baseline + ownership | No historical baseline otherwise |
| Senso.ai | Service ownership maps, runbooks, past postmortems | Task assignment random; runbook lookup generic otherwise |
| Composio | Posts structured Slack updates, creates Jira follow-up tickets, updates PagerDuty | Output stays inside the tool otherwise |
| OpenUI | Live incident timeline: scrolling event log, dependency-graph highlight, assign buttons, postmortem preview | Raw Slack thread otherwise; timeline is the demo anchor |
| Pioneer (Fastino) | Small classifier predicting severity + blast radius at alert time | Severity is a manual human call otherwise |
| Render | Slack webhook receiver + agent runner + frontend | No live deployment |

**Demo arc:** Simulated PagerDuty alert (payments latency) → ClickHouse correlates to DB pool exhaustion 3 min earlier → Guild incident agent fires → Senso retrieves runbook + owner → Pioneer classifies P1 → OpenUI live timeline with causal chain → Composio posts Slack update + Jira ticket → resolve → postmortem draft appears. 2 minutes wall-clock.

**5.5h sketch:** (1h) Airbyte history pull + ClickHouse causal SQL; (1.5h) Guild incident agent + Senso seeding + Composio Slack/Jira; (1h) Pioneer severity classifier + OpenUI timeline; (1h) Render deploy + fire drill; (1h) buffer.

**Biggest risk:** Real-time metric streaming is fiddly in 5.5h. Mitigation: ClickHouse HTTP bulk-insert replaying a pre-recorded metric CSV at 10× speed — window-function queries still run live, role stays load-bearing.

---

# Round 3 Revisions (Rev 2) — survivors only

Both Rev 2 specs below incorporate every required revision from debate-log.md Round 2. Statuses: IncidentSherpa = front-runner, ContractCopilot = runner-up.

## Idea: IncidentSherpa (Rev 2.1)

> **Rev 2.1 (Round 4 fix, DA-required):** GLiGuard is a safety-moderation model (safety/jailbreak/harm/refusal detection) and CANNOT classify incident severity — the Rev 2 claim was a factual error. Pioneer's role is corrected to **GLiNER2 schema-conditioned inference**: a custom schema (`severity: P0|P1|P2|P3`, `affected_services: span extraction`) extracted synchronously at alert ingestion (<100ms, ~30 min integration incl. schema design — GLiNER2 is designed for arbitrary-schema extraction). GLiGuard is retained in its actual role: safety guardrail screening all outbound agent text (Slack posts, Jira descriptions, postmortem) before send — a second legitimate Pioneer touchpoint. All "GLiGuard severity" references below should be read as "GLiNER2 severity extraction + GLiGuard output guardrail."

**One-line pitch:** An active incident-commander agent that opens mid-P0, streams a complete postmortem the moment you click Resolve, and suggests the likely owner for every remediation action — because it was the stenographer in the room, not a journalist reconstructing from Slack.

**The novel insight:** Every incident tool (PagerDuty, FireHydrant, Incident.io) reconstructs the past from unstructured Slack history — a journalist working from tweets. IncidentSherpa is the stenographer: a Guild-managed persistent agent that writes every alert, metric anomaly, and human action into a typed event log as they happen. ClickHouse runs lag/lead window functions over a replayed metric CSV to surface causal chains ("DB pool exhaustion preceded payments latency by 4 minutes") that no human remembers under pressure. The postmortem is not drafted afterward — it is emitted directly from the agent's own structured log at the moment of resolution. GLiGuard classifies severity synchronously at alert ingestion, 16–20x faster than prior SOTA, before any LLM call is made.

**Real user & problem:** SRE or EM at a 30–500 person microservices company. During a P0 the incident commander triages alerts, coordinates engineers, and is still expected to publish a postmortem from memory 48 hours later. The postmortem is always late, always incomplete, and the causal chain is always lost because documentation competes with firefighting. Incident.io's AI feature tries to solve this but reads unstructured Slack — it sees what people said, not what actually happened.

**Sponsor → role mapping:**

| Sponsor | Exact role | Why load-bearing |
|---|---|---|
| Guild.ai | Persistent session-scoped incident agent: typed event log, state machine (Investigating/Mitigating/Resolved), audit trail per action, credential-scoped access to Slack and Jira | The postmortem has no structured source of truth without a persistent stateful agent; Guild's session + audit-log primitives make "stenographer not journalist" literally true. Single-agent descope path documented — Guild remains load-bearing in either branch. |
| ClickHouse | Replay-CSV metric stream via bulk HTTP insert (DEFAULT path); lag/lead window-function SQL computes cross-service causal correlations; Langfuse traces stored on ClickHouse Cloud | Without ClickHouse the "4-minute causal chain" is an LLM guess. "Reason over data not just retrieve" is the exact judging hint. |
| Langfuse (ClickHouse bonus) | Instruments every LLM call — severity classification, runbook retrieval, postmortem draft, owner suggestion — with trace IDs, latency, token cost, eval scores in Langfuse Cloud | Claims the $350 bonus; visible trace waterfall proves the agent did what it claims. First-class component, not a one-liner. |
| Airbyte Agent Engine | GitHub + Jira connectors (both confirmed supported; Jira OAuth 2.0 confirmed 2026-06-03) pull historical incident tickets + PR merge events into ClickHouse for ownership baseline. PagerDuty attempted on-site as stretch only. | Ownership suggestion is random without historical GitHub/Jira signal; Context Store pre-indexes for <500ms lookups. |
| Senso.ai | Service ownership maps, runbook corpus, past postmortem summaries; agent queries "last time payments latency spiked, runbook step 3 resolved it in 8 min" | Without Senso, owner suggestions and runbook steps are generic hallucination; responses are cited and grounded. |
| Composio | Posts structured Slack status updates with causal summary; creates Jira follow-up ticket with owner suggestion; managed OAuth | Without Composio the agent is read-only. Slack + Jira = two apps orchestrated, the literal Composio criterion. |
| OpenUI | Live incident timeline: scrolling typed event log, dependency-graph causal highlight, "Suggested owner — confirm?" button, postmortem panel streaming token-by-token on Resolve | The timeline is the demo anchor; the streaming postmortem is the killer moment. |
| Pioneer (GLiNER2 + GLiGuard) | (1) GLiNER2 schema-conditioned inference at alert ingestion: custom schema `severity: [P0,P1,P2,P3]` + `affected_services` span extraction — NER + classification are two of GLiNER2's four native tasks, schema supplied at inference time (`GLiNER2.from_api()`, gliner.pioneer.ai, Pioneer API key). No fine-tune, no async job; measure actual REST latency at T+0:15 and cite the REAL number. (2) GLiGuard screens all outbound agent text (Slack, Jira, postmortem) before send — its actual purpose (safety/jailbreak/harm/refusal, 16–20x faster than prior SOTA, Fastino 2026-05-14) | Small encoder for hot-path structured extraction, frontier LLM only for reasoning — an architectural choice a CTO recognizes as intentional. Dual legitimate Pioneer touchpoints. ~30 min REST-only; no 402 risk (inference, not training). |
| Render | Webhook web service + agent background worker + Next.js frontend in one `render.yaml` Blueprint; deployed at T+0:25 | Multi-service Blueprint demonstrates Render-native architecture. |

**Prize categories targeted:** Guild ($2,800), ClickHouse ($1,600) + Langfuse ($350), Airbyte ($1,750), Pioneer ($500 + $1,500 credits), Composio ($200), Render ($1,000). **NOT contesting:** OpenUI prize (load-bearing in demo but not the primary novel integration).

**Demo arc (INVERTED):** The judge opens a screen already 8 minutes into a live P0 with the timeline scrolling — clicks "Incident Resolved" — a complete postmortem with causal chain, owner names, and action items streams to the screen within 20 seconds — then "let me show you how we got here" rewinds to the first alert.

**Revised 5.5h build plan (auth/setup minutes counted):**
- **T+0:00–0:25 — Auth + checkpoints (25 min):** T+0:00 Guild login + `npm view @guildai/agents-sdk` go/no-go (descope path below if 404); T+0:05 Airbyte cloud auth, confirm GitHub+Jira connectors (>20 min → switch to MCP path, confirmed 06-05); T+0:10 Composio `link()` Slack + Jira OAuth; T+0:15 Pioneer key + GLiNER2 test call with the severity schema — RECORD the measured latency for the demo badge (402 → run Apache-2.0 model locally via transformers); GLiGuard guardrail test on a sample outbound message; T+0:20 Langfuse keys + test span; T+0:25 Render skeleton deploy ("hello world" before any domain code).
- **T+0:25–1:25 — ClickHouse ingestion + causal SQL (60 min):** metrics + events tables; replay script bulk-inserting pre-recorded incident_metrics.csv at 10× (DEFAULT path); LAG/LEAD causal SQL; Langfuse spans on queries; smoke test names DB-pool exhaustion as precursor.
- **T+1:25–2:40 — Guild agent + Senso + GLiGuard (75 min):** seed Senso (3 runbooks, 2 postmortems, ownership map); Guild incident agent state machine writing typed events to ClickHouse + Guild audit log; GLiGuard severity at ingestion; Senso runbook/owner retrieval; Langfuse `@observe` on all LLM calls.
- **T+2:40–3:30 — Composio actions + postmortem draft (50 min):** SLACK_SEND_MESSAGE with causal summary; JIRA_CREATE_ISSUE with "Suggested owner — awaiting confirmation"; postmortem generated from the typed event log + causal SQL + Senso precedents; E2E test.
- **T+3:30–4:10 — OpenUI timeline (40 min):** `npx @openuidev/cli@latest create`; streaming event log, causal-chain highlight, owner-confirm buttons, postmortem panel; SSE from Render webhook service.
- **T+4:10–4:50 — Render final deploy + Airbyte pull (40 min):** 3-service render.yaml green; GitHub+Jira 90-day history into ClickHouse; ownership query wired; PagerDuty stretch only if ahead.
- **T+4:50–5:30 — Rehearsal + hardening (40 min):** full arc ×3; Langfuse waterfall verified; static-HTML fallback card for OpenUI; timeline rewind prepared.

**Guild T+0 descope path (written):** If the SDK is unavailable, a single Python IncidentAgent class manages state; Guild session created via REST (`POST /v1/sessions`), Slack/Jira credentials scoped through Guild Credentials API, every state transition appended to the Guild session audit log. Multi-agent architecture collapses into methods on one class — Guild's session management, credential governance, and audit trail remain the mechanism. Judging hints reward governance, not SDK import depth.

**Biggest remaining risk:** Guild session REST API shape unverified. Max 15 min on Guild auth before escalating to the sponsor rep; if unresolvable, drop the Guild prize claim, keep all other sponsors, manage state with LangGraph — build plan otherwise unaffected.

---

## Idea: ContractCopilot (Rev 2)

**One-line pitch:** An agent that reads your legal inbox, redlines risky NDA clauses against your company's policy playbook, and queues a pre-written counter-proposal for one-click send — collapsing a 3-day legal review to 15 minutes without a lawyer touching a keyboard.

**The novel insight:** Ironclad and Spellbook are static report generators — you upload a PDF, you get a list, you still write the email. ContractCopilot closes the loop in both directions: Composio reads the incoming contract from Gmail and sends the counter-proposal back through Gmail. The ClickHouse story is honestly analytical: Python compares clause embeddings at ingest; ClickHouse stores match flags, clause metadata, and acceptance history so "we have accepted this exact indemnification cap 12 times before" runs as real columnar SQL — no vector-index claim. TrueFoundry routes a 100-page MSA to a frontier model and a 3-clause NDA to a cheap one — the cost difference visible in Langfuse traces.

**Real user & problem:** Head of Legal or VP Ops at a 20–200 person startup. Every vendor NDA takes 3+ days; the same 6 clause types (liability cap, IP ownership, auto-renewal, indemnification, governing law, confidentiality term) are reviewed identically against a playbook living in someone's head. The agent replaces the repetitive-application-of-known-policy step — the lawyer still approves before anything sends.

**Sponsor → role mapping:**

| Sponsor | Exact role | Why load-bearing |
|---|---|---|
| Composio | GMAIL_FETCH_EMAILS attachment watch + GMAIL_SEND_EMAIL counter-proposal; `session.link()` managed OAuth | Without it the loop is broken: the agent can redline but cannot receive or send. The closed loop is the differentiation from Spellbook. |
| ClickHouse | Ingest-time: Python computes clause embeddings (sentence-transformers, local), writes match flags + clause_type + precedent_count + risk_score to `clauses` table. Live query: acceptance counts by clause type/vendor/date | The "accepted 12x before" query is real ClickHouse SQL judges can read and verify — honest columnar analytics, not a vector-index claim. |
| Langfuse (ClickHouse bonus) | Traces clause extraction, risk classification, redline drafts, counter-proposal synthesis; token cost per contract visible | $350 bonus + makes the TrueFoundry routing story legible via cost columns. |
| Senso.ai | Legal playbook: liability cap ranges, IP stances, jurisdiction rules, auto-renewal max, escalation triggers, past counter-proposal language; queried per clause type before drafting | Without Senso, redlines are generic LLM opinion, not company policy. Strongest Senso integration of the batch — cited answers are exactly what legal review requires. |
| TrueFoundry | Routes >20-page contracts → Claude Fable 5 via gateway (available 2026-06-09), ≤5-clause docs → cheap model; per-contract budget; PII guardrail on inputs | A 100-page MSA burns $8+ unrouted; 15 min to add with visible ROI. |
| OpenUI | Redline diff: original left / proposed right, risk badge, live precedent count, Accept/Reject/Escalate per clause, counter-proposal preview + one-click "Queue for Send"; streams token-by-token | The side-by-side diff is the clearest before/after in the batch; the button is the demo hook. |
| Render | Webhook receiver + agent worker + frontend, single render.yaml, deployed T+0:25 | Early deploy surfaces integration issues before T+3h. |

**Airbyte: DROPPED.** The static-corpus role was thin (DA Round 2); pandas + direct ClickHouse insert does it in 10 min without 30–45 min of setup risk. The $1,750 Airbyte prize is ceded to IncidentSherpa, which owns a genuine multi-connector use.

**Prize categories targeted:** ClickHouse ($1,600) + Langfuse ($350), Senso ($2,000 credits), TrueFoundry ($1,000), Composio ($200), Render ($1,000). **NOT contesting:** Guild (used for per-contract session audit but descoped, not the primary claim), Airbyte (dropped), Pioneer (not used), OpenUI (load-bearing but not primary claim).

**Demo arc:** A vendor NDA PDF lands in live Gmail → Composio triggers → clause analysis with live "accepted 12x before" ClickHouse query → Senso supplies the liability-cap policy → OpenUI streams a side-by-side redline diff with two flagged clauses → Accept one, queue counter-proposal for the other → Composio sends the email → Langfuse shows the full trace waterfall.

**Revised 5.5h build plan (auth/setup minutes counted):**
- **T+0:00–0:30 — Auth + checkpoints (30 min):** Composio Gmail `link()` OAuth (>15 min → 60s polling fallback, Composio still load-bearing); ClickHouse Cloud + `clauses` schema; Langfuse keys + test span; TrueFoundry PAT + test routed call; Render skeleton deploy at T+0:25; Guild go/no-go (REST session API descope same as IncidentSherpa — sessions per contract review, credential scoping, audit events on Accept/Reject/Escalate).
- **T+0:30–1:00 — PDF extraction (30 min):** **pdfplumber** (named library: pure-Python, reliable text-layer extraction); pre-staged EDGAR NDA (public domain, confirmed text layer, 8 standard clauses); clause-boundary parsing via section-header regex; local sentence-transformers embeddings (all-MiniLM-L6-v2); match flags → ClickHouse.
- **T+1:00–1:30 — Corpus ingest + Render confirm (30 min):** 50 synthetic historical clauses with accepted flags + vendor names inserted; "accepted 12x" query verified nonzero; Render all-green.
- **T+1:30–2:30 — Senso + agent pipeline (60 min):** 6 policy docs seeded (one per clause type, structured "policy / acceptable range / escalation trigger"); single-round negotiation agent: per risky clause (risk_score > 0.6) query Senso → TrueFoundry-routed LLM redline → `redlines` table; Langfuse on every call; Guild session audit per decision. Single-round scope: drafts all counter-proposals in one pass, human sends — no async round-trips (cut per DA).
- **T+2:30–3:15 — OpenUI diff component (45 min):** scaffold; streaming per-clause diff cards with live precedent counts; counter-proposal email preview; "Queue for Send" → Composio.
- **T+3:15–4:00 — Composio wiring + routing + E2E (45 min):** Gmail webhook → parser → pipeline; GMAIL_SEND_EMAIL prefilled; TrueFoundry routing rule (len(clauses) threshold); full E2E with trace waterfall confirmed.
- **T+4:00–4:30 — Final deploy + smoke (30 min):** Render auto-deploy green; cold-start health-check ping configured; Langfuse dashboard verified.
- **T+4:30–5:30 — Rehearsal + hardening (60 min):** demo arc ×3 with EDGAR NDA; Gmail-trigger-to-first-diff-card <15s; fallback CLI trigger (`python trigger.py --pdf edgar_nda.pdf`) if webhook fails on stage — counter-proposal send still fires live via Composio.

**Biggest remaining risk:** pdfplumber clause-boundary detection on non-standard formats — eliminated for the demo by pre-staging the EDGAR NDA. If asked about scanned PDFs: "word-level bounding-box extraction is the production path; for the hackathon we control the demo variable."


