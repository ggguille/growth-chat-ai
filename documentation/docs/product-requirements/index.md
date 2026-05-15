---
description: "Product Requirements Document for the AI-powered lead qualification chat — defines feature scope, functional and non-functional requirements, technical stack candidates, and open questions."
---

# Product Requirements Document (PRD)

## AI-Powered Lead Qualification Chat

**Project:** AI-powered lead qualification chat
**Version:** 1.0
**Status:** Final — stakeholder sign-off complete, engineering review complete; TRD and CDD complete (May 2026); two external dependencies outstanding (OQ-04, OQ-05)
**Last updated:** May 2026
**Owner:** Product / AI Engineering Team

---

## 1. Executive Summary

### 1.1 The Problem

The company website receives consistent inbound traffic but converts poorly into
qualified leads. The only conversion mechanism is a static contact form that cannot
engage visitors, answer questions, or differentiate between a CTO actively evaluating
vendors and a curious researcher. The sales team receives cold leads with no context.

Full problem definition in [problem-statement.md](../problem-statement.md).

### 1.2 The Solution

An AI-powered conversational chat widget embedded in the company landing page that
acts as an always-on acquisition channel. The chat responds to visitor questions with
the depth of a knowledgeable company representative, qualifies leads progressively
through natural conversation, and routes hot leads to the sales team in real time.

### 1.3 The MVP Hypothesis

> An intelligent conversational interface converts more visitors into qualified leads
> than a static contact form, and produces leads with a higher qualification rate.

This PRD defines the minimum viable implementation needed to validate that hypothesis.
It is not the complete system — it is the smallest version of the system that produces
a meaningful signal.

### 1.4 Success Metrics

| Metric | Target | Measurement |
| --- | --- | --- |
| Lead qualification rate | Chat leads reach sales call at ≥ 1.5× the rate of form leads (minimum threshold for go/no-go) | CRM comparison over 90 days |
| Contact capture rate | > 15% of chat conversations result in email captured | Chat analytics |
| Hot lead response time | Sales team follows up within 2 business hours of Slack notification | Handoff system logs |
| Conversation progression | > 30% of qualifying interactions reach Stage 3 (proposal) | Conversation state analytics |
| Conversation depth | Average number of exchanges per conversation before drop-off | Chat analytics |
| Go / no-go decision | Based on above metrics at 90-day mark | Product review |

Contact capture rate should not be read in isolation. Low capture rate paired with high conversation depth may indicate the approach is building brand value that does not show up in immediate conversions. A strategy re-evaluation is warranted only when both contact capture rate and conversation depth are below expectation simultaneously.

---

## 2. Background and Strategic Context

### 2.1 Why This, Why Now

The company's growth depends on converting inbound interest into sales conversations.
The current form-based approach creates a high-friction, low-context entry point
that is misaligned with how technical buyers — the primary company audience — make
vendor decisions. They research deeply, ask specific questions, and move on quickly
if they do not find confidence-building answers.

Simultaneously, AI-powered chat is becoming table stakes for B2B service companies
competing for technical buyers. This is not a novel experiment — it is a catch-up
investment with a clear commercial rationale.

### 2.2 Alignment with Company Positioning

The chat reinforces three core elements of the company's positioning:

**Senior engineers.** The chat speaks with technical depth and specificity,
not marketing language. It demonstrates the quality of thinking the visitor
can expect from the team.

**AI expertise.** A well-executed AI chat product is itself a proof point.
It signals that the company builds AI systems that work in production.

**European timezone coverage.** The outside-hours flow converts this
differentiator into a tangible experience — visitors understand the timezone
advantage before they speak to anyone.

---

## 3. Target Users

Full persona definitions in [user-personas](../user-personas/). This section summarises the
implications for product scope.

### 3.1 Target Personas

| Persona | Intent | Chat priority | Escalation |
| --- | --- | --- | --- |
| P1 — Evaluating CTO | High — active vendor evaluation | Technical depth, fast qualification | Immediate when hot |
| P2 — Exploring Founder | Medium — scoping and exploring | Education, trust building, lower friction capture | After nurture signals |
| P3 — Referred Decision-Maker | Very high — ready to talk | Remove friction, connect fast | Immediate |

