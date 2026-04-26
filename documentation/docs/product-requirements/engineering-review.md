---
description: "Engineering team review of the PRD for the AI-powered lead qualification chat — formal assessment of completeness, architectural gaps, and recommended build sequence before development starts."
---

# Engineering Review — AI-Powered Lead Qualification Chat

**Document type:** Engineering review
**PRD reviewed:** [Product Requirements Document v1.0](./index.md)
**Review date:** April 2026
**Status:** Pending sign-off

---

## Functional Requirements Analysis

**FR-01 — Qualification state object:** What to track is clear (four dimensions + confidence). The state representation schema (enum? numeric score? boolean flags?) and persistence backend are not specified. Both must be defined in the TRD before the agent is built — they affect orchestration design, the escalation trigger logic, and context packet generation — see EC-02.

**FR-02 — Three-stage model:** The respond → advance → propose sequence is well-specified. Prompt engineering for reliable stage adherence (staying in Stage 2 until all three maturity signals are present) is a non-trivial instruction-following challenge. Plan for iteration.

**FR-04 — One qualifying question per exchange:** Requires either output parsing as a post-generation validation step or a prompt structure that reliably prevents multi-question responses. Do not assume the LLM will comply without enforcement.

**FR-05 — Stage 3 maturity detection:** The qualification-signals.md principle that escalation must be programmatic applies here too. Stage 3 gating should not be left to LLM judgement — the orchestrator should track each maturity signal as a boolean and trigger Stage 3 independently.

**FR-07 — Stall detection:** "6+ exchanges without qualification progress" is ambiguous. Precise definition needed — see EC-06.

**FR-09 — Programmatic escalation trigger:** Correctly required as programmatic. The mechanism is not described — see EC-03.

**FR-13 — Context packet:** Schema is fully defined in human-handoff.md. Engineering note: context packet generation must be a deterministic function of the session state object, not an LLM generation step. This ensures consistency, testability, and auditability.

**FR-15 — RAG retrieval decision:** "The system decides per turn whether to retrieve" — the decision mechanism is not specified — see EC-01.

**FR-17 — Relevance threshold:** Specified as a requirement but no value given. Must be a configurable environment variable, not hardcoded — see EC-05.

**FR-19 — Dual destination delivery:** Clear. Undefined behaviour: if one of the two destinations (Slack, CRM) fails and the other succeeds, is the handoff considered complete? A partial failure needs a defined behaviour — log it, alert, retry the failed destination.

**FR-22 — Outside-hours commitment:** Clear. The business hours detection implementation has edge cases that must be addressed before building — see EC-04.

---

## Non-Functional Requirements Analysis

**Performance — < 3s p95:** Achievable with streaming, but the target definition is ambiguous — see EC-09. The DoD load test criterion is untestable until this is resolved.

**Availability — Graceful degradation:** The fallback contact form must submit through a path independent of the AI backend. If the form submits to the same process that serves the AI, it is not a fallback — see EC-07.

**Security — GDPR / LLM provider:** A Data Processing Agreement with the chosen LLM provider is a hard legal requirement before any real visitor data is sent to the API — see EC-08.

**Observability — Analytics event schema:** Defined at category level only (e.g. "contact captured"). The full event schema with field names and types must be specified in the TRD before implementation. Without it, the backend and frontend will log inconsistent shapes that break any downstream analytics.

---

## Technical Stack Analysis

**ADR sequencing:** ADR-001 (LLM provider) must be the first ADR completed. It constrains ADR-002 (orchestration) and ADR-006 (cloud). Do not start those ADRs until ADR-001 is resolved.

**Orchestration:** LangGraph is the strongest candidate given the explicit state machine requirement. It supports the qualification state object, conditional branching (hot/warm/cold paths), and observable graph execution. LangChain LCEL is less suited to complex branching. A custom state machine is viable but trades framework maintenance for engineering time.

**Vector store:** Chroma is sufficient for MVP development but not for production at any meaningful scale. Pinecone or pgvector (if PostgreSQL is already in the stack) should be the production target. Avoid building against Chroma if a migration to pgvector can be planned from the start.

**Missing from stack candidates — rate limiting and cost controls:** No mention of LLM API token budgets, per-session rate limits, or cost alerting. Required before production — see EC-12.

