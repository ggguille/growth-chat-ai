---
description: "Architecture Decision Records for the Growth Chat system — immutable records of significant technical decisions, their context, alternatives considered, and consequences."
---

# Architecture Decision Records

**Project:** AI-powered lead qualification chat
**Last updated:** May 2026

---

## Overview

Architecture Decision Records (ADRs) capture significant technical decisions made during the design and build of the Growth Chat system. Each record is immutable once accepted — if a decision is superseded, a new ADR is created and the original is updated to reference it.

---

## Decision Log

| ID | Title | Status | Date | Owner |
| --- | --- | --- | --- | --- |
| [ADR-001](./ADR-001-llm-provider.md) | Use Anthropic Claude Haiku 4.5 as the LLM Provider | Accepted | April 2026 | AI Engineering Lead |
| [ADR-002](./ADR-002-conversation-orchestrator.md) | Use LangGraph for Conversation Orchestration | Accepted | April 2026 | AI Engineering Lead |
| [ADR-003](./ADR-003-use-pgvector-and-openai-embeddings-for-knowledge-retrieval.md) | Use pgvector and OpenAI Embeddings for Knowledge Retrieval | Accepted | May 2026 | AI Engineering Lead |

---

*ADRs are immutable once accepted. To supersede a decision, create a new ADR and update the Status field of the original to `Superseded by ADR-NNN`.*
