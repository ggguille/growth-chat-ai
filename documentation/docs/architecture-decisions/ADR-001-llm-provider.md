---
description: "ADR-001: Decision to use Anthropic Claude Haiku 4.5 via the direct API as the sole production LLM for the website chat MVP — covers alternatives considered, rationale, fallback behaviour, and constraints on future decisions."
---

# ADR-001 — Use Anthropic Claude Haiku 4.5 as the LLM Provider

**Status:** Accepted
**Date:** April 2026
**Decision owner:** AI Engineering Lead
**Participants:** AI Engineering Lead, Product Manager, Engineering Lead

---

## Context

The website chat system requires a large language model to power three
distinct capabilities: generating conversational responses that maintain the
company representative persona, extracting qualification signals from natural
language across a multi-turn conversation, and deciding per turn whether to
retrieve from the RAG knowledge base via function calling (EC-01).

The system prompt is non-trivial — it encodes a three-stage conversation model,
per-persona tone adaptation, qualification logic, prohibited behaviours, and
handoff instructions. Reliable instruction following under this level of prompt
complexity is the primary technical requirement for the LLM.

The project is an MVP with the explicit goal of validating a hypothesis with
minimum cost and complexity. No model routing layer is planned for v1. The
selected model must perform acceptably across the full range of conversation
scenarios without requiring a secondary model for escalation or cost optimisation.

A local model (Llama 4 8B via Ollama) will be used exclusively for development
and offline testing. It is not part of the production stack and is not evaluated
as a production candidate here.

---

## Decision

**We will use Anthropic Claude Haiku 4.5 via the Anthropic API directly as the
sole production LLM for the website chat MVP.**

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **Claude Haiku 4.5 — Anthropic API** | Anthropic's lowest-cost production model. Strong instruction following, function calling support, 200K context window. $0.25/$1.25 per 1M input/output tokens. | Flagship low-cost model from the most instruction-following-reliable provider. Direct API eliminates intermediary complexity. | — **Chosen** |
| Claude Haiku 4.5 — Amazon Bedrock | Same model accessed via AWS Bedrock managed service. Identical per-token pricing. EU data residency available in eu-west-1. | Bedrock's multi-model API would allow future model switching without reintegration. | Only justified when using multiple model providers under one API. With a single Claude model, Bedrock adds operational complexity with no pricing benefit. New Claude features reach the direct API weeks before Bedrock. |
| Claude Sonnet 4.6 — Anthropic API | Anthropic's mid-tier model. Stronger reasoning than Haiku, better performance on complex multi-step tasks. $3.00/$15.00 per 1M input/output tokens. | Higher reasoning capability for edge cases in qualification logic and persona tone adaptation. | 12x cost increase over Haiku not justified for MVP. The conversation use case — lead qualification chat — does not require frontier reasoning. Cost optimisation is an explicit goal. Sonnet remains available as a manual upgrade path if Haiku proves insufficient in production. |
| Llama 4 Scout — Amazon Bedrock | Meta's open-weight model, ~$0.10/$0.30 per 1M tokens. Strong general capability, 130K context window. | Significantly cheaper than Claude. Open weights reduce vendor dependency. | Instruction following reliability on complex system prompts is less documented than Claude for production chat use cases. Function calling maturity for the RAG triage mechanism (EC-01) is a risk in v1. Adds Bedrock dependency for a single model with no other Bedrock models planned. |
| GPT-4o-mini — OpenAI API | OpenAI's low-cost model. Strong instruction following, wide ecosystem. $0.15/$0.60 per 1M tokens. | Competitive pricing and strong community documentation. | Weaker instruction following than Claude Haiku on complex system prompts in internal evaluations. GDPR data residency requires Azure OpenAI configuration, adding complexity. No existing relationship with OpenAI in the project stack. |

---

## Rationale

The decision tree applied to this use case resolves as follows:

```text
Is latency critical (< 500ms)?
└─ No — PRD requires TTFT < 3s. 500ms is not a constraint.

Is cost critical?
└─ No — Cost is a preference, not a hard constraint. Response quality
         for a B2B sales chat has higher weight than marginal cost savings.

Need long context (> 32K tokens)?
└─ No — A qualification conversation with system prompt, RAG context,
         and history fits comfortably within 8–12K tokens.

Need multimodal?
└─ No — Text only. Explicitly out of scope in PRD (W3).

Result: Any flagship model.
Tiebreaker: Minimum cost among flagships with reliable instruction following.
```

Claude Haiku 4.5 wins the tiebreaker on three grounds.

**Instruction following reliability.** The system prompt for this project is
structurally complex — it encodes staged conversation logic, persona detection,
qualification scoring, prohibited behaviours, and RAG triage instructions.
Claude models have the strongest documented track record of maintaining character
and following multi-constraint system prompts in production conversational systems.
This is the highest-risk technical requirement of the project.

**Function calling for RAG triage.** EC-01 requires a per-turn decision mechanism
for selective RAG retrieval. The recommended implementation (engineering review,
EC-01) is tool use via the main LLM call — the model calls a `retrieve_knowledge`
tool when a question requires domain content. Claude Haiku 4.5 has production-grade
function calling support. This avoids the latency and cost of a separate classifier
call (Option A in EC-01 analysis) and is more robust than keyword matching
(Option B).

**Direct API simplicity.** Since only Claude models are used in production,
a cloud provider managed service provides no multi-model benefit. The Anthropic
SDK is simpler to integrate, Claude features (prompt caching, new model versions)
reach the direct API before managed services, and there is no additional managed
service to configure or monitor.

The cost difference between Haiku ($0.25/$1.25) and the next cheapest viable
alternative (GPT-4o-mini at $0.15/$0.60) is marginal at MVP conversation volumes.
Instruction following quality is the dominant selection criterion, not per-token
price.

---

## Consequences

### Positive

- Single model, single provider, single SDK — minimal integration surface for MVP.
- Claude Haiku 4.5 function calling support enables the EC-01 RAG triage
  mechanism via tool use without a secondary classifier model.
- Direct Anthropic API gives immediate access to new features (prompt caching,
  model updates) without waiting for Bedrock propagation lag.
- Manual upgrade path to Claude Sonnet 4.6 is a one-line config change if
  Haiku proves insufficient in production — no reintegration required.
- No managed service dependency means cloud provider choice (ADR-006) is fully
  decoupled from LLM choice. Any cloud provider is equally viable.

### Negative / Trade-offs

- No model routing in v1. If a conversation requires deeper reasoning than
  Haiku can provide (e.g. a P1 CTO asking highly technical architecture questions),
  the chat cannot escalate to a more capable model automatically. This is a
  known limitation accepted for MVP scope.
- Vendor dependency on Anthropic for production availability. Mitigated by the
  degraded fallback flow defined below and the 99.5% uptime SLA in the PRD.

### Fallback Behaviour on Anthropic API Failure

When the Anthropic API is unavailable or returns an unrecoverable error, the
system does not attempt to maintain the full conversational experience with an
alternative model. Instead it redirects the visitor to the existing contact
form — which operates fully independently of the AI backend and
satisfies EC-07 without requiring any additional infrastructure.

**Trigger conditions:**

- Anthropic API returns 5xx error or connection timeout after 1 retry
- API response latency exceeds 10 seconds (hard timeout)

**Fallback sequence:**

1. The chat displays a transparent message to the visitor before redirecting:
   > *"I'm having a technical issue and can't continue our conversation right now.
   > You can reach us directly through our contact form — the team will get
   > back to you shortly."*

2. The widget surfaces a direct link to the existing contact form.
   The visitor completes the form through the standard submission path —
   no new endpoint, no new infrastructure required.

3. If the failure occurs mid-conversation and the visitor has already provided
   their email, the system attempts to send a fallback notification to the
   sales team flagged with `trigger: system_fallback` and whatever conversation
   context was collected before the failure. This is best-effort — if the
   backend is down, the notification may not be delivered.

**Why the existing contact form, not an inline fallback form:**
The company website already has a working contact form with its own independent
submission path. Redirecting to it solves EC-07 (graceful degradation form
must be independent of the AI backend) without building or maintaining a
second capture mechanism. It is the simplest solution that meets the requirement.