**Missing from stack candidates — context window management:** No mention of conversation turn limits or truncation strategy. Required before building the orchestration layer — see EC-13.

---

## Definition of Done Analysis

**20 test conversations for hallucination check:** Insufficient for a production system — see EC-11. The DoD must be updated before it can serve as a quality gate.

**Performance criterion:** "Response latency p95 < 3 seconds verified under simulated load" — load level is undefined, and the TTFT vs. full-response ambiguity (EC-09) makes this criterion untestable as written. Both must be resolved before Phase 5 testing begins.

**Conversation end definition:** The "conversation depth" metric depends on reliably detecting session end. Browser `beforeunload` events are unreliable. Define what constitutes conversation end (explicit close, inactivity timeout, or session expiry) before the analytics schema is built.

---

## Engineering Concerns

Thirteen architectural gaps and missing requirements not addressed in the PRD or supporting documents. Each must be resolved in the TRD or corresponding ADR before the relevant build phase begins.

| # | Title | Blocker level |
| --- | --- | --- |
| EC-01 | RAG triage mechanism not specified | Blocks backend build start |
| EC-02 | Qualification state object persistence backend not specified | Blocks architecture finalisation |
| EC-03 | Programmatic escalation trigger mechanism not specified | Blocks orchestration design |
| EC-04 | Business hours detection edge cases (DST, public holidays) | Must define before building that module |
| EC-05 | Relevance threshold undefined — must be configurable | Blocks RAG tuning |
| EC-06 | "Qualification progress" not precisely defined for stall detection | Low complexity; must define before building stall logic |
| EC-07 | Graceful degradation form submission destination not specified | Blocks frontend widget build |
| EC-08 | GDPR DPA with LLM provider required | Hard blocker for production launch |
| EC-09 | Performance target ambiguity: TTFT vs. full response | Must clarify before performance testing |
| EC-10 | Content audit (OQ-01) must run as parallel workstream, not prerequisite | Blocks M2 and all RAG features |
| EC-11 | DoD hallucination test count (20) insufficient | Blocks DoD as a quality gate |
| EC-12 | Missing: API rate limiting, cost controls, abuse prevention | Required before production launch |
| EC-13 | Missing: conversation turn limit and context window strategy | Must define before orchestration build |

---

### EC-01 — RAG Triage Mechanism Not Specified (FR-15 Gap)

**Concern:** FR-15 requires the system to decide per turn whether to retrieve from the vector store. The decision mechanism is not specified.

| Option | Mechanism | Latency impact | Reliability |
| --- | --- | --- | --- |
| A | Separate lightweight classifier LLM call | +100–300ms per turn | High — explicit decision |
| B | Rule-based keyword matching | Negligible | Low — brittle on paraphrasing |
| C | Tool-use in main LLM call (function calling) | None — same call | Medium — depends on instruction following |

**Recommendation:** Option C. Give the main LLM call a `retrieve_knowledge` tool and instruct it to call that tool when answering questions about company domain content. Avoids the latency and cost of a second LLM call and is more robust than keyword matching. Document in ADR-003.

**Blocker level:** Must resolve before backend agent build begins.

---

### EC-02 — Qualification State Object — Persistence Backend Not Specified (FR-01 Gap)

**Concern:** FR-01 requires a qualification state object per session. FR-07a confirms sessions are stateless across visits. The backend for in-session state is not specified.

| Option | Mechanism | Risk |
| --- | --- | --- |
| In-memory | State held in the process serving the session | Lost on process restart; unsafe for multi-instance deployments |
| Redis | External key-value store, TTL-based session expiry | Correct choice if backend scales horizontally |
| Database row | State persisted to the conversations table | Survivable across restarts; adds write overhead per turn |

**Recommendation:** In-memory is acceptable for a single-instance MVP with the risk documented. If horizontal scaling is anticipated from launch, Redis is the correct choice. Specify in the TRD.

**Blocker level:** Must resolve before backend architecture is finalised.

---

### EC-03 — Programmatic Escalation Trigger — Mechanism Not Specified (FR-09 Gap)

**Concern:** qualification-signals.md and human-handoff.md both explicitly require the escalation trigger to be programmatic, not LLM-driven. FR-09 requires it fires within the same exchange. The implementation mechanism is not described.

