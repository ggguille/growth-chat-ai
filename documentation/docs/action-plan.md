# Action Plan — AI-Powered Lead Qualification Chat

**Project:** Website Growth Chat
**Date:** May 2026
**Documentation status:** Pre-build complete — build start authorised

---

## Current state: what we have

All design and architecture documentation is complete. Pre-build gates are closed.

| Document | Status |
| --- | --- |
| Product Requirements Document (PRD) | ✅ Approved |
| Stakeholder Review | ✅ Approved |
| Engineering Review (13 ECs) | ✅ All resolved |
| Conversation Design Document (CDD) | ✅ Complete — 80 test cases defined |
| ADR-001 — LLM Provider (Claude Haiku 4.5) | ✅ Accepted |
| ADR-002 — Orchestrator (LangGraph) | ✅ Accepted |
| ADR-003 — RAG (pgvector + OpenAI Embeddings) | ✅ Accepted |
| ADR-004 — State persistence (PostgreSQL checkpointer) | ✅ Accepted |
| ADR-005 — Chat widget | ✅ Accepted |
| ADR-006 — Infra (Fly.io + Neon + Cloudflare) | ✅ Accepted |
| ADR-007 — LLM Observability (Langfuse) | ✅ Accepted |
| ADR-008 — Application logging (BetterStack) | ✅ Accepted |
| ADR-009 — CRM substitute (PostgreSQL leads table) | ✅ Accepted |
| Technical Requirements Document (TRD) | ✅ Complete (v0.2, 2026-05-15) |

### Pending gaps before build

Three deliverables that do not block the start but must be resolved in parallel:

| Gap | Blocks | Deadline |
| --- | --- | --- |
| Knowledge base placeholder (10-15 synthetic Markdown docs) | RAG pipeline testing from Phase 2 | Week 0 |
| RAG evaluation dataset (30-50 question/expected-answer pairs) | Quantitative RAG tuning in Phase 4 | Week 0, iterate in Phase 4 |
| Eval strategy document — conversational agent and red team | Production DoD | Before Phase 5 |

**Three evaluation layers not covered in the current documentation:**

| Layer | What it evaluates | Tool | When |
| --- | --- | --- | --- |
| RAG pipeline | Correct retrieval + response grounded in context, no hallucination | RAGAS + Langfuse | Phase 4 + ongoing production |
| Agent behaviour | Stages, prohibited behaviours, personas, pattern tests (60 test cases) | DeepEval + pytest | Phase 2 (partial) and Phase 5 (full) |
| Adversarial red team | Adaptive multi-turn attacks: prompt injection, extraction, jailbreak (20 test cases + auto-generation) | promptfoo redteam | Phase 5 |

> **Why the DeepEval / promptfoo split:** the 60 behaviour test cases (persona flows + pattern tests) require structured assertions over stateful multi-turn sequences — Python code, not YAML. The 20 adversarial test cases benefit from promptfoo generating them adaptively: it iterates over model responses using strategies like GOAT or Crescendo, uncovering failures that hand-written cases miss. The standard production pattern is to run both in CI: DeepEval as the metric gate, promptfoo as the red-team gate.

---

## Build phases

### Week 0 — Pre-build and parallel workstreams

**Goal:** Everything ready for engineering to start without friction on day 1.

**Engineering:**

- Create repository and project structure
- Configure environments: local (MemorySaver), staging (PostgreSQL checkpointer)
- Provision base infrastructure: Fly.io app (`fra`), Neon database, Cloudflare DNS
- Configure secrets and base environment variables
- Set up basic CI/CD (GitHub Actions or equivalent)
- Configure Langfuse (cloud, EU region) and BetterStack log shipper

**Parallel workstream — Knowledge Base (OQ-01):**

- Produce 10-15 synthetic Markdown documents covering the 5 KB categories:
  - 2-3 fictional but plausible case studies (fintech, SaaS, enterprise)
  - Service descriptions (AI engineering, RAG, MLOps, nearshore teams)
  - Team profiles (senior engineers, EU timezone, specialisms)
  - Engagement model (time & materials, embedded teams, end-to-end delivery)
  - FAQs (pricing deflection, timelines, how the engagement works)
- Format: Markdown, one document per category, ready to be ingested by the pipeline

**Parallel workstream — Eval Strategy (three layers):**

*Layer 1 — Agent behaviour (DeepEval + pytest):*

