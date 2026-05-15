# Technical Requirements Document

## AI-Powered Lead Qualification Chat

**Project:** AI-powered lead qualification chat
**Version:** 0.1
**Status:** `Draft`
**Last updated:** 2026-05-06
**Author:** AI Engineering Lead
**Reviewers:** Engineering Lead, Product Manager

> **Relationship to other documents:**
>
> - This TRD implements the requirements defined in the PRD (AI-Powered Lead Qualification Chat v1.0).
> - Technology decisions referenced here are recorded in ADR-001, ADR-002, and ADR-003.
> - This document does not repeat the rationale for decisions — it specifies the implementation that results from them.
> - Engineering concerns raised in the Engineering Review (April 2026) are explicitly resolved in Section 11.

---

## 1. Purpose and Scope

### 1.1 Purpose

This document specifies the technical requirements for the company AI-powered lead qualification chat. It translates the product requirements defined in the PRD into precise technical specifications that the engineering team can implement directly. It resolves the open engineering concerns (EC-01 through EC-13) identified in the Engineering Review, and defines the contracts — schemas, interfaces, logic, and configuration — that govern the system's behaviour.

This document is the authoritative technical specification. Any change to the architecture described here requires a corresponding ADR and a version increment to this document.

### 1.2 Scope

**In scope:**

- Conversation orchestration graph: session lifecycle, qualification state machine, stage routing, stall detection
- LLM integration: prompt structure, function calling for RAG triage, response validation
- RAG pipeline: retrieval decision mechanism, embedding, vector search, relevance threshold
- Human handoff subsystem: escalation trigger, context packet generation, Slack and CRM delivery, partial failure handling
- Frontend chat widget: embedding, streaming rendering, graceful degradation fallback form
- Business hours detection module
- Analytics event schema and logging contracts
- Performance requirements and load test plan
- Security and GDPR requirements
- Rate limiting, cost controls, and context window strategy

**Out of scope:**

- Knowledge base content production — owned by the content workstream (OQ-01); this TRD specifies the ingestion format and pipeline, not the content itself
- CRM platform implementation details — dependent on OQ-04 (platform TBC); the integration interface is specified here, the CRM-specific configuration is not
- A/B testing infrastructure — not in scope for MVP
- Existing client support routing beyond the no-fit detection path already defined in the PRD

### 1.3 Inputs

| Input document | Description |
| --- | --- |
| [PRD v1.0 — AI-Powered Lead Qualification Chat](../product-requirements/) | Product requirements, functional and non-functional requirements, definition of done |
| [Engineering Review — April 2026](../product-requirements/engineering-review) | 13 engineering concerns assessed against the PRD; several resolved in the PRD update, remainder resolved in this TRD |
| [Architecture Decision Records](../architecture-decisions/) | Decisions that affect system architecture |
| [Chat Behaviour](../considerations/chat-behaviour) | Three-stage conversation model, maturity signals, disqualification paths |
| [Qualification Signals](../considerations/qualification-signals) | Qualification dimensions, programmatic escalation rules |
| [Human Handoff](../considerations/human-handoff) | Context packet schema, handoff routing logic, outside-hours handling |

---

## 2. System Architecture

The system consists of eight components spanning frontend, backend, AI services, storage, and notification channels. Architecture diagrams, component responsibilities, and the happy-path data flow are specified in the dedicated document:

→ [System Architecture](./trd-system-architecture)

---

## 3. Component Specifications

Specifications for the Conversation Orchestrator (graph structure, node definitions, error handling) and the Qualification State Machine (SessionState schema, transition rules, session lifecycle, persistence backend) are in the dedicated document:

→ [Component Specifications](./trd-component-specifications)

---

## 4. Data Models

Canonical schemas for all data structures used by the system — `SessionState`,
`QualificationState`, `ContextPacket`, `HandoffRecord`, `Message`, and `KnowledgeChunk` —
together with PII classification, retention rules, and database DDL. This is the single
authoritative schema reference; component specifications in Section 3 reference this section
rather than repeating inline definitions.

→ [Data Models](./trd-data-model)

---

## 5. API Specifications

Chat endpoint contract (POST /chat, SSE streaming, authentication, error codes),
Handoff delivery interfaces (Slack Block Kit payload, CRM abstract interface, email fallback),
Fallback form resolution (EC-07), and internal component contracts
(`retrieve_knowledge`, `dispatch_handoff`, `is_business_hours`, `emit_event`).

→ [API Specifications](./trd-api-specification)

---

## 6. Infrastructure Requirements

Compute sizing for the Chat API and Backup Cron machines (Fly.io), storage
configuration and backup strategy for Neon Postgres and pgvector, TLS and CORS
networking requirements, and the consolidated environment variable reference —
all variables consumed by the system grouped by component, with required/optional
status, defaults, and the engineering concerns they resolve (EC-05, EC-12, EC-13).