**Recommendation:** Implement as an explicit condition node in the conversation graph, evaluated before the response generation step. When the hot threshold is met (Problem + Authority + one more dimension), the orchestrator routes to the escalation proposal path. The LLM does not decide to escalate — it is given the escalation proposal as the response to generate. Define as a graph node in ADR-002.

**Blocker level:** Must resolve in orchestration design before agent build begins.

---

### EC-04 — Business Hours Detection Edge Cases

**Concern:** Business hours are defined as Monday–Friday, 9am–6pm CET. Three implementation risks:

1. **DST transitions:** CET becomes CEST (UTC+2) from the last Sunday of March to the last Sunday of October. A hardcoded `+01:00` offset produces one-hour errors for seven months of the year.
2. **Public holidays:** CET spans multiple countries with different calendars. Which applies?
3. **Timezone perspective:** The check is against team timezone, not visitor timezone. Correct, but must be explicit in code to prevent accidental reversal.

**Recommendation:** Use a timezone-aware library with an IANA identifier (`Europe/Madrid` or equivalent), not a fixed UTC offset. For public holidays: no awareness in v1 (document as a known limitation), configurable holiday calendar in v2.

**Blocker level:** Must define before the business hours module is built.

---

### EC-05 — RAG Relevance Threshold Not Specified (FR-17 Gap)

**Concern:** FR-17 requires a minimum relevance threshold but gives no value. Too low: irrelevant chunks reach the LLM, increasing hallucination risk. Too high: the fallback fires too often, degrading UX.

**Recommendation:** The threshold must be a configurable environment variable from day one, not hardcoded. Tuning process: ingest the knowledge base, run a representative test query set, plot the score distribution, set the threshold at the natural gap between relevant and irrelevant results. Document the selected value and reasoning in the ADR.

**Blocker level:** Cannot be finalised until the knowledge base exists (OQ-01). Must be configurable before any RAG testing begins.

---

### EC-06 — "Qualification Progress" Not Precisely Defined (FR-07 Gap)

**Concern:** FR-07 triggers a stall handoff after "6+ exchanges without qualification progress." Two interpretations:

1. No new qualification dimension confirmed (state object unchanged for 6 exchanges).
2. No Stage 3 proposal triggered in 6 exchanges.

**Recommendation:** Use interpretation 2 (no Stage 3 proposal in 6+ exchanges), consistent with chat-behaviour.md. Implementation: a turn counter per session that resets when a Stage 3 proposal is issued. If the counter reaches 6 without a Stage 3 trigger, the stall handoff path is activated. Document as the precise implementation contract in the TRD.

**Blocker level:** Low complexity once defined. Must resolve before the stall detection logic is built.

---

### EC-07 — Graceful Degradation Form — Submission Destination Not Specified (NFR Gap)

**Concern:** Section 6.2 requires a fallback contact form if the AI service is unavailable. The submission destination is not specified. If the form submits to the same backend process that serves the AI, a backend outage takes down both — the fallback provides no protection.

**Recommendation:** Route fallback form submissions through a path independent of the AI backend — a lightweight static endpoint or a third-party form service (e.g. Formspree) that operates without the AI service running. Decide before the frontend widget is built.

**Blocker level:** Must resolve before frontend widget build. Low implementation complexity.

---

### EC-08 — GDPR Data Processing Agreement with LLM Provider

**Concern:** Conversation history is sent to the LLM API. Even after PII field scrubbing, conversation history describes a natural person in context (company, business problem, role signals) and constitutes personal data under GDPR Article 4. A Data Processing Agreement (DPA) with the chosen LLM provider is mandatory under GDPR Article 28 before any real visitor data is processed.

The DPA must cover: lawful processing purposes, EU data residency guarantee, sub-processor disclosure, and deletion timelines.

**Provider status:**

- OpenAI: DPA available; EU data residency via Azure OpenAI.
- Anthropic: DPA available for enterprise; EU residency via Claude on AWS/Azure EU regions.
- Mistral (self-hosted): No third-party processing — DPA not required.

**Recommendation:** Treat DPA sign-off as a go/no-go condition for production traffic. Development with synthetic test data can proceed without it. Track as a legal task running in parallel with engineering.

**Blocker level:** Hard blocker for production launch.

---

### EC-09 — Performance Target Ambiguity: TTFT vs. Full Response