- Configure **DeepEval** + pytest for the 60 behaviour test cases from CDD §9 (50 persona flows + 10 pattern tests)
- DeepEval allows defining custom metrics for conversational constraints: "no more than one qualifying question per turn", "no pricing disclosure", "no fabrication when no chunk is retrieved"
- Define test case format for automated execution: multi-turn input conversation → assertions on expected behaviour and absence of failure conditions
- Configure DeepEval + Langfuse integration: eval scores are logged to Langfuse traces
- Suite runs in CI on every PR touching the system prompt or the KB

*Layer 2 — Adversarial red team (promptfoo):*

- Configure **promptfoo** for the 20 adversarial test cases from CDD §9.4 (extraction, prompt injection, persona boundary, disqualification bypass)
- promptfoo generates adaptive multi-turn attacks using GOAT/Crescendo strategies — it iterates over model responses and uncovers failures that hand-written cases miss
- Define `purpose` in `promptfooconfig.yaml` with the system-specific description (lead qualification chat for an AI engineering company) — this guides contextually relevant attack generation
- Plugins to enable: `harmful`, `pii`, `prompt-injection`, `hijacking`, plus custom plugins for pricing extraction and client name extraction
- Runs in CI as a red-team gate independent from the DeepEval gate

*Layer 3 — RAG pipeline (RAGAS):*

- Produce RAG evaluation dataset: **30-50 pairs (question → expected answer)** covering the 5 KB placeholder categories
  - Questions with a known relevant chunk (expected: score ≥ threshold, correct answer)
  - Questions with no relevant chunk (expected: no retrieval, LLM acknowledges the limit)
  - Paraphrased versions of well-covered questions (recall robustness test)
- Reference targets: context precision > 0.8, faithfulness > 0.8, answer relevancy > 0.75
- This dataset evolves in Phase 4 with the real KB

**Exit gate:** Repo with green CI, infrastructure provisioned, KB placeholder available, RAG dataset produced, DeepEval + pytest configured with test case structure, promptfoo configured with `promptfooconfig.yaml` and plugins defined.

---

### Phase 1 — Weeks 1-2: Scaffolding and frontend widget

**Goal:** End-to-end system working with hard-coded responses. Widget is embedded and can be demonstrated.

**Backend:**

- FastAPI project scaffolding
- Implement `POST /chat/message` endpoint (streaming SSE)
- Implement `POST /chat/session` for session creation
- Implement `GET /health` and `GET /ready`
- Basic LangGraph integration: empty graph returning a fixed response
- Connect `MemorySaver` for local development
- Configure `langgraph-checkpoint-postgres` for staging
- Run checkpointer schema migration on staging
- Basic rate limiting with `slowapi` (20 msg / 5 min)
- GDPR data notice on the first message of each session

**Frontend (chat widget):**

- Embeddable widget via `<script>` tag with `fallback-url` attribute
- Streaming SSE rendering (tokens appear progressively)
- Graceful degradation state: if backend is unresponsive, display link to `fallback-url`
- GDPR notice visible before the first message
- Statically functional widget with no build dependencies on the host

**Infra:**

- Deploy to staging on Fly.io (`fra`)
- Cloudflare rate limiting: 30 req / 10 min (challenge), 60 / 10 min (block)
- Cloudflare Bot Score configured
- BetterStack log shipper active on staging

**Exit gate:** Widget embedded on a test page, user can send a message and receive a response (even a fixed one). GDPR notice visible. Fallback works when the backend is down.

---

### Phase 2 — Weeks 3-4: Conversation agent and qualification state machine

**Goal:** The agent holds real conversations, qualifies visitors, and follows CDD rules.

**Conversation Orchestrator (LangGraph graph):**

- Implement full `SessionState`: `QualificationState`, `turn_counter`, `stall_turn_counter`, `is_business_hours`, `handoff_triggered`
- Graph nodes:
  - `classify_input` — detects persona and intent
  - `score_router` — deterministic evaluation of hot/warm/cold threshold (Problem + Authority + Company/Timing)
  - `generate_response` — LLM call with Claude Haiku 4.5, streaming
  - `stall_check` — stall detection (6 turns without `propose_handoff`)
  - `update_state` — updates `QualificationState` after each turn
- Business Hours Detection Module: `zoneinfo` + `Europe/Madrid`, DST-correct, `BUSINESS_HOURS_TIMEZONE` env variable