### 3.2 Negative Personas

| Persona | Intent | Chat behaviour |
| --- | --- | --- |
| N1 — Competitor | Intelligence gathering | Public information only, no escalation |
| N2 — Curious Researcher | Research / exploration | Helpful, no escalation, no contact push |

### 3.3 Persona-Specific Tone

The chat adapts its register to the visitor profile it detects, within the
boundaries of the overall company voice.

**With P1:** Technically confident, peer-level. Uses engineering vocabulary without
explanation. Gets to the point. Does not over-explain what the company does.

**With P2:** Patient, educational, honest about complexity and cost. Does not
oversell. Acknowledges when something is a bigger conversation than a chat can handle.

**With P3:** Direct and efficient. Minimal qualification friction. Prioritises
connecting them with the right person quickly.

**Overall voice:** Professional but not corporate. Warm but not casual. The register
of a senior company engineer talking to a peer — not a sales assistant reading
from a script.

---

## 4. Feature Scope — MoSCoW

### 4.1 Must Have — MVP v1

These features are required to validate the core hypothesis. Without them,
the experiment cannot produce meaningful signal.

**M1 — Conversational interface**
A chat widget embedded on the company landing page. Visible as a passive icon
on page load. Opens into a full conversational interface on click. Responsive
on desktop and mobile.

**M2 — Contextual question answering with selective RAG**
The chat answers questions about the company's services, engagement models, team
structure, and expertise using a hybrid knowledge architecture (Option B):

- **System prompt layer:** Conversation behaviour, qualification logic, tone
  guidelines, and persona instructions. Never contains domain content — only
  instructions. This layer is stable and controlled.
- **RAG layer:** Company-specific domain knowledge — case studies, service
  descriptions, team profiles, engagement models — stored as embeddings in a
  vector store and retrieved selectively at query time.

The system decides per turn whether to retrieve from the vector store or respond
directly from instructions. Questions about the company's work, expertise, or specific
case studies trigger retrieval. Questions about conversation process, pricing
deflection, or handoff logic are handled from the prompt layer only.

Knowledge base scope for v1: publicly available company case studies (no NDA-protected
content), service offering descriptions, team and location profile, engagement model
documentation. Content audit required before build (see OQ-01) — only content already
published on the company website qualifies for v1 ingestion.

**M3 — Progressive qualification**
The chat detects fit signals across four dimensions (problem, authority, company,
timing) incrementally through natural conversation. It maintains a qualification
state object per session and escalates when the hot lead threshold is reached.
Full logic defined in [qualification-signals.md](../considerations/qualification-signals.md).

**M4 — Three-stage conversation model**
Every conversation follows the respond → advance → propose sequence defined
in [chat-behaviour.md](../considerations/chat-behaviour.md). The system does not ask for contact
information before providing value. It proposes the next step proactively
when maturity signals are detected.

**M5 — Hot lead escalation (business hours)**
When a hot lead is detected during business hours, the chat proposes a
connection to the company team and collects the visitor's email. It delivers
the context packet to two channels simultaneously: a Slack message to
`#new-leads` (for immediate visibility) and a new lead record in the CRM (for
record and follow-up tracking). Email to `sales@` is a fallback only if both
primary channels are unavailable. The sales team follows up by email or phone
within 2 business hours of receiving the Slack notification. No self-serve
booking tool is used — all scheduling is handled by the sales rep directly.

**M6 — Outside-hours capture flow**
When a hot lead or explicit handoff request occurs outside business hours,
the chat is transparent about availability, makes a specific follow-up
commitment, captures email, and optionally sends a relevant resource.
The company timezone is framed as a feature, not an apology.

