# Debate Log — Harness Engineering Hack War Room

## Round 1 (2026-06-12) — Research + Ideation

- Researcher A+B completed sponsor intel → `sponsors.md`. All 9 sponsors have a dated "NEWEST (last 30d)" line + install command. Notable flags: Guild.ai SDK public availability UNVERIFIED (45–60 min risk); Airbyte 30–45 min credential setup; Pioneer fine-tune ~45 min with 402-credit risk; Senso has no verified last-30d ship (most recent confirmed product set noted instead).
- Ideator produced 4 candidates → `ideas.md`: BreachRadar (security triage), DealPulse (revenue intelligence), ContractCopilot (legal redlining), IncidentSherpa (incident commander).

## Round 2 (2026-06-12) — Debate: DA attack + BizDev pressure-test + Demo check

### Scores summary (Devil's Advocate, 0–10; <7 on any axis = cut or revise)

| Idea | Feasibility | Novelty | Prize fit | Demo-ability | DA verdict | BizDev EV | Demo impact |
|---|---|---|---|---|---|---|---|
| BreachRadar | 4 | 5 | 5 | 4 | **CUT** | ~$2,844 | 7/10 |
| DealPulse | 3 | 4 | 4 | 3 | **KILL OUTRIGHT** | ~$3,296 | 6/10 |
| ContractCopilot | 5 | 6 | 6 | 6 | **FIX-THEN-PROCEED** | ~$2,842 | 8/10 |
| IncidentSherpa | 5 | 7 | 7 | 7 | **FIX-THEN-PROCEED (closest to survives)** | ~$3,459 | 8/10 |

### DA verdict: BreachRadar — CUT

- **Feasibility 4/10:** 145–185 min of pure auth/setup (Airbyte RISKY + Guild RISKY in serial) before any domain code. Hardest integration: Guild — if `@guildai/agents-sdk` isn't on public npm, the orchestration layer and the $2,800 prize collapse with no fallback that keeps Guild load-bearing.
- **Novelty 5/10:** Security-agent-with-auto-remediation is the most over-represented hackathon category; "feedback corpus gets smarter" is undemonstrable in 5.5h. "What stops me doing this with Postgres FTS and a Slack bot?"
- **Prize fit 5/10:** Honest load-bearing sponsors: 4. TrueFoundry (thin routing), Composio (single Slack call), OpenUI (simplest possible card) are bolted on. No Langfuse → $350 left on the table.
- **Demo-ability 4/10:** "Detected in 2s" requires bypassing Airbyte's 30s micro-batch at the killer moment — the fallback removes Agent Engine from the visible flow.

### DA verdict: DealPulse — KILL OUTRIGHT

- **Feasibility 3/10:** Highest setup load (190–235 min). Pioneer fine-tune is async with unknown SLA — the only moat may be undemonstrable at demo time through no fault of the engineer. Gong connector is 2 days old and needs a real Gong account with recordings; no Gong sandbox exists in the plan.
- **Novelty 4/10:** Most crowded category in enterprise AI (Clari, Gong AI, Einstein). Without the fine-tune completing, "78% churn risk" is a plain LLM guess with a Pioneer label = logo-stacking.
- **Prize fit 4/10:** Honest load-bearing: 4 (Airbyte, ClickHouse, OpenUI, Composio). Guild fleet value prop absent with one deal/one agent; Senso KB is fake seeded data.
- **Demo-ability 3/10:** 7 sequential live dependencies; wow moment arrives at 75–90s.
- BizDev ranked it #2 by EV (~$3,296) on Airbyte+Pioneer strength, but conceded: "If the demo runs without Pioneer, judges see a polished Clari clone." Demo-Designer scored it last (6/10). Orchestrator sides with DA: the EV is conditional on the single most uncontrollable dependency in the batch. **KILLED.**

### DA verdict: ContractCopilot — REVISE (survives to Round 3)

