---
description: "Product Requirements Document for the AI-powered lead qualification chat — defines feature scope, functional and non-functional requirements, technical stack candidates, and open questions."
---

# Product Requirements Document (PRD)

## AI-Powered Lead Qualification Chat

**Project:** AI-powered lead qualification chat
**Version:** 1.0
**Status:** Draft — pending engineering and stakeholder review
**Last updated:** April 2026
**Owner:** Product / AI Engineering Team

---

## 1. Executive Summary

### 1.1 The Problem

The company website receives consistent inbound traffic but converts poorly into
qualified leads. The only conversion mechanism is a static contact form that cannot
engage visitors, answer questions, or differentiate between a CTO actively evaluating
vendors and a curious researcher. The sales team receives cold leads with no context.

Full problem definition in [problem-statement.md](./problem-statement.md).

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
| Lead qualification rate | Chat leads reach sales call at higher rate than form leads | CRM comparison over 90 days |
| Contact capture rate | > 15% of chat conversations result in email captured | Chat analytics |
| Hot lead response time | < 5 minutes during business hours | Handoff system logs |
| Conversation progression | > 30% of qualifying interactions reach Stage 3 (proposal) | Conversation state analytics |
| Go / no-go decision | Based on above metrics at 90-day mark | Product review |

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

Full persona definitions in [user-personas](./user-personas/). This section summarises the
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

Knowledge base scope for v1: all available company case studies, service offering
descriptions, team and location profile, engagement model documentation.
Content audit required before build (see OQ-01).

**M3 — Progressive qualification**
The chat detects fit signals across four dimensions (problem, authority, company,
timing) incrementally through natural conversation. It maintains a qualification
state object per session and escalates when the hot lead threshold is reached.
Full logic defined in [qualification-signals.md](./considerations/qualification-signals.md).

**M4 — Three-stage conversation model**
Every conversation follows the respond → advance → propose sequence defined
in [chat-behaviour.md](./considerations/chat-behaviour.md). The system does not ask for contact
information before providing value. It proposes the next step proactively
when maturity signals are detected.

**M5 — Hot lead escalation (business hours)**
When a hot lead is detected during business hours, the chat proposes a
connection to the company team immediately. It collects email and optional
preferred time. It sends a structured notification to the sales team containing
the conversation summary and qualification state. Target: < 5 minutes from
detection to notification.

**M6 — Outside-hours capture flow**
When a hot lead or explicit handoff request occurs outside business hours,
the chat is transparent about availability, makes a specific follow-up
commitment, captures email, and optionally sends a relevant resource.
The company timezone is framed as a feature, not an apology.

**M7 — Negative persona handling**
The chat does not escalate visitors classified as N1 or N2. For N1 (competitor),
it responds only with publicly available information and does not engage with
operational or pricing probes. For N2 (researcher), it is helpful but does
not push toward capture or escalation.

**M8 — Existing client deflection**
When a visitor identifies as an existing company client seeking support, the
chat recognises the out-of-scope context and routes them to the appropriate
contact (account management), not to the sales team.

**M9 — Pricing deflection**
The chat does not give specific pricing. When asked, it acknowledges the
question honestly and explains why scoping is needed before any number is
meaningful. It offers a call as the natural next step. It does not sound evasive.

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

**C2 — CRM integration**
Automatic creation of a lead record in the company's CRM at the point of handoff,
populated with the qualification state and conversation summary. Requires
CRM selection and API access.

**C3 — A/B testing framework**
Infrastructure to test different greeting approaches, conversation opening
lines, and escalation timing. Requires a baseline dataset from v1 before
meaningful experiments can be designed.

**C4 — Multi-page context awareness**
The chat knows which page the visitor is on and adjusts its opening approach
accordingly (homepage vs. services page vs. a specific case study).

**C5 — Returning visitor recognition**
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
| FR-07 | The system recognises when a conversation has stalled (6+ exchanges without qualification progress) and offers a human | Must |