**System prompt:**

- Implement the 9 layers from CDD §8.3 in the specified order
- Layers 1-6: stable (role, conversation model, persona adaptation, prohibited behaviours, knowledge scope, handoff instructions)
- Layer 7: dynamic injection of `QualificationState` serialised as JSON
- Layer 8: placeholder for RAG chunks (real retrieval not yet active)
- Layer 9: conversation history sliding window (`CONTEXT_WINDOW_TURNS=10`)
- CDD §8.1 system prompt checklist: verify all criteria pass

**RAG (placeholder):**

- Implement `retrieve_knowledge` tool in `generate_response`
- Indexing pipeline: chunking, embedding (OpenAI EU endpoint), insert into pgvector
- Ingest the Week 0 KB placeholder
- `RAG_RELEVANCE_THRESHOLD=0.70` (provisional value for Phases 1-2)
- `RAG_TOP_K` configurable

**Eval — first cycle (DeepEval, behaviour):**

- Run subset of behaviour test cases with DeepEval + pytest
- Scope: P1 persona flows (TC-P1-001 to TC-P1-005) + basic pattern tests (TC-PAT-001 to TC-PAT-003)
- Custom metrics to verify per turn:
  - Single qualifying question per exchange
  - No pricing disclosure
  - No fabrication when no chunk is retrieved
- Goal: detect and fix prompt failures before proceeding; adversarial tests run in Phase 5 with promptfoo
- DeepEval results logged as scores in Langfuse — full traces available for inspection

**Exit gate:** A P1 conversation reaches Stage 3 (call proposal). `score_router` fires correctly. System prompt passes the CDD §8.1 checklist. First DeepEval cycle running and logging scores to Langfuse.

---

### Phase 3 — Weeks 5-6: Human handoff and CRM

**Goal:** When a hot lead is detected, the notification reaches Slack and the lead is persisted in the database.

**Handoff subsystem:**

- `propose_handoff` node in the LangGraph graph
- `ContextPacket` generation with all fields from CDD §5:
  - `lead_level`, `qualification_signals` (4 dimensions with confidence)
  - `conversation_summary`, `contact_email`, `is_business_hours`
  - `referral_mentioned`, `authority_level`, `company_signals`, `timing_signals`
- Outside-hours flow: system proposes the call, acknowledges the team is offline, commits to next morning before 10am CET

**Slack integration:**

- Webhook to `#new-leads`
- Message formatted with the `ContextPacket`
- Retry logic: on failure, log + alert; handoff not considered complete until delivery is confirmed

**PostgreSQL CRM (`PostgresCRMClient`):**

- `leads` table schema (ADR-009): `session_id`, `email`, `lead_level`, `context_packet` (JSONB), `created_at`, `slack_delivered`, `crm_delivered`
- `PostgresCRMClient.write(context_packet)` → insert into `leads`
- Partial failure handling: if Slack fails but DB succeeds (or vice versa), log the failure, retry the failed delivery, do not mark handoff as complete until both destinations confirm
- Email fallback to `sales@` if both channels fail

**Exit gate:** End-to-end test: hot lead detected → Slack message in `#new-leads` + row inserted in `leads` table. Outside-hours flow works correctly.

---

### Phase 4 — Weeks 7-8: Real knowledge base and RAG validation

**Prerequisite:** Real OQ-01 content delivered by marketing/PM (deadline: kickoff + 2 weeks; if the content audit is delayed, continue with the placeholder until it arrives).

**Knowledge base:**

- Ingest real content into pgvector (replaces the placeholder)
- Verify the indexing pipeline processes all formats correctly
- Proactive case study surfacing (S3 — Should): `proactive_case_study` flag on `RetrievalResult` when the top chunk is a case study with score ≥ `RAG_PROACTIVE_THRESHOLD`

**RAG tuning (EC-05) — quantitative evaluation with RAGAS:**

*Step 1 — Threshold calibration (TRD method):*

- Run the representative test query set against the real KB
- Plot the score distribution (relevant vs. irrelevant)
- Identify the natural gap and set `RAG_RELEVANCE_THRESHOLD` at that value
- Document the selected value and reasoning (update TRD)

*Step 2 — Quantitative validation with RAGAS + Langfuse:*

