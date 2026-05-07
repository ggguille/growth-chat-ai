---
description: "ADR-003: Decision to use PostgreSQL with the pgvector extension for the vector store and OpenAI text-embedding-3-small for production embeddings — covers alternatives considered (ChromaDB, Pinecone, Cohere), rationale, and constraints on future decisions."
---

# ADR-003 — Use pgvector and OpenAI Embeddings for Knowledge Retrieval

**Status:** `Accepted`
**Date:** May 2026
**Decision owner:** AI Engineering Lead
**Participants:** Engineering Lead, Backend Engineer

---

## Context

The system requires a vector store to support knowledge retrieval (FR-14 to FR-18): company-specific content (case studies, service descriptions, team profiles) is embedded and retrieved per turn via a `retrieve_knowledge` tool call in the main LLM call. The team must choose a vector database and an embedding model before the agent-api build begins, as this decision blocks the RAG layer implementation. EU data residency is a hard constraint — all data at rest must remain within EU infrastructure. Integration with the LangChain/LangGraph ecosystem is required to avoid bespoke retrieval glue code. The deployment model must be operationally simple: a separate managed vector service introduces cost, a new failure domain, and complicates local development.

---

## Decision

**We will use PostgreSQL with the pgvector extension as the vector store, OpenAI `text-embedding-3-small` as the production embedding model, and `sentence-transformers/all-MiniLM-L6-v2` via LangChain's `HuggingFaceEmbeddings` as the development embedding model.**

---

## Alternatives Considered

**Vector store:**

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **pgvector (Chosen)** | PostgreSQL extension adding vector column types and HNSW/IVFFlat indexes | Reuses the Postgres instance already required for session state; LangChain native via `PGVector`; EU deployable on any cloud Postgres offering | — Chosen |
| ChromaDB | Lightweight embedded or standalone vector DB | Simplest local dev setup; LangChain native integration | The engineering review explicitly recommends against building for ChromaDB if pgvector can be planned from the start — the migration cost at production launch outweighs the setup convenience; not production-grade at any meaningful scale |
| Pinecone | Fully managed vector DB with EU region support | High query performance at scale; zero operational overhead | Adds a paid managed service (~$70/month minimum) and a new failure domain; does not reuse existing infrastructure; requires a Pinecone-specific client alongside LangChain |

**Embedding model:**

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **OpenAI text-embedding-3-small (Production)** | Managed API; 1536-dim vectors; $0.02/1M tokens | Very low cost; strong quality on technical B2B content; first-class LangChain support via `OpenAIEmbeddings` | — Chosen for production |
| **sentence-transformers all-MiniLM-L6-v2 (Development)** | Open-source model run in-process via `HuggingFaceEmbeddings`; 384-dim vectors; free | Zero cost; no API key required; runs offline; LangChain native | — Chosen for development |
| Cohere embed-v3 | Managed API with native EU data processing | Multilingual; EU residency without DPA negotiation | Adds a second vendor API alongside Anthropic; LangChain integration is less mature; multilingual capability is not needed for an English-only knowledge base |

---

## Rationale

pgvector reuses the PostgreSQL instance already required for the LangGraph checkpointer state — no additional service, no additional failure domain, and the embedding data stays in the same EU-region database as the rest of the application state. LangChain's `PGVector` store integrates directly into the retrieval chain without bespoke glue code, and pgvector's HNSW index delivers sub-100ms query latency at knowledge-base sizes realistic for this product.

The engineering review explicitly recommends against building against ChromaDB if a migration to pgvector can be planned from the start. Building the ingestion pipeline and retrieval logic targeting pgvector from the first commit means the production environment is the target environment throughout development — there is no migration step and no risk of score distribution drift caused by a vector store switch.

For production, OpenAI `text-embedding-3-small` is the cheapest viable managed embedding API at $0.02/1M tokens — a knowledge base of approximately 200 documents re-ingested weekly costs under $0.01. For development, `sentence-transformers/all-MiniLM-L6-v2` runs entirely in-process via LangChain's `HuggingFaceEmbeddings`, requires no API key, and works offline. The two models produce different vector dimensions (384 vs 1536), so the pgvector column dimension must be environment-specific, configured via `EMBEDDING_DIMENSIONS` alongside the model name. Because dev and prod databases are always separate, there is no runtime dimension mismatch — the mismatch is between environments, not within one. The switch between models is a one-line change to the LangChain embeddings constructor; the rest of the retrieval pipeline is identical.