### 5.2 Qualification and Escalation

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-08 | The system classifies each session as hot, warm, or cold based on the scoring model in [qualification-signals.md](./considerations/qualification-signals.md) | Must |
| FR-09 | Hot lead classification triggers an escalation proposal within the same exchange | Must |
| FR-10 | An explicit visitor request for a human triggers immediate escalation regardless of qualification state | Must |
| FR-11 | Escalation to sales is blocked for sessions classified as N1 or N2 | Must |
| FR-12 | The system generates a structured context packet at the point of handoff | Must |
| FR-13 | The context packet contains: conversation summary, qualification state, lead level, trigger, visitor-provided data, timestamp | Must |

### 5.3 Knowledge Base and RAG

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-14 | The system maintains two distinct knowledge layers: a prompt layer (behaviour and instructions only) and a RAG layer (company domain content only). No domain content lives in the system prompt. | Must |
| FR-15 | The system performs a retrieval step when the visitor's message contains a question about the company's work, services, case studies, or expertise. It responds from instructions only when the question is about process, pricing, or conversation mechanics. | Must |
| FR-16 | The system does not fabricate information not present in the retrieved context or the instruction layer. If retrieval returns no relevant result, the system acknowledges the limit and offers to connect the visitor with a human. | Must |
| FR-17 | Retrieved chunks are ranked by relevance score. Only chunks above a minimum relevance threshold are used in the response. Below-threshold results are treated as no result. | Must |
| FR-18 | The system surfaces a relevant case study proactively — without being asked — when the visitor's described problem matches a retrieved case study with high relevance score. | Should |

### 5.4 Handoff and Capture

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-19 | The system sends a structured sales notification within 5 minutes of hot lead detection during business hours | Must |
| FR-20 | The system captures email with a clear, value-attached reason — never as a standalone request | Must |
| FR-21 | The system detects outside-hours context and executes the outside-hours capture flow | Must |
| FR-22 | The outside-hours flow states the specific follow-up time commitment (next business day before 10am CET) | Must |
| FR-23 | The system routes existing client support requests to account management contact, not to sales | Must |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Requirement | Target |
| --- | --- |
| Chat response latency (p95) | < 3 seconds from visitor message to first token displayed |
| Time to first meaningful response | < 5 seconds end-to-end |
| Sales notification delivery | < 5 minutes from hot lead detection to notification received |
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
| Analytics events | Defined event schema for: chat opened, first message sent, qualification state change, contact captured, escalation triggered, conversation ended |

---

## 7. Technical Constraints and Candidates

### 7.1 Stack Candidates — v1

No technology decisions are final at this stage. This section lists the
candidate options for each component, the key evaluation criteria, and the
open decision. Final selections are made in the Technical Requirements Document
and recorded in the corresponding ADR.

---

#### LLM Provider

> *Decision owner: AI Engineering Lead — ADR-001 (pending)*

| Candidate | Strengths | Weaknesses |
| --- | --- | --- |
| OpenAI GPT-4o | Best instruction-following, wide ecosystem, streaming support, function calling | Cost at scale, data leaves EU by default (GDPR consideration) |
| Anthropic Claude Sonnet 3.5 | Strong reasoning, large context window, good at staying in character, EU data processing available | Smaller ecosystem, fewer native integrations |
| Mistral Large (self-hosted) | Full data control, EU infrastructure, no per-token cost at scale | Higher infrastructure overhead, weaker instruction-following than GPT-4o |

**Key evaluation criteria:** instruction-following quality, GDPR compliance posture,
cost at projected conversation volume, streaming latency, function calling support
for qualification state management.

---

#### Conversation Orchestration

> *Decision owner: AI Engineering Lead — ADR-002 (pending)*

| Candidate | Strengths | Weaknesses |
| --- | --- | --- |
| LangGraph | Native stateful graph execution, explicit node/edge control, ideal for multi-step qualification logic, strong observability | Steeper learning curve, more boilerplate than LangChain |
| LangChain LCEL | Simpler to get started, large community, broad integrations | Less suited to complex branching state machines, harder to maintain qualification state explicitly |
| Custom state machine (no framework) | Full control, no framework dependencies, minimal overhead | More code to maintain, reinvents solved problems |

**Key evaluation criteria:** ability to maintain an explicit qualification state
object across turns, support for conditional branching (hot/warm/cold logic),
observability and debuggability of conversation state.

