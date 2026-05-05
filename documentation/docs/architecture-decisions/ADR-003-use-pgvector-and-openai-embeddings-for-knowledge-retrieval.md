# ADR-003 — Use pgvector and OpenAI Embeddings for Knowledge Retrieval

**Status:** Proposed
**Date:** 2026-05-05
**Decision owner:** AI Engineering Lead
**Participants:** AI Engineering Lead, Backend Engineer

---

## Context

The chat system includes a retrieval-augmented generation layer to answer questions about the company's services, team, and processes. Company knowledge is stored as embedded text chunks and retrieved at query time when a message requires domain-specific content beyond what the system prompt can provide. Not every message warrants retrieval — injecting retrieved content unconditionally degrades response quality and inflates token costs — so a per-turn retrieval decision is needed. Three decisions are therefore interdependent: the storage backend that holds embedded vectors, the model that produces embeddings at index and query time, and the mechanism that triggers retrieval selectively within the conversation loop.

---

## Decision

**We will use pgvector as the vector storage layer in all environments, sentence-transformers (all-MiniLM-L6-v2) for embedding generation in local development, OpenAI text-embedding-3-small for embedding generation in staging and production, and a dedicated `retrieve_knowledge` tool invoked via the LLM's function-calling API to make per-turn retrieval decisions.**

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **Option A — Chosen: pgvector + OpenAI text-embedding-3-small** | Postgres extension for vector storage; OpenAI API for embedding generation at $0.02/1M tokens | Reuses existing Postgres instance; lowest cost viable API embedding | — Chosen |
| Option B — Chroma + sentence-transformers | Local Python-native vector store; self-hosted embedding model (all-MiniLM-L6-v2) | Zero external API cost; minimal setup for development | Chroma has no production cloud path without a separate managed offering; sentence-transformers require GPU infrastructure for acceptable inference latency; OOM risk at 5M vectors when running in-process alongside the LLM |
| Option C — Pinecone + OpenAI text-embedding-3-small | Fully managed vector SaaS; OpenAI API embeddings | Zero operational surface; strong LangChain integration | Managed-only with no self-hosted option; $50/month minimum for production features; EU data residency not available on standard tiers; introduces a third external vendor |
| Option D — pgvector + sentence-transformers | Postgres extension for storage; self-hosted embedding model (all-MiniLM-L6-v2) | No external embedding API; zero cost; full data control without a DPA | Adopted for local development. Rejected for staging/production: GPU infrastructure required for acceptable per-query latency at production scale; adds an ML serving component not otherwise needed |

---

## Rationale

pgvector is the natural storage choice because Postgres is already in the architecture for session persistence. Adding the pgvector extension introduces no new services to operate, monitor, or pay for separately. Managed Postgres providers (Supabase EU, Neon EU, AWS RDS EU) handle backups, replication, and patching. At the expected knowledge corpus size — company FAQ, blog posts, and case studies — the vector count stays well under 1M, where HNSW index performance is comfortably within acceptable latency bounds. The cold-cache and index-tuning challenges that affect pgvector at scale are real but irrelevant at MVP corpus sizes.

The embedding model is split by environment. In local development, sentence-transformers (all-MiniLM-L6-v2) runs entirely on-device via `pip install sentence-transformers` with no API key, no cost, and no network dependency. CPU inference is slow under load but acceptable for the small corpora and low concurrency typical of a development loop. This keeps the local environment free and self-contained.

In staging and production, OpenAI text-embedding-3-small is used. At $0.02 per million tokens, it is the cheapest viable API option by a wide margin: Cohere embed-v3 costs $0.10/1M (5×). The model achieves competitive MTEB retrieval scores for English-language short-text content, and its 8,191-token context window comfortably handles standard document chunks. Matryoshka training allows dimension reduction to 512 later without re-embedding if storage optimisation is needed. OpenAI text-embedding-3-large was rejected for production because a ~2 MTEB point improvement for 6.5× cost increase is not justified for FAQ-style content. The vector dimensions differ between the two environments (384 for all-MiniLM-L6-v2 vs. 1,536 for text-embedding-3-small), so the local and production corpora are separate — local indexes are not promoted to production.