→ [Infrastructure Requirements](./trd-infrastructure-requirements)

---

## 7. Performance Requirements

TTFT and retrieval latency targets (p95), per-stage latency budget validating the 3s end-to-end target,
widget load time and bundle size constraints, and a stress test plan dimensioned against observed site
traffic — including the 10-concurrent-session target and success criteria (resolves EC-09).

→ [Performance Requirements](./trd-performance-requirements)

---

## 8. Security Requirements

Transport security (TLS 1.3, HSTS, AES-256 at rest), widget-to-API authentication via static key,
PII scrubbing rules before Anthropic API calls, rate limiting per IP and per session (resolves EC-12),
GDPR compliance (data notice, 90-day retention, Anthropic DPA — resolves EC-08), and secret management
via Fly.io secrets.

→ [Security Requirements](./trd-security-requirements)

---

## 9. Observability

Structured JSON logging emitted to `stdout` and shipped to Better Stack (Logtail) — mandatory field schema, 15-event table with levels and component assignments, and PII/log-safety rules. Metrics implemented as named Better Stack log queries with per-metric alert thresholds, uptime monitors for the Chat API health endpoint and the backup cron heartbeat, and a monthly LLM cost alert. Full analytics event schema: 8 frontend `CustomEvent`s dispatched on `<growth-chat>` (with `detail` fields) and 8 backend events emitted to Langfuse via `emit_event` (with field-level types) — including a frontend/backend mapping table for events that have representations at both layers.

→ [Observability](./trd-observability)

---

## 10. Resilience and Degradation

A consolidated failure mode table spanning all system components — Chat API, Conversation Orchestrator, LLM, RAG, PostgreSQL Checkpointer, Human Handoff Subsystem, Chat Widget, and State Machine — with system behaviour, user-facing impact, and recovery path for each. Graceful degradation specifications: the fallback form path (zero dependency on the AI backend, resolves EC-07), handoff partial failure (one channel down — fallback email dispatched, resolves FR-19), handoff total failure and SMTP failure recovery, LLM failure mid-conversation routing to handoff capture, and RAG bypass behaviour. Sliding-window context window management: eviction strategy, what survives eviction (always-fresh `QualificationState`), `CONTEXT_WINDOW_TURNS` configuration, per-turn token budget table, and v1 limitations — resolves EC-13.

→ [Resilience & Degradation](./trd-resilience-degradataion)

---

## 11. Engineering Concerns Resolution

This section maps each of the 13 engineering concerns from the Engineering Review (April 2026) to the TRD section that resolves it. Concerns resolved in the PRD are confirmed here with a reference to the resulting implementation. Concerns that required no TRD implementation section are marked accordingly.

