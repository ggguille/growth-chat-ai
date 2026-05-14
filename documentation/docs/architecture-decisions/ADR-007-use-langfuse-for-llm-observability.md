---
description: "ADR-007: Decision to use Langfuse Cloud (EU) as the LLM observability platform for the website chat MVP — covers LangGraph trace capture, analytics pipeline, EU data residency, and alternatives considered."
---

# ADR-007 — Use Langfuse Cloud as the LLM Observability Platform

**Status:** Accepted
**Date:** 2026-05-14
**Decision owner:** AI Engineering Lead
**Participants:** AI Engineering Lead, Engineering Lead

---

## Context

The website chat system is built on a LangGraph orchestration graph (ADR-002)
that executes a multi-node pipeline per visitor turn: qualification signal
extraction, RAG triage, response generation, state persistence, and analytics
event emission. Diagnosing production issues — incorrect qualification scores,
unexpected escalations, RAG misses, prompt compliance violations — requires
visibility into what each node received, what it produced, and what the LLM
was actually sent at the moment of failure.

Standard application logging captures system-level errors but not LLM-specific
observability: token usage per turn, latency per node, prompt inputs and
outputs, tool call decisions, and retrieval outcomes. Without this layer, the
only available signal when the qualification logic misbehaves is the final
visitor-facing response — tracing the root cause back to a specific node state
or prompt instruction requires manual log correlation across multiple components.

The system also requires an evaluation dataset for Phase 4 RAG threshold tuning
and the 70–80 structured test conversations defined in the PRD Definition of Done.
An LLM observability platform that doubles as an evaluation dataset store
eliminates a separate tooling layer for the testing workstream.

The observability platform will receive conversation data, including visitor
messages, which may constitute personal data under GDPR Article 4. EU data
residency is therefore a hard requirement, consistent with the constraint applied
to every component in this stack (ADR-001, ADR-003, ADR-006).

**Scope note.** This ADR covers LLM-layer observability only — traces, prompt
inputs/outputs, token usage, node latency, and RAG retrieval outcomes. Application-
level logging (system errors, infrastructure failures, `checkpointer_write_failure`,
rate limit hits) is a separate concern not addressed by LLM observability platforms.
That layer requires a dedicated decision and is out of scope here.

---

## Decision

**We will use Langfuse Cloud (EU region) as the LLM observability platform
for the website chat MVP.**

Langfuse will serve three roles:

1. **LLM tracing** — per-turn trace capture of all LangGraph node inputs,
   outputs, LLM calls, tool invocations, and token usage, via the Langfuse
   Python SDK with LangGraph callback integration.
2. **Analytics pipeline destination** — the `emit_event` interface (TRD
   Section 5) will write backend analytics events to Langfuse as structured
   trace metadata, replacing a custom analytics pipeline for MVP.
3. **Evaluation dataset** — production traces are promoted to the Langfuse
   dataset store for Phase 4 RAG tuning and the structured test conversation
   suite.

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **Langfuse Cloud (EU) — Chosen** | Open-source LLM observability platform. Cloud offering with EU region. Free tier: 50k observations/month, no seat-based pricing. Python SDK with LangGraph callback integration. Evaluation datasets and LLM-as-judge scoring included. | EU data residency on free tier. Open-source reduces vendor lock-in. Free tier 10× more generous than LangSmith. Evaluation tooling directly addresses Phase 4 requirements. | — Chosen |
| LangSmith (EU) | LangChain Inc.'s hosted observability platform. EU data residency available on all tiers including free, hosted on Google Cloud EU. Zero-config integration with LangGraph via two environment variables. | Native zero-config integration with LangGraph — deepest available. EU data residency confirmed on all plans since July 2024. Already referenced in ADR-002 as a positive consequence of choosing LangGraph. | Free tier limited to 5,000 traces/month with 14-day retention — 10× less than Langfuse (50k observations). Per-seat pricing on paid plans ($39/seat/month) compounds with team growth; Langfuse charges a flat rate with no per-seat model. Adds a second dependency on LangChain Inc., which already owns LangGraph (ADR-002) — concentrating vendor risk in one company for both orchestration and observability. LangSmith is the better option if Langfuse's LangGraph integration proves difficult to maintain — documented as a Review Trigger. |
| Langfuse self-hosted on Fly.io | Langfuse deployed as an additional Fly Machine, with traces stored in a dedicated ClickHouse container or the existing Neon instance. | EU data residency guaranteed. Zero third-party data sharing. | Operational overhead not justified when Langfuse Cloud EU achieves identical data residency with zero infrastructure to maintain. Self-hosted is correct only if data cannot leave company infrastructure — that constraint does not apply here. Retained as a migration path if Langfuse Cloud EU changes its data residency terms. |

---

## Rationale

The decision is primarily driven by three factors: free tier capacity, vendor
concentration risk, and pricing model at scale.

**Free tier capacity.** Langfuse's free tier covers 50,000 observations per month —
ten times LangSmith's 5,000 traces. At MVP conversation volumes (≤ 10 concurrent
sessions, estimated <500 conversations/day), Langfuse's free tier provides sufficient
headroom for the entire 90-day validation period at zero cost. LangSmith's free tier
would likely be exhausted within the first weeks of production traffic, forcing an
upgrade to the Plus plan ($39/seat/month) before the MVP hypothesis is validated.

**Vendor concentration.** LangSmith is maintained by LangChain Inc., the same
organisation that maintains LangGraph (ADR-002). Choosing LangSmith would make
LangChain Inc. responsible for both the conversation orchestration framework and
the observability layer — two critical components. A pricing change, acquisition,
or service disruption would affect both layers simultaneously. Langfuse is an
independent open-source project (MIT licence), reducing single-vendor exposure
at a layer where the switching cost is lower than at the orchestration layer.