**M7 — Negative persona handling and disqualification**
The chat does not escalate visitors classified as N1 or N2, and handles the
broader set of no-fit visitors defined in the disqualification path
(individual contractors, geography or regulatory mismatches, and any context
that clearly falls outside the company's ICP).

For N1 (competitor): responds only with publicly available information;
does not engage with operational or pricing probes.

For N2 (researcher): helpful, no escalation, no contact push.

For all other no-fit visitors: acknowledges the mismatch honestly, offers
a relevant resource where possible, and closes the conversation with a positive
impression. The chat never pretends a visitor is a fit and never requests
contact information from a visitor who will not convert.

Full disqualification criteria and example responses in
[chat-behaviour.md](../considerations/chat-behaviour.md).

**M8 — Existing client deflection**
When a visitor identifies as an existing company client seeking support, the
chat recognises the out-of-scope context and routes them to the appropriate
contact (account management), not to the sales team.

**M9 — Pricing deflection**
The chat does not give specific pricing. When asked, it acknowledges the
question honestly and explains why scoping is needed before any number is
meaningful. It offers a call as the natural next step. It does not sound evasive.

**M10 — CRM lead record creation**
At the point of any escalation or capture handoff, the system creates a new
lead record in the company CRM pre-populated with the full context packet
(conversation summary, qualification state, lead level, trigger, visitor data,
timestamp). The CRM is the system of record for all leads — the Slack
notification links to it so the sales rep does not need to reconstruct context.
Specific CRM platform to be confirmed pending OQ-04.

Example response pattern:
> *"We don't publish standard rates — the right engagement structure really
> depends on what you're building, your timeline, and how you work best with
> external teams. A 20-minute conversation with one of our engineers would
> give you a much more useful number than anything I could tell you here.
> Want me to set that up?"*

### 4.2 Should Have — MVP v1 if capacity allows

**S1 — Proactive greeting trigger**
After a visitor spends more than 45 seconds on the page without interacting,
the chat icon displays a subtle prompt (e.g. "Have a question about AI
engineering?"). Does not auto-open the chat — respects the visitor's agency.

**S2 — Conversation summary email to visitor**
After a handoff, the chat sends the visitor a brief email summarising the
conversation and confirming next steps. Increases trust and reduces no-shows
on booked calls.

**S3 — Relevant case study surfacing**
Within the static knowledge base, the chat proactively surfaces the most
relevant case study based on the visitor's described problem, rather than
waiting to be asked.

### 4.3 Could Have — Backlog v2

**C1 — RAG over full case study library**
Dynamic retrieval from a structured knowledge base of all company case studies,
enabling precise matching between visitor problems and relevant work. Requires
a content audit and embedding pipeline before implementation.

**C2 — A/B testing framework**
Infrastructure to test different greeting approaches, conversation opening
lines, and escalation timing. Requires a baseline dataset from v1 before
meaningful experiments can be designed.

**C3 — Multi-page context awareness**
The chat knows which page the visitor is on and adjusts its opening approach
accordingly (homepage vs. services page vs. a specific case study).

**C4 — Returning visitor recognition**
If a visitor has chatted before, the chat acknowledges the previous conversation
and picks up from where they left off, rather than starting cold.

### 4.4 Won't Have — Explicitly out of scope

**W1 — Support channel for existing clients.**
The chat is an acquisition tool. Client support is a different product
with different requirements.

**W2 — Autonomous deal closing.**
The chat qualifies and connects. It does not negotiate, quote, or close.

**W3 — Voice or video interface.**
Text only in v1.

**W4 — Integration with third-party chat platforms** (Intercom, Drift, etc.)
Custom build in v1 to maintain full control over conversation logic and data.

**W5 — Self-serve calendar booking.**
All handoff flows end with email collection. Scheduling is handled by the sales
rep directly — no Calendly or equivalent integration in v1.

---

## 5. Functional Requirements

### 5.1 Conversation System

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-01 | The system maintains a qualification state object per session tracking the four fit dimensions and their confidence levels | Must |
| FR-02 | The system follows the three-stage model: respond → advance → propose, in that order, within each exchange | Must |
| FR-03 | The system never asks for contact information before completing at least one substantive response to the visitor's question | Must |
| FR-04 | The system asks a maximum of one qualifying question per exchange | Must |
| FR-05 | The system detects maturity signals and triggers a Stage 3 proposal proactively when all three signals are present | Must |
| FR-06 | The system adapts its register to the detected persona profile | Should |
| FR-07 | The system recognises when a conversation has stalled (6+ exchanges without a Stage 3 proposal being triggered) and offers a human. A turn counter per session resets when a Stage 3 proposal is issued; at 6 it activates the stall handoff path. | Must |
| FR-07a | The system treats each session as stateless — no cross-session memory is maintained in v1. Each visit starts fresh regardless of prior conversations | Must |

### 5.2 Qualification and Escalation

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-08 | The system classifies each session as hot, warm, or cold based on the scoring model in [qualification-signals.md](../considerations/qualification-signals.md) | Must |
| FR-09 | Hot lead classification triggers an escalation proposal within the same exchange | Must |
| FR-10 | An explicit visitor request for a human triggers immediate escalation regardless of qualification state | Must |
| FR-11 | Escalation to sales is blocked for sessions classified as N1, N2, or any visitor context matching the disqualification criteria in chat-behaviour.md | Must |
| FR-11a | When a session is classified as no-fit, the system acknowledges the mismatch, offers a relevant resource where possible, and closes without requesting contact information | Must |
| FR-12 | The system generates a structured context packet at the point of handoff | Must |
| FR-13 | The context packet contains: conversation summary, qualification state, lead level, trigger, visitor-provided data, timestamp, consultant/evaluator flag if the visitor identified as evaluating on behalf of a client | Must |

### 5.3 Knowledge Base and RAG

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-14 | The system maintains two distinct knowledge layers: a prompt layer (behaviour and instructions only) and a RAG layer (company domain content only). No domain content lives in the system prompt. | Must |
| FR-15 | The system performs a retrieval step when the visitor's message contains a question about the company's work, services, case studies, or expertise. It responds from instructions only when the question is about process, pricing, or conversation mechanics. | Must |
| FR-16 | The system does not fabricate information not present in the retrieved context or the instruction layer. If retrieval returns no relevant result, the system acknowledges the limit and offers to connect the visitor with a human. | Must |
| FR-17 | Retrieved chunks are ranked by relevance score. Only chunks above a minimum relevance threshold are used in the response. Below-threshold results are treated as no result. The threshold must be a configurable environment variable, not hardcoded; the value is determined during RAG tuning in Phase 4. | Must |
| FR-18 | The system surfaces a relevant case study proactively — without being asked — when the visitor's described problem matches a retrieved case study with high relevance score. | Should |

### 5.4 Handoff and Capture

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-19 | At the point of any escalation handoff, the system delivers the context packet to two destinations: a Slack message to `#new-leads` and a new CRM lead record. Email to `sales@` is used only if both primary channels are unavailable. If one destination fails and the other succeeds, the failure is logged, an alert is triggered, and the failed delivery is retried; the handoff is not considered complete until both destinations confirm delivery or the retry limit is reached. | Must |
| FR-20 | The system captures email with a clear, value-attached reason — never as a standalone request | Must |
| FR-21 | The system detects outside-hours context and executes the outside-hours capture flow | Must |
| FR-22 | The outside-hours flow states the specific follow-up time commitment (next business day before 10am CET). The system does not offer same-day follow-up for conversations that begin after 4pm CET | Must |
| FR-23 | The system routes existing client support requests to account management contact, not to sales | Must |
| FR-24 | All handoff flows — hot, warm, and cold — end with email collection. No self-serve booking tool is offered. The sales rep follows up directly to schedule a call | Must |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Requirement | Target |
| --- | --- |
| Chat response latency (p95) | < 3 seconds from visitor message to first token displayed |
| Time to first meaningful response | < 5 seconds end-to-end |
| Sales notification delivery | Slack + CRM delivery on hot lead detection (best-effort, no hard SLA for MVP) |
| Widget load time | < 1 second on page load, non-blocking |

### 6.2 Availability

| Requirement | Target |
| --- | --- |
| Widget availability | 99.5% monthly uptime |
| Graceful degradation | If the AI service is unavailable, the widget falls back to a simple contact capture form — it does not show an error and disappear |
| Outside-hours handling | Operates 24/7 — availability refers to the AI service, not business hours |

### 6.3 Security and Privacy

| Requirement | Detail |
| --- | --- |
| Data in transit | All communication encrypted via TLS 1.3 |
| Conversation data storage | Conversations stored for 90 days for analytics, then deleted unless a lead record exists |
| PII handling | Email addresses and names treated as PII — stored only in the lead capture system, not in raw conversation logs sent externally |
| GDPR compliance | Chat displays a brief data notice on first interaction. Visitor can request deletion of their data. |
| No sensitive data in prompts | Conversation history sent to the LLM API must be scrubbed of any data that should not leave company infrastructure |

### 6.4 Observability

| Requirement | Detail |
| --- | --- |
| Conversation logging | All conversations logged with session ID, timestamp, persona classification, qualification state at close, and outcome |
| Escalation logging | All handoff events logged with trigger type, lead level, and response time |
| Error logging | LLM errors, timeout events, and fallback activations logged with sufficient context to diagnose |
| Analytics events | Defined event schema for: chat opened, first message sent, qualification state change, contact captured, escalation triggered, conversation ended. Full event schema with field names, types, and PII rules defined in TRD Section 9 (Observability) — 8 frontend CustomEvents on the `<growth-chat>` element and 8 backend Langfuse traces/spans. Both layers must conform to the schema before implementation. |

---

## 7. Technical Constraints and Candidates

### 7.1 Stack Candidates — v1

No technology decisions are final at this stage. This section lists the
candidate options for each component, the key evaluation criteria, and the
open decision. Final selections are made in the Technical Requirements Document
and recorded in the corresponding ADR.

---

#### LLM Provider

> *Decision: **Anthropic Claude Haiku 4.5** via the Anthropic API — ADR-001 (Accepted, April 2026). Selected for instruction-following reliability under a complex system prompt, EU data processing endpoint availability (Frankfurt), function calling support for RAG triage (EC-01), and cost profile at MVP volume.*

---

#### Conversation Orchestration

> *Decision: **LangGraph** (`StateGraph`) — ADR-002 (Accepted, April 2026). Selected for native stateful graph execution, explicit node/edge control suited to the qualification state machine, support for deterministic programmatic nodes alongside LLM nodes, and built-in observability of graph execution.*

---

#### Knowledge Architecture

*Decision: Selective RAG — Option B (agreed in PRD). See M2 for rationale.*
*Component decisions resolved — ADR-003 (Accepted, April 2026) and ADR-004 (Accepted, April 2026).*

| Component | Decision | ADR |
| --- | --- | --- |
| Vector store | **pgvector** (PostgreSQL extension, HNSW index) | ADR-003 |
| Embedding model | **OpenAI text-embedding-3-small** (1536 dimensions, EU endpoint) | ADR-003 |
| RAG triage mechanism | **Tool use** — `retrieve_knowledge` function call in the main LLM turn; no separate classifier call (EC-01) | ADR-003 |
| Session state persistence | **langgraph-checkpoint-postgres** (production); `MemorySaver` (local dev) | ADR-004 |

---

#### Frontend Widget

> *Decision: **Custom web component** (`<growth-chat>` element, embeds via a `<script>` tag on the company site) — ADR-005 (Accepted, April 2026). Selected for minimal bundle footprint (≤ 200KB gzipped), no framework dependency on the host site, full control over streaming UX, and straightforward embedding without a site rebuild.*

---

#### Notification and Lead Capture

*Decision: Both Slack webhook (`#new-leads`) and CRM integration are required in V1 — Slack for speed, CRM for record (see M5, M10, FR-19). Email to `sales@` is fallback only on dual-channel failure. No self-serve booking tool — all scheduling handled by the sales rep directly. CRM platform unconfirmed pending **OQ-04** (external dependency — blocks Phase 3 build). CRM adapter ADR to be written once OQ-04 is resolved.*

| Candidate | Strengths | Weaknesses |
| --- | --- | --- |
| Slack webhook | Instant, zero cost, sales team already in Slack | No structured data, hard to query later, not a CRM |
| Email (SMTP / SendGrid) | Universal, structured template possible, easy to route | Slower than Slack, higher chance of being missed |
| Zapier / Make webhook | No-code routing to any destination, easy to change target | External dependency, adds latency, not suitable for real-time handoff |
| Native CRM integration | Structured lead record from day one | Requires CRM selection (OQ-04 unresolved), significant added complexity for MVP |

**Key evaluation criteria:** reliable delivery of the context packet (FR-13),
operational simplicity for MVP. Slack and CRM are both required; the evaluation
focuses on which CRM and which Slack integration approach.

---

#### Data Storage

> *Decision: **PostgreSQL** — single storage backend for all persistence needs (ADR-003, ADR-004).*

| Purpose | Solution | ADR |
| --- | --- | --- |
| Knowledge index (vector store) | PostgreSQL + **pgvector** extension (HNSW index) | ADR-003 |
| Session state (conversation history, qualification state) | PostgreSQL + **langgraph-checkpoint-postgres** | ADR-004 |
| Handoff audit records | PostgreSQL — `handoff_records` table | ADR-004 |
| Managed instance | **Neon** — `eu-central-1` (Frankfurt) | ADR-006 |

No separate vector store service is needed. PostgreSQL handles both the knowledge index and session state, keeping the infrastructure footprint minimal.

---

#### Rate Limiting, Cost Controls, and Context Window Management

> *Resolved in TRD Section 8 and Section 10 (May 2026) — EC-12, EC-13.*

**Rate limiting and cost controls (EC-12 — resolved):** Per-IP rate limiting via Cloudflare Rules (30 req / 10 min); per-session rate limiting via `slowapi` middleware (20 messages / 5 min); per-session token budget of 16,000 tokens (`MAX_TOKENS_PER_SESSION`); monthly cost cap of $50 with alerting at 80% (`MONTHLY_COST_CAP_USD`); bot prevention via Cloudflare Bot Score, API key validation, and 2,000-character message size limit. See TRD Section 8.

**Context window management (EC-13 — resolved):** Sliding window strategy — `CONTEXT_WINDOW_TURNS = 10` exchange pairs (configurable environment variable). Qualification state is stored independently on `SessionState` and is never evicted from the window, so the LLM never loses qualification context regardless of conversation length. See TRD Section 10.

---

#### Cloud Provider

> *Decision: **Fly.io (fra) + Neon (eu-central-1) + Cloudflare** — ADR-006 (Accepted, April 2026). Full EU data residency at every processing step; low operational overhead for a small team.*

| Component | Decision | Notes |
| --- | --- | --- |
| Application hosting | **Fly.io** — `fra` region (Frankfurt) | Deploy via CLI; EU data residency; auto-restart on failure |
| PostgreSQL (managed) | **Neon** — `eu-central-1` (Frankfurt) | Serverless Postgres; pgvector supported; AES-256 at rest |
| Edge / CDN / WAF | **Cloudflare** | TLS 1.3 termination; rate limiting rules; Bot Score; HSTS |

All components — LLM API (Anthropic EU endpoint), embeddings (OpenAI EU endpoint), session state, and knowledge index — process and store data within EU territory, satisfying GDPR Article 44 without relying on Standard Contractual Clauses.

---

### 7.2 Key Technical Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| LLM hallucination on company-specific facts | Medium | High — damages trust | Domain content exclusively in RAG layer (FR-14); retrieval threshold prevents low-confidence results reaching the LLM (FR-17); hallucination tested in DoD |
| Retrieval returning irrelevant chunks | Medium | Medium — degrades answer quality | Minimum relevance threshold defined and tuned during development (FR-17); fallback to human offer if no result above threshold |
| Response latency exceeds 3s on complex queries | Low | Medium — degrades UX | Streaming responses; timeout fallback with "let me connect you with the team" |
| Competitor extraction of sensitive information | Low | Medium | Defensive prompt design; no sensitive information in knowledge base |

---

## 8. Definition of Done

A feature is complete when it meets all of the following:

- [ ] Functional requirement implemented and verified against the acceptance criteria
- [ ] Unit tests covering the qualification state logic
- [ ] Conversation tested against all five persona profiles with at least 10 simulated conversations each
- [ ] Edge cases documented and handled (stall, frustration, out-of-scope, negative persona)
- [ ] Analytics events firing correctly for all defined event types
- [ ] No hallucination on company knowledge base content (verified by manual review of 70–80 structured test conversations: 10 per persona × 5 personas + 20–30 adversarial cases covering out-of-scope questions, competitor probes, and absent-content queries). Test cases must have defined expected outputs and be run through a repeatable eval framework.
- [ ] RAG retrieval verified: relevant questions return above-threshold results; irrelevant questions do not trigger retrieval
- [ ] Prompt layer and RAG layer correctly separated — no domain content in system prompt
- [ ] p95 TTFT (time-to-first-token) < 3 seconds verified under a stress test of 10 concurrent sessions sustained for 10 minutes (TRD Section 7 — ~40× expected peak production concurrency). Streaming must be enabled; full-response latency is not the target metric.
- [ ] GDPR data notice displayed on first interaction
- [ ] Graceful degradation tested (AI service down → fallback form)
- [ ] Sales notification (Slack + CRM) received and verified end-to-end on hot lead detection
- [ ] Conversation end is consistently defined in code and analytics as: explicit close action, 15-minute inactivity timeout, or session expiry — all three cases fire the conversation-ended event with the correct termination type field.

---

## 9. Open Questions

These questions remain unresolved and require input before or during development.

| # | Question | Owner | Needed by |
| --- | --- | --- | --- |
| OQ-01 | Which specific company case studies should be included in the v1 knowledge base? Requires a content audit. **Constraint resolved: v1 is restricted to publicly available content only — no NDA-protected case studies.** **Sequencing resolved: the content audit must begin immediately at kickoff as a parallel workstream with a hard two-week deadline — it is not a prerequisite that blocks engineering start. Engineering builds the ingestion pipeline against a synthetic placeholder knowledge base; real content replaces it when delivered. Content format: Markdown or plain text files.** | marketing / PM | Kickoff + 2 weeks |
| OQ-03 | ~~What is the current form submission volume and qualification rate?~~ **Resolved:** 30-day analytics export (form submission count + form-to-sales-call rate) to be completed before deployment. Responsibility: Product Owner. | sales / analytics | Before deployment |
| OQ-04 | Is there an existing CRM? If so, which one? (CRM integration is required in V1 — M10 — this determines the implementation path) | ops | Before build starts |
| OQ-05 | Are there specific topics that must never be discussed — beyond pricing and internal operations? | leadership | Before build starts |

---

## 10. Referenced Documents

| Document | Description |
| --- | --- |
| [problem-statement.md](../problem-statement.md) | Distilled problem statement — authoritative input to this PRD |
| [user-personas](../user-personas/) | Five visitor personas — three target, two negative |
| [chat-behaviour.md](../considerations/chat-behaviour.md) | Conversation model and lead capture principles |
| [qualification-signals.md](../considerations/qualification-signals.md) | Qualification dimensions, scoring model, escalation logic |
| [human-handoff.md](../considerations/human-handoff.md) | Handoff triggers, execution sequences, escalation matrix |

---

*This PRD defines the scope of the company website chat MVP. It is a living document
and will be updated as open questions are resolved and decisions are made during
development. The Conversation Design Document and the Technical Requirements Document
are complete — the TRD is the authoritative reference for all technology decisions
and implementation specifications.*