| EC | Title | Resolved in | Resolution |
| --- | --- | --- | --- |
| EC-01 | RAG triage mechanism not specified | §3 — Component Specifications (RAG Triage Module) | Resolved via tool-use on the main LLM call (Option C from the Engineering Review analysis). The `generate_response` node exposes `retrieve_knowledge` as a tool to Claude Haiku 4.5 on every turn. The LLM decides when to invoke it; the RAG Triage Module executes only when called. No separate classifier. No keyword matching. |
| EC-02 | Qualification state object persistence backend not specified | §3 — Component Specifications (Qualification State Machine); §4 — Data Models; ADR-004 | Resolved in ADR-004: `MemorySaver` for local development; `langgraph-checkpoint-postgres` on Neon Postgres for production. `SessionState` is persisted on every turn via the `BaseCheckpointSaver` interface. Survives process restarts. EU data residency satisfied by Neon EU region. |
| EC-03 | Programmatic escalation trigger mechanism not specified | §3 — Component Specifications (Conversation Orchestrator — `score_router` node) | The `score_router` node evaluates `QualificationState` after every `update_state`. When the hot-lead threshold is met (Problem + Authority + one additional dimension confirmed), the graph routes to `propose_handoff` without LLM participation. The LLM receives the escalation as an instruction to generate the proposal — it does not decide to escalate. |
| EC-04 | Business hours detection edge cases (DST, public holidays) | §3 — Component Specifications (Business Hours Detection Module) | Python `zoneinfo` (stdlib 3.9+) with IANA identifier `Europe/Madrid` handles DST automatically — no hardcoded UTC offset. No public holiday awareness in v1; documented as a known limitation. Configurable holiday calendar is a v2 item. |
| EC-05 | Relevance threshold undefined — must be configurable | §3 — Component Specifications (RAG Triage Module); §6 — Infrastructure Requirements (env vars) | Resolved in the PRD (FR-17 updated) and specified here: `RAG_RELEVANCE_THRESHOLD` is a required environment variable with no hardcoded default. Provisional value 0.70 for Phase 1–2 development only. Final value determined during Phase 4 RAG tuning once the production knowledge base is available. |
| EC-06 | "Qualification progress" not precisely defined for stall detection | §3 — Component Specifications (Conversation Orchestrator — stall detection) | Resolved in the PRD (FR-07 updated) and implemented here: stall is defined as 6+ turns without `score_router` triggering a `propose_handoff`. The `stall_turn_counter` resets when a Stage 3 proposal is issued. Configurable via `STALL_TURN_THRESHOLD` (default: `6`). |
| EC-07 | Graceful degradation form submission destination not specified | §5 — API Specifications (Fallback Form); §10 — Resilience and Degradation (AI Backend Unavailable) | Resolved by design: there is no fallback form endpoint in this system. When the AI backend is unavailable, the widget activates a permanent fallback state displaying a link to the `fallback-url` HTML attribute, which points to the existing company contact form or any external URL. The submission path has zero dependency on the AI backend. |
| EC-08 | GDPR DPA with LLM provider required | §8 — Security Requirements (GDPR Compliance) | DPA required with all five data processors: Anthropic (LLM), OpenAI (embeddings), Fly.io (compute), Neon (storage), Cloudflare (edge/CDN). Sign-off on all five DPAs is a go/no-go condition for production traffic with real visitor data. Engineering may proceed against synthetic test data before DPAs are in place. |
| EC-09 | Performance target ambiguity: TTFT vs. full response | §7 — Performance Requirements | Resolved in the PRD (DoD updated) and specified in §7: the target is p95 TTFT < 3s, measured from API request sent to first token received at the client. Streaming is enabled from day one. Full-response latency is not the target metric. |
| EC-10 | Content audit (OQ-01) must run as parallel workstream, not prerequisite | Resolved in PRD — no TRD implementation section | Resolved entirely in the PRD: OQ-01 is a parallel workstream with a two-week hard deadline from kickoff. Engineering builds the ingestion pipeline and RAG architecture against a synthetic placeholder knowledge base. Real content replaces the placeholder when delivered. Does not block engineering start. |
| EC-11 | DoD hallucination test count (20) insufficient | Resolved in PRD — no TRD implementation section | Resolved in the PRD: the DoD now requires 70–80 structured test conversations covering all target personas plus adversarial cases. Belongs to QA planning; no TRD implementation section required. |
| EC-12 | Missing: API rate limiting, cost controls, abuse prevention | §8 — Security Requirements (Rate Limiting and Cost Controls) | Per-IP rate limiting via Cloudflare Rules (30 req / 10 min — challenge; 60 req / 10 min — block). Per-session rate limiting via `slowapi` (20 messages / 5 min). Per-session token budget via `MAX_TOKENS_PER_SESSION`. Monthly cost alerting via `MONTHLY_COST_CAP_USD`. |
| EC-13 | Missing: conversation turn limit and context window strategy | §3 — Component Specifications (Orchestrator config — `CONTEXT_WINDOW_TURNS`); §10 — Resilience and Degradation (Context Window Management) | Sliding window, configurable via `CONTEXT_WINDOW_TURNS` (default: `10` exchanges). `QualificationState` is always injected in full regardless of window position, preserving qualification context across eviction. Only raw conversation history is subject to eviction. |

---

## 12. Open Questions

The following questions remain unresolved. Each blocks a specific TRD section or build phase and requires an owner decision before the dependent work can begin.

| # | Question | Owner | Blocks | Needed by |
| --- | --- | --- | --- | --- |
| OQ-04 | Is there an existing CRM in use, and if so which platform? CRM integration is a Must requirement for v1 (M10). Without a confirmed platform it is not possible to define the CRM adapter, the lead record schema, or the abstract interface extension in §5.2. | ops / commercial | §5.2 — CRM Interface; Phase 3 build (Weeks 5–6) | Before build start (Week 0) |
| OQ-05 | Are there specific topics that the system must never discuss, beyond pricing and internal operations? This list determines the topic restriction rules in the system prompt. Without it the prompt cannot be finalised and the Phase 5 QA test suite cannot be completed. | leadership | System prompt (Phase 2); QA test suite (Phase 5) | Before Phase 2 start |
| OQ-06 | What is the production `fallback-url` value? The chat widget requires this attribute in the embed tag. If absent, the widget enters a degraded fallback state without a link to the contact form — functional but suboptimal. | PM / web ops | Chat Widget embed (Phase 1 frontend) | Before widget deploy to staging |

---

## 13. Revision History

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 0.1 | 2026-05-06 | AI Engineering Lead | Initial draft — header and scope |
| 0.2 | 2026-05-15 | AI Engineering Lead | Completed all sections |

---

*This TRD is the authoritative technical specification for the company lead qualification chat system. It must be kept up to date as decisions are made and implemented. Any change that affects the architecture described here requires a corresponding ADR and a version increment to this document.*
