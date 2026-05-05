---
description: "ADR-002: Decision to use LangGraph as the conversation orchestration framework for the website chat MVP."
---

# ADR-002 — Use LangGraph for Conversation Orchestration

**Status:** Accepted
**Date:** April 2026
**Decision owner:** AI Engineering Lead
**Participants:** AI Engineering Lead, Engineering Lead, Product Manager

---

## Context

The website chat requires a conversation orchestration framework to manage a
multi-turn per-turn pipeline. Each turn follows the same repeating sequence:
evaluate the visitor's message to update a qualification state object, decide
whether to retrieve from the knowledge base, generate a response, and append
a qualifying action. The loop continues until one of several programmatic exit
conditions is met. This structure is cyclic, not linear — the loop back to the
next turn is the normal operating path, not an exception.

The framework must handle two distinct types of logic within the same pipeline:
LLM calls that produce natural language or structured output, and deterministic
programmatic nodes that evaluate conditions against session state (exit checks,
business hours detection, escalation triggers). Both types must share the same
state-passing contract. The framework must also maintain a structured session
state object across every turn, independently of conversation history, because
qualification context cannot be re-derived from raw message history alone.

Without an explicit framework choice, the orchestration layer defaults to an ad
hoc `while` loop with qualification state managed as free variables — an
approach that makes the escalation logic untestable and the conversation
structure invisible.

---

## Decision

**We will use LangGraph as the conversation orchestration framework.**

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **LangGraph — chosen** | Stateful graph execution framework with native support for cyclic graphs, typed state objects, conditional branching, and a swappable persistence backend (checkpointer interface). | Only evaluated framework that models cycles and typed state as first-class citizens. Directly matches the loop structure of the per-turn pipeline. | — Chosen |
| LangChain LCEL | DAG-based pipeline composition framework. Simpler to start, large community, same LangChain ecosystem. | Lower initial setup cost; team familiarity with LangChain. | DAG-only — no native cycle support. The per-turn loop requires a `while` wrapper external to the chain, forcing qualification state and counters into variables outside the framework's control. Technical debt accumulates at the most critical points of the system. |
| Custom state machine | A `while` loop in Python with a typed dict and direct LLM API calls. No framework dependency. | Full control, no external dependency, minimal overhead. | Logging, error handling, node isolation, and state instrumentation must all be built from scratch. For an MVP team, that time has better ROI invested in product behaviour. Produces the same result as LangGraph without the observability or testability benefits. |

---

## Rationale

The core requirement is a cyclic, stateful pipeline — and that is precisely what
LangGraph is designed for. The loop from the exit check back to the next turn is
not an edge case; it is the default path for every turn that does not trigger
escalation. LangGraph models this as a native conditional edge. In LCEL, the same
structure requires a `while` loop external to the chain, which breaks the
composition model and pushes qualification state outside the framework's
awareness. In a custom state machine, the cycle is structurally sound but
produces none of the observability or testability benefits that matter for a
production system.

The pipeline mixes LLM nodes and deterministic programmatic nodes. LangGraph
treats both as first-class nodes with the same state-passing contract — the
distinction is a property of the node's implementation, not a constraint imposed
by the framework. This makes the exit check and escalation trigger natural graph
nodes with explicit inputs, outputs, and test boundaries, rather than conditional
logic embedded inside a generation call or scattered across middleware.

The checkpointer interface is the specific property that makes LangGraph the right
choice given the uncertainty in the project. The persistence backend — in-memory
for development, Redis or Postgres for production — is swapped by changing the
checkpointer configuration, not the graph. The graph definition is stable
regardless of which backend is used. This is not a property of LCEL or a custom
state machine; both would require a custom abstraction layer to achieve the same
result.

The accepted trade-off is framework dependency on LangChain Inc. and a 1–2 day
onboarding cost for engineers unfamiliar with LangGraph's StateGraph and
conditional edge model. Both are judged acceptable at MVP scale.

---

## Consequences

### Positive

- The cyclic pipeline structure maps directly to LangGraph's graph model with no
  structural workarounds.
- Programmatic nodes (exit check, escalation trigger, business hours check) are
  isolated graph nodes with explicit state inputs and outputs — unit-testable
  without an LLM.
- The checkpointer interface decouples the graph from the persistence backend.
  Swapping from `MemorySaver` (development) to Redis or Postgres (production) is
  a single configuration change.
- LangSmith integration provides turn-level observability of node inputs, outputs,
  and state transitions without additional instrumentation.
- In development, `MemorySaver` requires no external infrastructure.

### Negative / Trade-offs

- **LangChain ecosystem dependency.** LangGraph is maintained by LangChain Inc.
  A licensing change or abandonment affects this decision. The custom state
  machine remains a viable migration path.
- **LangGraph version pinning required.** The checkpointer depends on
  `BaseCheckpointSaver`. Breaking changes in minor releases require review.
- **Learning curve.** Engineers unfamiliar with StateGraph and conditional edges
  require 1–2 days of onboarding. Mitigated by defining a standard node template
  at the start of Phase 1.

### Constraints on future decisions

- The cloud provider decision must provide an external
  key-value store compatible with an official LangGraph checkpointer (Redis or
  Postgres). Any other store requires a custom checkpointer implementation.
- The runtime must support stateless invocations — in-memory state between
  invocations must not be assumed.
- The runtime must support token streaming to the client. LangGraph's
  `astream_events` produces the token stream; the deployment environment must
  be able to pipe it to the HTTP response without buffering.

---

## Compliance Notes

- Session state maintained by the checkpointer contains conversation history
  that may include indirect personal data under GDPR Article 4. The KV store
  used by the checkpointer must operate within EU boundaries.

---

## Review Triggers

This decision should be revisited if:

- LangGraph introduces a breaking change to `StateGraph` or
  `BaseCheckpointSaver` that requires significant rework.
- LangChain Inc. changes the licensing terms of LangGraph in a way that
  affects production use.
- The custom state machine option becomes cheaper to maintain than keeping up
  with LangGraph minor releases.

---

## References

- [PRD § 7.1 — Conversation orchestration candidates and evaluation criteria](../../product-requirements/#product-requirements-document-prd-7-technical-constraints-and-candidates-71-stack-candidates-v1-conversation-orchestration)
- [PRD § FR-01, FR-02, FR-07, FR-07a — Qualification state, conversation model, stall detection](../../product-requirements/#product-requirements-document-prd-5-functional-requirements)
- [PRD § NFR 6.3 — PII handling and GDPR compliance](../../product-requirements/#product-requirements-document-prd-6-non-functional-requirements-63-security-and-privacy)
- [Engineering Review § EC-02 — Qualification state persistence backend](../../product-requirements/engineering-review/#engineering-review-ai-powered-lead-qualification-chat-engineering-concerns-ec-02-qualification-state-object-persistence-backend-not-specified-fr-01-gap)
- [Engineering Review § EC-03 — Programmatic escalation trigger mechanism](../../product-requirements/engineering-review/#engineering-review-ai-powered-lead-qualification-chat-engineering-concerns-ec-03-programmatic-escalation-trigger-mechanism-not-specified-fr-09-gap)
- [Engineering Review § EC-13 — Context window strategy](../../product-requirements/engineering-review/#engineering-review-ai-powered-lead-qualification-chat-engineering-concerns-ec-13-missing-conversation-turn-limit-and-context-window-strategy)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