All three components have first-class LangChain wrappers — `PGVector` for vector storage, `OpenAIEmbeddings` for production embeddings, and `HuggingFaceEmbeddings` for local sentence-transformers — so no custom integration layer is needed and the retriever interface is uniform across environments.

The `retrieve_knowledge` function-calling approach delegates the retrieval decision to the LLM on each turn. This avoids the latency and token cost of unconditional retrieval, and it removes the need for a separate classification model or hand-tuned threshold to decide when to retrieve. The LLM's understanding of the question's intent produces a more contextually accurate retrieval decision than a similarity score threshold alone. A relevance score filter is still applied before injecting retrieved chunks to discard low-quality matches, configured via environment variable to allow production tuning without code changes.

---

## Consequences

### Positive

- Knowledge retrieval runs on the same Postgres instance used for session persistence, adding no new managed services to the production stack
- Local development requires no API key and incurs zero embedding cost — sentence-transformers runs entirely on-device
- Embedding API costs in production are negligible at startup query volumes — 10,000 query embeddings at 100 tokens each cost approximately $0.02 per month
- Relevance threshold is configurable via environment variable, allowing quality tuning without a code deploy
- pgvector supports EU-region hosting through standard Postgres providers, limiting data residency surface to provider choice

### Negative / Trade-offs

- A GDPR Data Processing Addendum with OpenAI must be signed and retained before embedding any user-originated message content; this is a contractual step with lead time
- Local and production corpora use different embedding models (all-MiniLM-L6-v2 at 384 dimensions vs. text-embedding-3-small at 1,536 dimensions), so local vector indexes cannot be promoted to production and must be re-indexed on first deploy
- Switching the production embedding provider in future requires re-embedding the entire corpus, as vectors from different models are not cross-compatible
- pgvector HNSW index performance requires tuning (ef_construction, m, ef_search parameters) as corpus size grows past approximately 1M vectors — manageable with a single engineer at that scale but not automatic
- Cold-cache behaviour after a Postgres failover slows first-queries until HNSW index pages reload into shared memory; production deployments need index pre-warming strategy before full traffic cut

### Constraints on future decisions

- The cloud provider must support a managed Postgres instance with the pgvector extension (all major managed Postgres providers support this as of 2025)
- If EU-only data residency becomes a hard regulatory requirement rather than a DPA obligation, the OpenAI EU API endpoint configuration must be explicitly validated, or the embedding provider must be replaced with a self-hosted alternative

---

## Compliance Notes

- Embedding requests transmit text content (including user messages) to OpenAI's API. A GDPR-compliant Data Processing Addendum (DPA) with OpenAI must be executed under Article 28 before the system handles real user data.
- OpenAI provides a European API endpoint that limits cross-border data transfers. This endpoint should be configured as the default in all environments that process EU user data.

---

## Review Triggers

This decision should be revisited if:

- OpenAI text-embedding-3-small is retired or its pricing increases by more than 5× relative to comparable alternatives on the MTEB leaderboard
- p95 retrieval latency exceeds 500ms consistently in production under normal query load
- The knowledge corpus grows past 10M vectors, at which point pgvector performance characteristics change materially and pgvectorscale or a dedicated vector database should be re-evaluated
- EU-only data residency becomes a hard legal requirement rather than a DPA compliance obligation

---

## References

- MTEB Leaderboard (April 2026 snapshot) — huggingface.co/spaces/mteb/leaderboard
- OpenAI text-embedding-3 pricing — openai.com/pricing
- OpenAI EU data residency announcement — openai.com/index/introducing-data-residency-in-europe
- pgvector GitHub — github.com/pgvector/pgvector
- Supabase pgvector vs Pinecone cost comparison — supabase.com/blog/pgvector-vs-pinecone

---

*ADRs are immutable once accepted. If this decision is superseded,
create a new ADR and update the Status field above to
`Superseded by ADR-NNN`. Do not edit the body of this document.*
