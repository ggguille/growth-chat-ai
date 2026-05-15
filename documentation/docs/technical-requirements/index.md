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

> **[PLACEHOLDER — Section to be completed]**
>
> Esta sección listará cada EC del Engineering Review con referencia explícita a la sección del TRD que lo resuelve. Cubrirá EC-01 a EC-13.

---

## 12. Open Questions

> **[PLACEHOLDER — Section to be completed]**
>
> Preguntas abiertas que bloquean secciones específicas del TRD:
>
> - OQ-04: CRM platform por confirmar — bloquea sección 5.2
> - OQ-05: Topic restrictions list por recibir — bloquea especificación del system prompt
> - Nivel de carga para load test (EC-09) — bloquea sección 7

---

## 13. Revision History

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 0.1 | 2026-05-06 | AI Engineering Lead | Initial draft — header and scope |

---

*Este TRD es la especificación técnica autoritativa del sistema de chat de cualificación de leads. Debe mantenerse actualizado a medida que se toman e implementan decisiones. Cualquier cambio que afecte a la arquitectura aquí descrita requiere un ADR correspondiente y un incremento de versión en este documento.*