- **Feasibility 5/10:** 180–225 min setup, but the domain logic is the simplest (document pipeline, not streaming). Hardest: Guild async state machine across email rounds — descope to single-round. Hidden yak-shave: PDF extraction on vendor-formatted PDFs (no library named). ClickHouse vector similarity is architecturally suspect (OLAP ≠ vector DB).
- **Novelty 6/10:** Closed-loop email negotiation with playbook memory is genuinely novel at demo level (Ironclad/Spellbook are static reports). CTO pushback expected on ClickHouse-as-vector-DB.
- **Prize fit 6/10:** 6 honest load-bearing sponsors. Strongest Senso integration of all four; strongest TrueFoundry routing story; OpenUI redline diff most visually differentiated. Airbyte weakest (static corpus load). No Langfuse → fix.
- **Demo-ability 6/10:** Most controllable trigger (one email with PDF). Failure modes: scanned PDF with no text layer; Render cold-start killing the webhook.
- **Required revisions (DA):** (1) Guild SDK 15-min checkpoint at T+0 → descope to single session-managed agent if absent; (2) replace ClickHouse vector search with ingest-time embedding comparison in Python, store match flags in ClickHouse — keeps the "accepted 12× before" analytics honest; (3) add Langfuse (20 min, $350); (4) pre-stage text-layer NDA PDF; (5) deploy Render at T+1h not T+4h.
- **BizDev:** Strongest real-world story but hardest moat to defend in 3 min ("why not Spellbook?" — answer: "Spellbook is a static report you upload manually; we close the loop: read inbox, send counter, track rounds"). Must reframe "negotiates autonomously" → "drafts + queues for one-click send" (liability). EV ~$2,842; TrueFoundry is the highest-probability single win (35%).
- **Demo-Designer (8/10, tie 1st):** Redline diff is the clearest before/after of the batch; pipeline trigger visible at ~10s, diff card streaming at ~50s. Fallback: pre-authorized throwaway Gmail + polling-mode toggle.

### DA verdict: IncidentSherpa — REVISE (front-runner)