- Update the RAG evaluation dataset (Week 0) with the real KB: replace placeholder expected answers with answers based on real content
- Run RAGAS against Langfuse traces captured with the updated dataset
- Target metrics:
  - **Faithfulness > 0.8** — generated response is grounded in retrieved chunks, not in model memory
  - **Context precision > 0.8** — retrieved chunks are relevant to the question
  - **Context recall > 0.7** — system retrieves the information needed to answer correctly
  - **Answer relevancy > 0.75** — response is pertinent to the visitor's question
- RAGAS can operate in *reference-free* mode on production traces — no ground-truth labels required for faithfulness and answer relevancy
- If faithfulness < 0.8: review system prompt grounding instructions and threshold. If context precision < 0.8: review chunking strategy or `RAG_TOP_K`

*Step 3 — Functional validation:*

- Relevant questions → result above threshold ✓
- Irrelevant questions → no retrieval triggered ✓
- `[NO RELEVANT RESULTS]` signal works → LLM acknowledges the limit without fabricating ✓

*Chunking evaluation (optional if scores are low):*

- Langfuse allows evaluating the retrieval component independently from the LLM — iterate over `CHUNK_SIZE` and `CHUNK_OVERLAP` without running costly LLM calls
- Compare configurations using the Langfuse Experiment Runner with the evaluation dataset

**Exit gate:** RAG threshold documented. RAGAS scores: faithfulness > 0.8, context precision > 0.8, answer relevancy > 0.75. Proactive case study surfacing working (if S3 in scope).

---

### Phase 5 — Weeks 9-10: Testing and DoD sign-off

**Goal:** Pass all production gates before launch.

**Full evaluation suite — three layers:**

*Layer 1 — Agent behaviour with DeepEval (60 test cases):*

- Run the 60 behaviour test cases with DeepEval + pytest:
  - 50 persona flows (10 × 5 personas: P1, P2, P3, N1, N2)
  - 10 pattern tests (§9.3: business hours, out-of-scope, stall, AI disclosure, existing client...)
- Custom metrics per test case: expected behaviour present, failure condition absent
- Cross-cutting metrics: one-question-per-exchange compliance, pricing non-disclosure, no fabrication
- Scores logged to Langfuse via DeepEval+Langfuse integration
- Suite must pass at 100% — re-runnable in CI on every PR touching the system prompt or the KB

*Layer 2 — Adversarial red team with promptfoo (20 test cases + adaptive generation):*

- Run `promptfoo redteam run` against the staging endpoint
- The 20 CDD §9.4 test cases are used as a baseline, but promptfoo generates adaptive variations using GOAT/Crescendo — the attack model learns what works against this specific system
- Categories covered: pricing extraction, client name extraction, system prompt extraction, competitor intelligence, prompt injection, persona boundary violations, disqualification bypass
- Red team failures are documented and the system prompt or grounding constraints are corrected before launch
- Runs as a separate CI gate: a red team failure does not block the deploy automatically but requires explicit documented review before approval

*Layer 3 — RAG pipeline with RAGAS (post-Phase 4 regression):*

- Re-run RAGAS against the RAG evaluation dataset with the final KB
- Confirm Phase 4 scores are maintained: faithfulness > 0.8, context precision > 0.8, answer relevancy > 0.75
- Detect retrieval regressions introduced when the KB placeholder was replaced with real content

**Performance load test (EC-09):**

- Target: p95 TTFT < 3s
- Load level: 10 concurrent sessions sustained for 10 minutes (~40× expected production peak)
- Measurement: from API request sent to first token received at the client
- Streaming enabled — full-response latency is not the target metric
- If the test fails: first action is `min_machines_running=1` on Fly.io (no code changes required)

**End-to-end tests:**

- Full handoff: hot lead → Slack + `leads` table (both confirmed)
- Graceful degradation: AI backend down → fallback form accessible from `fallback-url`
- Analytics events: all defined events firing with the correct schema
- GDPR notice: visible on first message, approved text

**Exit gate:** 60/60 DeepEval test cases passing. promptfoo red team with no unreviewed critical failures. RAGAS scores maintained (faithfulness > 0.8, context precision > 0.8). p95 TTFT < 3s verified. End-to-end handoff confirmed. Graceful degradation works.

---

### Phase 6 — Launch readiness

**Pre-production checklist:**

