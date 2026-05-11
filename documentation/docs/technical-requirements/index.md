# Technical Requirements Document

## AI-Powered Lead Qualification Chat

**Project:** Zartis — Website Growth Chat
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

This document specifies the technical requirements for the Zartis AI-powered lead qualification chat. It translates the product requirements defined in the PRD into precise technical specifications that the engineering team can implement directly. It resolves the open engineering concerns (EC-01 through EC-13) identified in the Engineering Review, and defines the contracts — schemas, interfaces, logic, and configuration — that govern the system's behaviour.

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

> **[PLACEHOLDER — Section to be completed]**
>
> Esta sección especificará:
>
> - **5.1 Chat endpoint** — POST /chat, request/response schema, autenticación, errores
> - **5.2 Handoff webhook** — contrato de entrega a Slack y CRM, campos, reintentos
> - **5.3 Fallback form endpoint** — ruta independiente del AI backend para captura en degradación (resuelve EC-07)
> - **5.4 Interfaces internas** — contratos entre orquestador, RAG module y handoff subsystem

---

## 6. Infrastructure Requirements

> **[PLACEHOLDER — Section to be completed]**
>
> Esta sección cubrirá:
>
> - Compute: requisitos de instancia para backend y vector store
> - Storage: pgvector sizing, retención de conversaciones (90 días según PRD), backup
> - Networking: TLS 1.3, CORS para el widget embebido
> - **Environment variables completas** — todas las variables de configuración requeridas, incluyendo RAG relevance threshold (resuelve EC-05), sliding window size (resuelve EC-13), y cost limits (resuelve EC-12)

---

## 7. Performance Requirements

> **[PLACEHOLDER — Section to be completed]**
>
> Esta sección definirá:
>
> - Target TTFT p95 < 3s con streaming habilitado (resuelve EC-09 — confirmado en PRD como TTFT, no full response)
> - **Nivel de carga para el load test** — número de sesiones concurrentes sobre las que se mide el p95 (pendiente de definir, requerido por el DoD)
> - Presupuesto de latencia por etapa del pipeline RAG: embedding + vector search + LLM TTFT + network
> - Widget load time < 1s no-blocking

---

## 8. Security Requirements

> **[PLACEHOLDER — Section to be completed]**
>
> Esta sección cubrirá:
>
> - TLS 1.3 en tránsito
> - Scrubbing de PII antes de enviar historial al LLM API
> - Rate limiting por IP y por sesión (resuelve EC-12 — valores concretos)
> - GDPR: data notice en primer turno, política de retención 90 días, estado del DPA con Anthropic (EC-08 — hard blocker para producción)
> - No almacenamiento de PII en logs crudos

---

## 9. Observability

> **[PLACEHOLDER — Section to be completed]**
>
> Esta sección definirá:
>
> - **9.1 Logging** — eventos, niveles, campos y retención
> - **9.2 Metrics** — counters, gauges e histogramas con thresholds de alerta
> - **9.3 Analytics Event Schema** — schema completo a nivel de campo para todos los eventos definidos en el PRD (chat_opened, first_message_sent, qualification_state_change, contact_captured, escalation_triggered, conversation_ended), incluyendo field names, tipos y quién los dispara (frontend vs backend). Requerido antes de implementación para garantizar shapes consistentes.

---

## 10. Resilience and Degradation

> **[PLACEHOLDER — Section to be completed]**
>
> Esta sección cubrirá:
>
> - **10.1 Failure Modes** — tabla de modos de fallo por componente con comportamiento del sistema y recuperación
> - **10.2 Graceful Degradation** — fallback form con ruta de submission independiente del AI backend (resuelve EC-07); comportamiento cuando Slack falla pero CRM tiene éxito y viceversa (partial failure — resuelve FR-19)
> - **10.3 Context Window Management** — estrategia sliding window, tamaño configurable, comportamiento en límite de turno (resuelve EC-13)

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

*Este TRD es la especificación técnica autoritativa del sistema de chat de cualificación de leads de Zartis. Debe mantenerse actualizado a medida que se toman e implementan decisiones. Cualquier cambio que afecte a la arquitectura aquí descrita requiere un ADR correspondiente y un incremento de versión en este documento.*