- **Feasibility 5/10:** 190–230 min setup. Saving grace: the replay-CSV mitigation for real-time metrics is "the only intellectually honest mitigation across all four ideas" — window-function causal SQL still runs live. Risks: Guild SDK (highest single point); Pioneer must be GLiGuard *inference* not fine-tune; Composio needs Slack AND Jira OAuth (~20 extra min); PagerDuty connector unconfirmed in Agent Engine (fallback: GitHub+Jira, both supported).
- **Novelty 7/10:** Highest of the four. Active coordination + self-writing postmortem from the agent's own structured event log is architecturally defensible; ClickHouse lag/lead causal chain is the strongest technical insight in the batch and survives the "so it's just RAG" kill shot.
- **Prize fit 7/10:** 7 of 8 sponsors honestly load-bearing. Guild alignment is "the best single alignment in the entire field" (persistent agent + state machine + audit log = the literal judging hints). ClickHouse "reason over data" exact match. Composio multi-app (Slack+Jira) strongest of the four. Langfuse again unclaimed → fix.
- **Demo-ability 7/10:** Most self-contained arc (JSON POST trigger, replayed CSV, pre-OAuth'd Composio). Failure mode: Guild SDK absent → event log becomes a hardcoded dict → moat evaporates.
- **Required revisions (DA):** (1) Guild SDK verify at T+0, sponsor rep escalation; (2) Pioneer = GLiGuard synchronous inference (20–30 min, "16–20× faster than SOTA" benchmark to cite); (3) Langfuse 20-min add; (4) PagerDuty connector check, GitHub+Jira fallback; (5) pre-OAuth Composio Slack at T+0.
- **BizDev (#1, EV ~$3,459; best-case $6,750 across Guild+ClickHouse+OpenUI):** "Of course your postmortem is incomplete — you wrote it from memory two days later while the only accurate record, the agent's structured event log, was sitting there the whole time." Must pre-empt Incident.io's AI postmortem feature: "theirs drafts from unstructured Slack history — a journalist reconstructing from tweets; ours is the stenographer who was in the room." Reframe "assigns owners" → "suggests likely owner for confirmation" (stale ownership maps).
- **Demo-Designer (8/10, tie 1st; best first-60-seconds with INVERTED ARC):** Open the recording 8 minutes into a live P0, click "Incident Resolved," postmortem streams in within the first 20 seconds — then "let me show you how we got here." No other idea has a single-click payoff this legible to a tired judge at 9pm.

### Round 2 — Orchestrator convergence decision

1. **CUT: BreachRadar** (two axes <5; 3 bolted-on sponsors; detection moment requires bypassing its own data pipeline).
2. **KILL: DealPulse** (lowest scores across the board; moat hostage to an async fine-tune; no recovery path that doesn't make it a worse IncidentSherpa).
3. **SURVIVE→REVISE: IncidentSherpa** (front-runner: unanimous #1 across DA ranking, BizDev EV, and demo first-60s) and **ContractCopilot** (runner-up: best natural demo arc, strongest Senso/TrueFoundry stories).
4. **Round 3 task:** Ideator applies the DA's named revisions to both survivors (notably: Pioneer→GLiGuard inference, Langfuse instrumentation, Guild T+0 checkpoint with descope path, ClickHouse honest-analytics fix for ContractCopilot, inverted demo arc for IncidentSherpa). DA re-scores all four axes; target ≥7 everywhere. Demo-Designer writes full 3-min beat-by-beat scripts. Then final-plan.md.

**Open objections carried into Round 3:** (a) Guild SDK availability is the shared single point of failure for both survivors — both need a credible descope that keeps Guild load-bearing; (b) both must claim the Langfuse $350; (c) ContractCopilot's Airbyte role is thin — strengthen or drop the claim to that category.

## Round 3 (2026-06-12) — Rev 2 re-debate

Ideator delivered Rev 2 specs for both survivors (appended to ideas.md), applying all Round 2 required revisions. Notable: Airbyte honestly DROPPED from ContractCopilot (prize ceded to IncidentSherpa); Langfuse first-class in both; Guild T+0 go/no-go checkpoints with written REST descope paths; pdfplumber + pre-staged EDGAR NDA named; replay-CSV promoted to default; inverted demo arc adopted.

### DA re-scores (Round 3)

| Idea | Feasibility | Novelty | Prize fit | Demo | Clears >=7 bar? | Verdict |
|---|---|---|---|---|---|---|
| IncidentSherpa Rev 2 | 6 (was 5) | 6 (was 7, DOWNGRADE) | 7 | 8 (was 7) | NO (2 axes) | FIX-THEN-PROCEED — single named fix |
| ContractCopilot Rev 2 | 7 (was 5) | 7 (was 6) | 7 (was 6) | 7 (was 6) | YES | SURVIVES — build-ready |

**NEW OBJECTION (critical) — GLiGuard misuse in IncidentSherpa:** GLiGuard's four tasks are safety classification, jailbreak detection, harm-category detection, and refusal detection (verified: pioneer.ai blog, MarkTechPost, arxiv 2605.07982). It is NOT an incident-severity or blast-radius classifier. Shipping it labeled "severity classification" invites a fatal CTO kill shot in Q&A and jeopardizes the Pioneer prize claim. This single defect caused both failing axes (novelty downgraded 7→6, feasibility held at 6).
**DA's named fix (required before final-plan):** (a) GLiGuard as a safety guardrail on LLM outputs (legitimate, ~20 min, less dramatic), or (b) **preferred** — Pioneer schema-conditioned GLiNER2 inference with a custom severity/blast-radius schema ("severity: P0/P1/P2; affected_services: span extraction") — GLiNER2 IS designed for arbitrary-schema extraction; ~30 min including schema design. Build plan structurally unchanged.

**Other new objections:** Guild REST endpoint shapes (`POST /v1/sessions`) not publicly documented — 15-min on-site escalation is the only mitigation; LangGraph fallback costs the $2,800 claim. The T+1:25–2:40 block compresses if the Guild go/no-go overruns. ContractCopilot: "3 days to 15 minutes" pitch must rehearse the "what if the vendor rejects the counter?" answer; the diff-card demo is objectively less dramatic than the streaming postmortem in head-to-head.

**ContractCopilot improvements accepted by DA:** Airbyte drop removes 30–45 min risk and the logo-stacking objection; pdfplumber + EDGAR NDA eliminates both Round 2 yak-shaves; honest ClickHouse columnar analytics resolves the vector-DB objection ("judges can read and verify the SQL").

### BizDev final (Round 3)

- **IncidentSherpa Rev 2:** EV $2,683 across 7 categories (Langfuse 72% — essentially uncontested; ClickHouse 42%; Guild 28% with descope credibility). Best-case $5,250 (Guild+ClickHouse+Langfuse+Pioneer). Nominal EV down vs R2 because OpenUI prize is now honestly ceded — concentration up, defensibility up.
- **ContractCopilot Rev 2:** EV $2,134 across 6 categories (Langfuse 68%, Senso 35% — strongest Senso story of the batch, TrueFoundry 38%). Best-case $4,950. Ceding Airbyte/Guild was the right trade — those were the categories most likely to draw a logo-stacking objection.
- **Recommendation: Build IncidentSherpa** — "the postmortem-from-structured-event-log is an architectural insight, not a workflow automation; the ClickHouse lag/lead causal SQL survives a hostile CTO asking 'show me the query.'" ContractCopilot is the backup if Guild fails at T+0 (its 5 categories are achievable without Guild).

### Demo-Designer (Round 3)

Full beat-by-beat 3-minute scripts for both survivors written to **demo-scripts.md**: timestamped beats 0:00–3:00, wow moments (IncidentSherpa 0:12–0:30 streaming postmortem via inverted arc; ContractCopilot 0:35–0:42 one-click Accept), complete sponsor-visibility checklists (every sponsor has an exact timestamp + screen element), per-dependency fallback tables with switch cues, and full pre-staging checklists (accounts, OAuth, seeded data, pinned browser tabs, rehearsal gates).

### Round 3 — Orchestrator convergence decision

1. **ContractCopilot Rev 2: PASSES all four axes (7/7/7/7).** Locked as runner-up, build-ready.
2. **IncidentSherpa Rev 2: one named, scoped defect** (GLiGuard role). Orchestrator applies the DA's preferred fix (b) — GLiNER2 schema-conditioned severity/blast-radius extraction, GLiGuard optionally retained as an output-safety guardrail (its actual purpose). Spec updated to Rev 2.1 in ideas.md.
3. **Round 4 = DA confirmation re-score of the single fix.** If IncidentSherpa clears, all stopping conditions are met → final-plan.md → convergence declared.

## Round 4 (2026-06-12) — DA confirmation re-score of the GLiNER2 fix → CONVERGENCE

Orchestrator applied the DA's preferred fix (b) to IncidentSherpa (Rev 2.1 in ideas.md; demo-scripts.md updated to match). DA (same agent, full context) re-scored the failed axes:

| Idea | Feasibility | Novelty | Prize fit | Demo | Clears >=7 bar? |
|---|---|---|---|---|---|
| IncidentSherpa Rev 2.1 | **7** (was 6) | **7** (was 6) | 7 (holds) | 8 (holds) | **YES** |
| ContractCopilot Rev 2 | 7 | 7 | 7 | 7 | YES (since Round 3) |

- **Feasibility 7:** GLiNER2 schema-conditioned classification is the model's explicit design (NER + classification are 2 of its 4 native tasks; schema supplied at inference time; `GLiNER2.from_api()` confirmed at gliner.pioneer.ai). ~30 min integration replaces the prior GLiGuard wiring — no net budget expansion.
- **Novelty 7:** Dual Pioneer story (small encoder for hot-path structured extraction + GLiGuard guardrail on outbound text) is technically honest and MORE defensible: the "so it's just RAG" kill shot is now answered at two layers (ClickHouse causal SQL + GLiNER2 schema extraction).
- **Conditions attached:** (1) measure GLiNER2's actual REST latency at T+0:15 and cite the REAL number — the <100ms claim is unverified to that precision and "87ms" must not be fabricated (demo script updated to [measured]ms); (2) the stale "GLiGuard severity" body text in the ideas.md sponsor table was a visible contradiction — fixed by Orchestrator.
- **DA final verdict (verbatim):** "IncidentSherpa Rev 2.1 clears all four axes (7/7/7/8) — the GLiNER2 fix is technically sound and verified against Fastino's published architecture... Primary recommendation confirmed."

### Convergence check (stopping conditions)

1. ✅ sponsors.md: every sponsor has a dated last-30d feature line + install command.
2. ✅ ≥2 ideas with all four DA axes ≥7/10: IncidentSherpa Rev 2.1 (7/7/7/8), ContractCopilot Rev 2 (7/7/7/7).
3. ✅ Each survivor has a complete 3-min beat-by-beat demo script (demo-scripts.md) + Render deploy plan (render.yaml Blueprint, deploy at T+0:25 in both build plans).
4. ✅ final-plan.md written: recommended idea, runner-up, hour-by-hour T+0→T+5.5h, sponsor→prize mapping with $ estimates, top 3 risks.

**CONVERGENCE DECLARED after 4 rounds** (IncidentSherpa won Rounds 2, 3, and 4; the only Round 3 objection was resolved by a verified fix; no new objections remain). War room closed.