**Concern:** Section 6.1 specifies "< 3 seconds from visitor message to first token displayed." "First token displayed" implies time-to-first-token (TTFT). The DoD states "Response latency p95 < 3 seconds" without qualification — ambiguous.

**Typical RAG pipeline TTFT:** embedding query (50–100ms) + vector search (50–200ms) + LLM first token with streaming (500ms–2s) + network round-trip (50–150ms) ≈ 700ms–2.5s. Achievable at p95 with streaming enabled.

**Full response** at < 3s is feasible only for very short replies. Replies longer than ~100 tokens will exceed 3s at typical streaming rates.

**Recommendation:** Confirm the target is TTFT. Update the DoD to read: "p95 TTFT < 3s, measured from API request sent to first token received at client." Streaming must be enabled in the frontend widget from day one.

**Blocker level:** Must clarify before performance testing is designed.

---

### EC-10 — Content Audit (OQ-01) Must Run as a Parallel Workstream

**Concern:** The knowledge base content (case studies, service descriptions, team profiles) does not exist yet. Treating OQ-01 as a prerequisite that delays engineering start blocks:

- All FR-14 through FR-18 (RAG requirements)
- Relevance threshold tuning (EC-05)
- S3 proactive case study surfacing
- All hallucination testing in the DoD
- M2 acceptance testing

**Recommendation:** Start the content audit immediately as a parallel workstream with a hard two-week deadline from kickoff. Engineering builds the ingestion pipeline and RAG architecture against a synthetic placeholder knowledge base. The real content replaces the placeholder when delivered. The content deliverable format should be Markdown or plain text files — chunking and embedding are engineering responsibilities.

**Blocker level:** Blocks M2 and all RAG features. Does not block the widget skeleton, qualification state machine, handoff logic, or conversation model.

---

### EC-11 — Definition of Done: 20 Conversations Insufficient for Hallucination Testing

**Concern:** The DoD requires "No hallucination verified by manual review of 20 test conversations." 20 is not an adequate sample for a system routing real sales leads.

**Recommendation:** The test suite should include:

- 10 structured conversations per persona (5 personas) = 50 conversations
- 20–30 adversarial cases: out-of-scope questions, competitor probes, questions about content absent from the knowledge base
- Total: 70–80 conversations minimum

Test cases should have defined expected outputs, not be unscripted runs. Implement a repeatable eval framework (`promptfoo` or a lightweight custom harness) from day one so the suite can be re-run whenever the knowledge base changes.

**Blocker level:** Does not block development. The DoD must be updated before it is used as a quality gate.

---

### EC-12 — Missing: Rate Limiting, Cost Controls, and Abuse Prevention

**Concern:** The PRD has no mention of LLM API token budgets, per-session rate limits, cost alerting, or bot prevention. For a publicly-accessible widget, all four are required before production.

**Gaps:**

1. No maximum tokens per conversation — a bot or long session consumes credits without limit.
2. No per-IP or per-session rate limit.
3. No cost alerting — a traffic spike generates unexpected API costs silently.
4. No bot/crawler fingerprinting.

**Recommendation:** Define in the TRD:

- Max tokens per session (e.g. 4,000 context tokens) and truncation strategy (see EC-13)
- Rate limit per IP: e.g. 30 messages per 10 minutes
- Monthly cost cap with alerting at 80% of threshold
- Basic bot fingerprinting (user-agent, interaction timing)

**Blocker level:** Required before production launch. Not needed in a non-public dev environment.

---

### EC-13 — Missing: Conversation Turn Limit and Context Window Strategy

**Concern:** No maximum conversation length is defined. As conversation history grows, each turn becomes more expensive and the context window eventually overflows — at which point the conversation fails silently. Conversation depth is a success metric, so long conversations are expected.

**Options:**

1. Hard limit (e.g. 30 turns): close gracefully, offer handoff.
2. Sliding window: drop oldest exchanges, keep recent turns and system prompt.
3. Summarisation: periodically summarise older turns and inject the summary.

**Recommendation:** Sliding window in v1, configurable window size (e.g. last 10 exchanges + system prompt + qualification state object). The qualification state object is a persistent summary of key facts — it does not need to be re-derived from raw history, so the sliding window does not lose qualification context. Define the window size in the TRD.

**Blocker level:** Must define before conversation orchestration is implemented.

---

## Build Sequence