**Why not a secondary LLM model:**
Three alternatives were evaluated — a secondary cloud model (GPT-4o-mini),
a local model (Llama 4 8B via Ollama), and the degraded redirect flow above.
For an MVP where Anthropic's API uptime is 99.9%+, the incremental value of
maintaining a full conversational fallback does not justify the added complexity
of a second model integration, a second DPA, or a local model deployment
requirement. Model fallback is deferred to v2 if production data shows API
unavailability is a meaningful problem.

### Constraints on future decisions

- **ADR-003 (RAG architecture):** Must design the RAG triage mechanism around
  Claude Haiku 4.5's function calling API — specifically the `tools` parameter
  in the Anthropic Messages API. The `retrieve_knowledge` tool definition must
  be validated against Haiku's tool use behaviour during Phase 2 development.
  If Haiku shows unreliable tool use in testing, ADR-003 must consider a
  rule-based fallback triage mechanism.
- **ADR-006 (Cloud provider):** This decision is now fully decoupled from the
  LLM choice. The Anthropic API is provider-agnostic — Claude Haiku 4.5 works
  identically regardless of the cloud provider chosen. ADR-006 should be
  evaluated purely on infrastructure criteria.
- **v2 model strategy:** If conversation volume grows significantly and cost
  becomes a meaningful constraint, the v2 options are: (a) upgrade to prompt
  caching for the static system prompt sections, reducing effective input token
  cost by ~80% on cached content, or (b) evaluate Llama 4 Scout as a cheaper
  alternative once its instruction following on complex system prompts is better
  documented in production use cases.

---

## Compliance Notes

- The Anthropic API processes conversation data on Anthropic's infrastructure.
  A Data Processing Agreement (DPA) with Anthropic is required before processing
  real visitor data in production (EC-08 in the engineering review).
- Anthropic offers EU data processing for enterprise customers. DPA status must
  be confirmed before production launch — this is a hard blocker per EC-08.
- Conversation history sent to the API must be scrubbed of PII fields before
  transmission, as specified in PRD NFR 6.3.

---

## Review Triggers

This decision should be revisited if:

- Anthropic API availability falls below the 99.5% uptime requirement in
  the PRD over any 30-day period.
- Claude Haiku 4.5 shows consistent instruction following failures on the
  qualification logic or persona tone adaptation in production (defined as
  failure rate > 5% on the structured test suite from the PRD DoD).
- Monthly LLM API cost exceeds $500 USD — at that point, prompt caching
  or model routing should be evaluated.
- Anthropic changes its EU data processing terms or DPA availability.

---

## References

- [PRD Section 7.1 — LLM Provider candidates and evaluation criteria](../product-requirements/index.md#product-requirements-document-prd-7-technical-constraints-and-candidates-71-stack-candidates-v1)
- [PRD Section 7.2 — Key technical risks (hallucination, latency)](../product-requirements/index.md#product-requirements-document-prd-7-technical-constraints-and-candidates-72-key-technical-risks)
- [PRD NFR 6.3 — Security and privacy requirements](../product-requirements/index.md#product-requirements-document-prd-6-non-functional-requirements-63-security-and-privacy)
- [Engineering Review EC-01 — RAG triage mechanism (tool use recommendation)](../product-requirements/engineering-review.md#engineering-review-ai-powered-lead-qualification-chat-engineering-concerns-ec-01-rag-triage-mechanism-not-specified-fr-15-gap)
- [Engineering Review EC-08 — GDPR DPA requirement](../product-requirements/engineering-review.md#engineering-review-ai-powered-lead-qualification-chat-engineering-concerns-ec-08-gdpr-data-processing-agreement-with-llm-provider)
- [Chat Behaviour](../considerations/chat-behaviour.md) — Conversation model complexity that drives instruction following requirements
- [Qualification Signals](../considerations/qualification-signals.md) — Qualification logic that the LLM must execute reliably across turns

---

*ADRs are immutable once accepted. If this decision is superseded,
create a new ADR and update the Status field above to
`Superseded by ADR-NNN`. Do not edit the body of this document.*