---

#### Knowledge Architecture

*Decision: Selective RAG — Option B (agreed in PRD). See M2 for rationale.*
*Component-level decisions below remain open — ADR-003 (pending)*

| Component | Candidate | Strengths | Weaknesses |
| --- | --- | --- | --- |
| Vector store | Chroma (local) | Zero infrastructure, fast to set up, good for MVP | Not managed, manual scaling, not suitable for production at volume |
| Vector store | Pinecone (managed) | Fully managed, production-ready, low latency at scale | Cost, external dependency, data leaves infrastructure |
| Vector store | pgvector (Postgres extension) | Stays within existing DB infrastructure if Postgres is used, no new service | Less mature than dedicated vector stores, limited ANN algorithm options |
| Embedding model | OpenAI text-embedding-3-small | Low cost ($0.02/1M tokens), strong quality for English technical content | Data sent to OpenAI API |
| Embedding model | Cohere embed-v3 | Competitive quality, multilingual, EU data processing | Slightly higher cost than OpenAI small |
| Embedding model | sentence-transformers (self-hosted) | Free, full data control, runs locally | Infrastructure overhead, slower than managed APIs |

**Key evaluation criteria:** retrieval quality on technical B2B content, data
residency requirements, cost per query at projected volume, operational complexity.

---

#### Frontend Widget

> *Decision owner: Frontend / Full-stack Lead — ADR-004 (pending)*

| Candidate | Strengths | Weaknesses |
| --- | --- | --- |
| Custom JS widget (vanilla) | Minimal footprint, no framework dependency, embeds via script tag, full control over UX | More code to maintain, no pre-built UI components |
| React component (embeddable) | Component ecosystem, easier to build complex UI states, familiar to most frontend devs | Heavier bundle if React is not already on the company site |
| Vercel AI SDK + Next.js | Rapid development, built-in streaming UI, good DX | Tighter coupling to Vercel infrastructure, overkill if site is not Next.js |

**Key evaluation criteria:** bundle size impact on company website load time,
ease of embedding without company site rebuild, streaming response support,
mobile responsiveness.

---

#### Notification and Lead Capture

> *Decision owner: AI Engineering Lead — ADR-005 (pending)*

| Candidate | Strengths | Weaknesses |
| --- | --- | --- |
| Slack webhook | Instant, zero cost, sales team already in Slack | No structured data, hard to query later, not a CRM |
| Email (SMTP / SendGrid) | Universal, structured template possible, easy to route | Slower than Slack, higher chance of being missed |
| Zapier / Make webhook | No-code routing to any destination, easy to change target | External dependency, adds latency, not suitable for < 5 min SLA |
| Native CRM integration (v1) | Structured lead record from day one | Requires CRM selection (OQ-04 unresolved), significant added complexity for MVP |

**Key evaluation criteria:** delivery speed (< 5 min SLA from FR-19), structured
context packet support (FR-13), operational simplicity for MVP, path to CRM
integration in v2.

---

#### Data Storage

> *Constraint: minimal in v1. No CRM. Session logs and captured leads only.*

| Candidate | Strengths | Weaknesses |
| --- | --- | --- |
| PostgreSQL | Reliable, queryable, familiar, can add pgvector for vector store consolidation | Requires a managed instance if not already available |
| SQLite (local / dev only) | Zero setup, good for MVP development | Not suitable for production multi-instance deployment |
| Firebase Firestore | Managed, real-time, easy to set up | NoSQL limitations for analytics queries, Google Cloud dependency |

**Key evaluation criteria:** ability to store structured conversation logs and
qualification state, query capability for post-launch analytics, operational
simplicity, cost at MVP scale.

---

#### Cloud Provider

> *Decision owner: Engineering Lead + Operations — ADR-006 (pending)*

The cloud provider choice affects data residency (GDPR), latency for European
and US visitors, operational complexity for the team, and long-term cost. Three
candidates are under evaluation.