The GDPR posture for embeddings is materially lower risk than for the LLM API: embedding requests contain knowledge-base chunks (company-authored content), not visitor conversation data. A Data Processing Agreement with OpenAI is still required before real content is embedded in a production environment, but development against synthetic placeholder content can proceed without it.

---

## Consequences

### Positive

- No additional vector service to deploy, monitor, or pay for — pgvector runs as a PostgreSQL extension on the existing database instance
- pgvector data is co-located with session state in the same EU-region database, simplifying the GDPR compliance audit surface
- LangChain `PGVector` + `OpenAIEmbeddings` (production) and `HuggingFaceEmbeddings` (development) are both first-class integrations — no custom retrieval logic required in either environment
- Local development requires no API keys or internet access for embeddings — `sentence-transformers` installs as a pip dependency and runs in-process
- Local development environment matches production on the vector store: `docker compose up` with `pgvector/pgvector:pg16` is sufficient

### Negative / Trade-offs

- PostgreSQL must have the pgvector extension enabled — a one-line setup step (`CREATE EXTENSION vector`), but a deployment prerequisite that must be documented and enforced in infrastructure provisioning
- OpenAI embeddings introduce a second third-party data processor alongside Anthropic — a DPA with OpenAI is required under GDPR Article 28 before real knowledge-base content is embedded in a production environment
- Development retrieval quality differs from production — `all-MiniLM-L6-v2` (384-dim) scores are not comparable to OpenAI (1536-dim); the RAG relevance threshold must be tuned separately per environment and must not be copied from dev to prod
- pgvector's HNSW index may require tuning (`ef_construction`, `m` parameters) and periodic `VACUUM` as the knowledge base grows past approximately 10,000 chunks — not a concern for MVP but must be monitored in production

### Constraints on future decisions

- The pgvector column dimension is environment-specific (384 in development, 1536 in production) and must be driven by environment variables (`EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`) from day one — hardcoding either value breaks the other environment
- The production embedding dimension (1536 for `text-embedding-3-small`) is fixed at schema creation time in the production database — switching the production model requires a full re-ingestion and schema migration
- The RAG relevance threshold must be tuned against the OpenAI embedding score distribution after the real knowledge base is ingested; it must be exposed as a configurable environment variable from day one, not hardcoded
- Any ADR covering cloud deployment must ensure the chosen Postgres service supports the pgvector extension — all major EU-region managed Postgres offerings (AWS RDS on `eu-west-*`, Azure Database for PostgreSQL, Supabase EU) support it

---

## Compliance Notes

- A Data Processing Agreement with OpenAI is required under GDPR Article 28 before real knowledge-base content is embedded via the OpenAI API in a production environment. Development against synthetic placeholder content can proceed without it.
- pgvector data resides entirely within the EU-region PostgreSQL instance — no knowledge-base content leaves EU infrastructure via the vector store itself.

---

## Review Triggers

This decision should be revisited if:

- The knowledge base grows beyond 50,000 chunks and pgvector HNSW query latency consistently exceeds 200ms at p95
- OpenAI embedding API costs exceed $50/month (currently negligible at this knowledge-base size)
- EU data residency compliance is interpreted to require that even knowledge-base content not leave EU infrastructure via third-party APIs — in which case sentence-transformers self-hosted or a Cohere EU-region endpoint must be evaluated
- OpenAI deprecates `text-embedding-3-small`

---

## References

- [Product Requirements Document](../product-requirements/index.md) — FR-14 to FR-18 (RAG requirements)
- [Engineering Review](../product-requirements/engineering-review.md) — EC-01 (RAG triage mechanism), EC-05 (relevance threshold), EC-10 (content audit as parallel workstream)
- [ADR-001 — Use Anthropic Claude Haiku 4.5 as the LLM Provider](./ADR-001-llm-provider.md)
- [ADR-002 — Use LangGraph for Conversation Orchestration](./ADR-002-conversation-orchestrator.md)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
