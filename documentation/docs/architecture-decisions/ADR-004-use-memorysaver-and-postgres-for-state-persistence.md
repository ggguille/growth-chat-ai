---
description: "ADR-004: Decision to use LangGraph's built-in MemorySaver for local development and langgraph-checkpoint-postgres backed by the existing PostgreSQL instance for production state persistence — covers alternatives considered (Redis, SQLite, MemorySaver-only), rationale, and constraints on future decisions."
---

# ADR-004 — Use MemorySaver for development and PostgreSQL checkpointer for production state persistence

**Status:** `Accepted`
**Date:** 2026-05-07
**Decision owner:** AI Engineering Lead
**Participants:** AI Engineering Lead

---

## Context

The project uses LangGraph for conversation orchestration (ADR-002). LangGraph persists conversation state through a checkpointer interface, and a concrete backend must be selected. In development, engineers must be able to run the agent locally without standing up external services, so zero-configuration persistence is required. In production, conversation state must survive process restarts, support concurrent users, and scale as the user base grows. ADR-003 already provisions a PostgreSQL instance for pgvector; any persistence choice that avoids introducing a new service reduces operational surface and deployment complexity.

---

## Decision

**We will use LangGraph's built-in `MemorySaver` for local development and `langgraph-checkpoint-postgres` backed by the existing PostgreSQL instance for production state persistence.**

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **MemorySaver (dev) + PostgreSQL (prod)** | Built-in in-memory checkpointer for dev; `langgraph-checkpoint-postgres` for prod | Reuses the Postgres instance from ADR-003; zero dev configuration | — Chosen |
| MemorySaver only | Single in-process backend for all environments | Simplest possible setup; no dependencies in any environment | State is lost on every process restart; not viable in production where durability is required |
| MemorySaver (dev) + Redis (prod) | Redis as the production checkpointer | Redis is purpose-built for ephemeral session state and offers sub-millisecond read latency | Adds a new managed service with no clear gain at current scale; the one-read-one-write-per-turn access pattern does not justify the operational overhead when PostgreSQL is already available |
| SQLite (dev) + PostgreSQL (prod) | File-backed SQLite for dev; PostgreSQL for prod | Preserves dev state across process restarts without requiring a running Postgres | Two different SQL dialects to maintain; dev/prod schema divergence risk; `MemorySaver` is sufficient for iterative development work where session continuity across restarts is not needed |

---

## Rationale

LangGraph's checkpointer abstraction, adopted in ADR-002, is the core enabler of this decision. Because the agent code is coupled to the `BaseCheckpointSaver` interface rather than any specific backend, swapping backends between environments is a single configuration change. This makes it acceptable to use a non-durable backend in development without compromising confidence in the production path.

`MemorySaver` requires zero configuration — no migrations, no connection strings, no running services. It is importable directly from `langgraph` and is the lowest-friction option for a development environment where fast iteration is the priority. The accepted trade-off — state is lost on process restart — is tolerable because development sessions are short and multi-turn continuity across restarts is not needed during feature work.

For production, PostgreSQL is the correct choice given the existing infrastructure. ADR-003 already provisions and manages a PostgreSQL instance; adding the `langgraph-checkpoint-postgres` checkpointer tables is an incremental schema migration, not a new service. Redis would offer faster reads, but the access pattern — one checkpoint read at conversation start, one write at the end of each turn — does not demand sub-millisecond latency. The complexity cost of a second managed service is not justified at current scale.

Both backends implement the same interface, so the production checkpointer does not impose any design constraints on the application layer beyond ensuring the `setup()` migration has been run before first deployment.

---

## Consequences

### Positive

- No new production infrastructure service required; checkpointer tables (`checkpoints`, `checkpoint_writes`) live alongside pgvector tables in the existing Postgres instance, reducing operational surface
- Dev environment starts with zero external dependencies — `MemorySaver` is a pure-Python in-process object
- Because both backends implement `BaseCheckpointSaver`, migrating from PostgreSQL to Redis in the future is a configuration-level change that does not touch application code

### Negative / Trade-offs

- Dev state is lost on every process restart; engineers cannot resume a multi-turn conversation across a server reload during development
- The shared Postgres instance now serves two roles (vector store + conversation state); sustained high-volume write loads from many concurrent long sessions could pressure the instance
- A schema migration (`AsyncPostgresSaver.setup()` or equivalent) must be executed before the production checkpointer is functional; this adds a required step to the initial deployment runbook

### Constraints on future decisions

- Production deployments must run the checkpointer schema migration before the API is started
- If the project adds horizontal API scaling (multiple agent-api replicas), the Postgres checkpointer handles concurrent access safely, unlike `MemorySaver` which is process-local and cannot be shared across replicas

---

## Review Triggers

This decision should be revisited if:

- PostgreSQL write throughput attributable to checkpointing exceeds 20% of total observed DB load in production monitoring
- Per-session latency attributed to checkpointer reads or writes consistently exceeds 100 ms at p95
- The project adopts a managed Redis service for another purpose, making it available at no additional operational cost

---

## References

- [ADR-002 — Use LangGraph for Conversation Orchestration](./ADR-002-conversation-orchestrator.md) (establishes the `BaseCheckpointSaver` interface this ADR depends on)
- [ADR-003 — Use pgvector and OpenAI Embeddings for Knowledge Retrieval](./ADR-003-use-pgvector-and-openai-embeddings-for-knowledge-retrieval.md) (establishes the PostgreSQL instance this ADR reuses)
- [LangGraph Persistence documentation](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [langgraph-checkpoint-postgres package](https://pypi.org/project/langgraph-checkpoint-postgres/)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