- [ ] Rate limiting active: Cloudflare Rules (30/60 req / 10 min) + `slowapi` (20 msg / 5 min)
- [ ] Token budget: `MAX_TOKENS_PER_SESSION` configured (default: 16,000 tokens)
- [ ] Cost alerting: `MONTHLY_COST_CAP_USD` with alert at 80% of threshold ($50 default)
- [ ] Context window: `CONTEXT_WINDOW_TURNS=10` active, `QualificationState` never evicted
- [ ] Real KB ingested and threshold tuned (EC-05)
- [ ] DeepEval: 60/60 behaviour test cases passing (EC-11)
- [ ] promptfoo: red team with no unreviewed critical failures documented
- [ ] RAGAS scores verified: faithfulness > 0.8, context precision > 0.8 (EC-05 complement)
- [ ] p95 TTFT < 3s verified under load (EC-09)
- [ ] Monitoring active: Langfuse traces, BetterStack logs, alerts configured
- [ ] Daily backup to Tigris working (Fly.io scheduled machine)
- [ ] `fallback-url` configured with the real existing contact form URL (OQ-06)
- [ ] GDPR notice: approved text visible on first message
- [ ] Analytics baseline: 30-day form submission export for post-launch comparison (OQ-03)

**Open questions to resolve before deploy:**

- OQ-06: What is the `fallback-url` value in production? (PM / web ops)

---

## Dependency overview

```text
Week 0
├── [parallel] KB placeholder (10-15 docs)              ──┐
├── [parallel] RAG eval dataset (30-50 Q/A pairs)       ──┤
├── [parallel] DeepEval + pytest setup (60 test cases)  ──┤
├── [parallel] promptfoo config + plugins                ──┤
└── Infra + repo + CI                                    ──┤
                                                           │
Phase 1 (W1-2): Widget + API scaffold                  ←───┘
│
Phase 2 (W3-4): Agent + qualification SM               ← KB placeholder required
│   └── [DeepEval: partial cycle — P1 flows + basic pattern tests]
│
Phase 3 (W5-6): Human handoff + CRM
│
Phase 4 (W7-8): Real KB + RAG tuning                   ← OQ-01 (real content) required
│   ├── Threshold calibration (TRD method)
│   └── [RAGAS + Langfuse: faithfulness, precision, recall, relevancy]
│
Phase 5 (W9-10): Testing + DoD sign-off
│   ├── [DeepEval: 60 behaviour test cases — metric gate]
│   ├── [promptfoo redteam: 20 adversarial + adaptive generation — red-team gate]
│   ├── [RAGAS: post-real-KB regression]
│   ├── Load test TTFT p95 < 3s
│   └── End-to-end tests
│
Phase 6: Launch readiness
```

---

## Documents still to be created

In addition to code, the following documents must be produced during the build:

| Document | When | Owner |
| --- | --- | --- |
| Knowledge base placeholder (Markdown, 10-15 docs) | Week 0 | AI Engineer + PM |
| RAG evaluation dataset (30-50 Q/A pairs) | Week 0 → update in Phase 4 | AI Engineer |
| DeepEval test suite (60 behaviour test cases in pytest format) | Week 0 → complete in Phase 5 | AI Engineer |
| promptfoo config (plugins, purpose, GOAT/Crescendo strategies) | Week 0 → run in Phase 5 | AI Engineer |
| System prompt (real artefact, not the CDD design) | Phase 2 | AI Engineer |
| RAG threshold — documented decision + RAGAS scores | Phase 4 | AI Engineer → updates TRD |

---

## Post-launch success metrics

The PRD defines the primary success metric: **chat becomes a top-3 lead source with a higher qualification rate than form submissions**.

Metrics tracked from day 1:

- Conversations started / day
- Stage 3 proposals issued / total conversations (hot lead conversion rate)
- Emails captured / Stage 3 proposals issued
- Leads qualified by chat vs. by form (rate comparison vs. OQ-03 baseline)
- Conversation depth (average turns to Stage 3 or drop-off)
- p95 TTFT in production (ongoing)
- Hallucination flags in Langfuse (prompt compliance violations)
- RAGAS faithfulness in production (periodic batch scoring over Langfuse traces — detects regressions when the KB or prompt changes)

---

*This document is the operational execution plan. The authoritative technical specification is the TRD (v0.2, 2026-05-15). Any architectural deviation requires a corresponding ADR. Last updated: 2026-05-15 — evaluation stack revised: DeepEval (behaviour, 60 test cases) + promptfoo (adversarial red team, 20 test cases + adaptive generation) + RAGAS+Langfuse (RAG pipeline).*