| Candidate | Data residency | AI services | Operational complexity | Best fit scenario |
| --- | --- | --- | --- | --- |
| AWS (eu-west-1 / eu-central-1) | EU regions available | Amazon Bedrock (LLM hosting), SageMaker | High — broadest ecosystem but most configuration overhead | If the company already has AWS infrastructure or anticipates significant scaling |
| Microsoft Azure (westeurope / northeurope) | EU regions, GDPR compliance built-in | Azure OpenAI Service — same GPT-4o / Claude models with EU data residency guaranteed | Medium — more enterprise tooling than Fly.io, less raw complexity than AWS | If GPT-4o is the chosen LLM and GDPR compliance is a hard requirement; native integration between Azure OpenAI and Azure infrastructure eliminates data residency concern |
| Fly.io (EU regions) | EU regions available, data stays in selected region | None native — connects to external LLM APIs | Low — deploy via CLI, minimal DevOps, no infrastructure management | If the team is small, speed of setup is a priority, and the system does not need to integrate with existing enterprise infrastructure |

**Key evaluation criteria:**

- **GDPR / data residency:** Can all components — LLM API, vector store, conversation
  logs, lead data — run within EU boundaries? Azure has the clearest answer if
  Azure OpenAI Service is used. AWS and Fly.io require careful configuration
  to achieve the same guarantee.
- **Operational overhead for MVP:** Fly.io has the lowest setup cost for a small
  team. AWS has the highest. Azure sits in between, particularly if the team
  has existing Microsoft familiarity.
- **LLM integration:** If Azure OpenAI Service is selected as the LLM candidate,
  Azure as the cloud provider creates a natural, low-friction integration.
  If Anthropic or Groq is selected, provider choice is more neutral.
- **Path to v2:** AWS and Azure have broader managed services for CRM integration,
  advanced monitoring, and scaling. Fly.io is a good MVP platform but may require
  migration as the system grows.

**Interaction with LLM candidate decision:** The cloud provider and LLM provider
decisions are partially coupled. See dependency note in ADR-001 and ADR-006.

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
- [ ] No hallucination on company knowledge base content (verified by manual review of 20 test conversations)
- [ ] RAG retrieval verified: relevant questions return above-threshold results; irrelevant questions do not trigger retrieval
- [ ] Prompt layer and RAG layer correctly separated — no domain content in system prompt
- [ ] Response latency p95 < 3 seconds verified under simulated load
- [ ] GDPR data notice displayed on first interaction
- [ ] Graceful degradation tested (AI service down → fallback form)
- [ ] Sales notification received within 5 minutes of hot lead detection (tested end-to-end)

---

## 9. Open Questions

These questions remain unresolved and require input before or during development.

| # | Question | Owner | Needed by |
| --- | --- | --- | --- |
| OQ-01 | Which specific company case studies should be included in the v1 knowledge base? Requires a content audit. | marketing / PM | Before build starts |
| OQ-02 | Who receives the sales notification — a shared inbox, a specific person, a Slack channel? | sales team | Before build starts |
| OQ-03 | What is the current form submission volume and qualification rate? (Baseline for success metric comparison) | sales / analytics | Before launch |
| OQ-04 | Is there an existing CRM? If so, which one? (Informs v2 integration planning) | ops | Before v2 planning |
| OQ-05 | Are there specific topics that must never be discussed — beyond pricing and internal operations? | leadership | Before build starts |
| OQ-06 | Should the chat offer a self-serve calendar booking (e.g. Calendly) for hot leads, or always go through a human to schedule? | sales team | Sprint 1 |

---

## 10. Referenced Documents

| Document | Description |
| --- | --- |
| [problem-statement.md](./problem-statement.md) | Distilled problem statement — authoritative input to this PRD |
| [user-personas](./user-personas/) | Five visitor personas — three target, two negative |
| [chat-behaviour.md](./considerations/chat-behaviour.md) | Conversation model and lead capture principles |
| [qualification-signals.md](./considerations/qualification-signals.md) | Qualification dimensions, scoring model, escalation logic |
| [human-handoff.md](./considerations/human-handoff.md) | Handoff triggers, execution sequences, escalation matrix |

---

*This PRD defines the scope of the company website chat MVP. It is a living document
and will be updated as open questions are resolved and decisions are made during
development. The next documents in the series are the Conversation Design Document
and the Technical Requirements Document.*