### Week 0 — Pre-Build Decisions

- [ ] ADR-001 completed: LLM provider selected (constrains ADR-002 and ADR-006)
- [ ] ADR-002 completed: orchestration framework selected
- [ ] TRD drafted: covers EC-01, EC-02, EC-03, EC-06, EC-07, EC-09, EC-12, EC-13
- [ ] DoD updated: hallucination test count raised to 70–80; TTFT definition added
- [ ] CRM platform confirmed (OQ-04) — engineering cannot build the handoff subsystem without this
- [ ] Topic restrictions initial list received (OQ-05) — engineering cannot write the system prompt without this

---

### Phase 1 — Foundation (Weeks 1–2)

**Backend:**

- Conversation orchestration graph (LangGraph or chosen framework), placeholder LLM responses
- Qualification state object: schema and persistence backend (EC-02)
- Programmatic escalation trigger graph node (EC-03)
- Programmatic Stage 3 gating
- Stall detection turn counter (EC-06)
- Business hours detection module, timezone-aware with IANA identifier (EC-04)
- Context packet generator as a deterministic function of session state

**Frontend:**

- Chat widget embed (script tag or React component per ADR-004)
- Streaming response rendering
- Stateless session management (FR-07a)
- Analytics event firing for all defined event types
- Graceful degradation fallback form with independent submission path (EC-07)

---

### Phase 2 — Core AI Behaviour (Weeks 3–4)

Requires Phase 1 complete and ADR-001 resolved:

- LLM integration with chosen provider
- System prompt: three-stage model, persona tone, disqualification paths, pricing deflection, topic restrictions (OQ-05)
- RAG triage mechanism via tool-use (EC-01, ADR-003)
- RAG layer: embedding pipeline, vector store setup, ingestion tooling against placeholder knowledge base
- Relevance threshold as configurable env variable (EC-05)

---

### Phase 3 — Handoff and Integration (Weeks 5–6)

Requires Phase 2 complete and CRM platform confirmed (OQ-04):

- Slack webhook integration (#new-leads)
- CRM integration
- Outside-hours capture flow
- Email fallback (sales@ for dual-channel failure)
- End-to-end handoff test: hot lead detected → Slack + CRM delivered successfully

---

### Phase 4 — Knowledge Base and RAG Validation (Weeks 7–8)

Requires real content deliverable from OQ-01:

- Ingest production knowledge base
- Tune and document relevance threshold (EC-05)
- RAG retrieval validation: relevant questions retrieve above threshold, irrelevant do not trigger retrieval
- Proactive case study surfacing (S3)

---

### Phase 5 — Testing and DoD Sign-Off (Weeks 9–10)

- Hallucination test suite: 70–80 structured conversations across all personas + adversarial cases (EC-11)
- Performance load test: TTFT p95 < 3s (EC-09)
- End-to-end handoff test: Slack + CRM delivery verified
- Graceful degradation test: AI service down → fallback form captures lead independently
- Analytics event audit: all defined events firing with correct schema
- GDPR data notice verified on first interaction

---

### Phase 6 — Launch Readiness

- DPA with LLM provider signed (EC-08)
- Rate limiting and cost controls in place (EC-12)
- Context window strategy and turn limit enforced (EC-13)
- Monitoring and alerting configured

---

## Engineering Sign-Off Checklist

**Gates development start:**

- [ ] ADR-001 completed (LLM provider)
- [ ] ADR-002 completed (orchestration framework)
- [ ] TRD drafted covering EC-01, EC-02, EC-03, EC-06, EC-07, EC-09, EC-12, EC-13
- [ ] DoD updated: hallucination test count and TTFT definition
- [ ] CRM platform confirmed — external dependency, blocks handoff subsystem build
- [ ] Topic restrictions list received — external dependency, blocks system prompt

**Gates production launch:**

- [ ] DPA with LLM provider signed (EC-08)
- [ ] Rate limiting and cost controls implemented (EC-12)
- [ ] Real knowledge base ingested and threshold tuned (EC-05)
- [ ] Hallucination test suite passing at 70–80 conversations (EC-11)
- [ ] TTFT p95 < 3s verified under load (EC-09)

---

*The next document in this series is the Technical Requirements Document (TRD), which resolves the engineering concerns raised here and records all technology decisions in the corresponding ADRs.*