**Pricing model at scale.** LangSmith's Plus plan charges per seat plus per-trace
overage. A two-engineer team accessing traces costs $78/month before any trace
overage. Langfuse's paid tier charges a flat monthly rate with no per-seat model,
making it cheaper for any realistic team size during the post-MVP phase. The
difference is not material at MVP scale, but per-seat pricing creates pressure to
restrict dashboard access — counterproductive for an observability tool.

**Integration trade-off.** LangSmith's zero-config LangGraph integration is a
material advantage: two environment variables, no code changes. Langfuse requires
explicit SDK initialisation and a callback handler — estimated at 0.5–1 day. This
is the primary trade-off accepted here and is documented explicitly as a Review
Trigger: if Langfuse's integration creates ongoing maintenance friction, LangSmith
should be re-evaluated.

---

## Consequences

### Positive

- EU data residency maintained across all components, consistent with ADR-001,
  ADR-003, and ADR-006.
- Free tier (50k observations/month) sufficient for the full 90-day MVP
  validation period — zero additional cost during hypothesis validation.
- Per-turn LLM observability: node inputs/outputs, prompt content, token usage,
  tool call decisions, and RAG retrieval outcomes visible without additional
  per-node instrumentation.
- Phase 4 evaluation dataset requirement addressed within the same platform.
- `emit_event` interface decouples the graph from the analytics destination.
  Langfuse is the MVP implementation; the interface is the stable contract.
- Open-source core (MIT licence) — self-hosted deployment is a viable migration
  path with no code changes if cloud terms change.
- No per-seat pricing — dashboard access is not a cost centre.

### Negative / Trade-offs

- **SDK integration required.** Langfuse requires explicit SDK initialisation
  and a LangGraph callback handler. Estimated setup cost: 0.5–1 day. This is
  the primary cost of choosing Langfuse over LangSmith.
- **Third-party data processor.** Visitor messages and qualification signals
  flow through Langfuse Cloud EU. A Data Processing Addendum must be executed
  before processing real visitor data in production — consistent with the DPA
  pattern across all ADRs.
- **`emit_event` single destination.** For MVP, backend analytics events go to
  Langfuse only. Post-MVP BI integration requires extending the `emit_event`
  interface, not replacing it.

### Constraints on future decisions

- The `emit_event` interface (TRD Section 5) must treat Langfuse as a replaceable
  implementation. The event schema in TRD Section 9 is the contract.
- Langfuse SDK initialisation must degrade gracefully if env vars are absent —
  missing observability must never prevent the chat from functioning.
- PII scrubbing (TRD Section 8) applies before data is written to Langfuse, not
  only before Anthropic API calls. Visitor email addresses and names must not
  appear in raw trace content.
- A dedicated `evaluation` dataset must be created in Langfuse before Phase 4
  begins. Production traces are promoted to it, not moved.
- Application-level logging is out of scope for this decision and requires a
  separate ADR.

---

## Compliance Notes

- Langfuse Cloud EU processes trace data in the EU region, satisfying GDPR
  Article 44 transfer restrictions applied consistently across this stack.
- A Data Processing Addendum (DPA) with Langfuse must be reviewed and signed
  before production traces contain real visitor data.
  Langfuse DPA: langfuse.com/docs/data-security/gdpr.
- PII scrubbing (TRD Section 8) must be applied before trace data is written
  to Langfuse. The same fields scrubbed before Anthropic API calls apply here.

---

## Review Triggers

This decision should be revisited if:

- Langfuse Cloud EU changes its data residency guarantees or DPA terms.
- The Langfuse LangGraph callback integration creates ongoing maintenance friction
  or falls behind LangGraph version updates — at that point LangSmith should be
  re-evaluated, as its zero-config integration removes that maintenance burden.
- Monthly observation volume consistently exceeds the free tier (50k/month) and
  Langfuse's paid tier cost is not justified relative to self-hosted.
- Post-MVP BI integration requires a dedicated analytics pipeline — extend
  `emit_event` rather than replace Langfuse.

---

## References

- [ADR-001 — Use Anthropic Claude Haiku 4.5 as the LLM Provider](./ADR-001-llm-provider.md) — EU data residency constraint and DPA pattern
- [ADR-002 — Use LangGraph for Conversation Orchestration](./ADR-002-conversation-orchestrator.md) — LangSmith mentioned as a positive consequence; this ADR formalises the platform decision
- [ADR-003 — Use pgvector and OpenAI Embeddings for Knowledge Retrieval](./ADR-003-use-pgvector-and-openai-embeddings-for-knowledge-retrieval.md) — EU data residency constraint
- [ADR-006 — Use Fly.io, Neon, and Cloudflare](./ADR-006-use-flyio-neon-cloudflare.md) — EU data residency and DPA pattern
- [TRD Section 5 — `emit_event` interface](../technical-requirements/index.md#technical-requirements-document-5-api-specifications)
- [TRD Section 9 — Analytics Event Schema](../technical-requirements/index.md#technical-requirements-document-9-observability)
- [PRD § 6.4 — Observability requirements](../product-requirements-document.md#product-requirements-document-prd-6-non-functional-requirements-64-observability)
- [PRD — Definition of Done](../product-requirements-document/#product-requirements-document-prd-8-definition-of-done)
- [Langfuse data regions](https://langfuse.com/security/data-regions)
- [Langfuse LangGraph integration](https://langfuse.com/docs/integrations/langchain/tracing)
- [Langfuse pricing](https://langfuse.com/pricing)
- [LangSmith EU data residency](https://changelog.langchain.com/announcements/eu-data-residency-for-langsmith)
- [LangSmith pricing](https://www.langchain.com/pricing)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
