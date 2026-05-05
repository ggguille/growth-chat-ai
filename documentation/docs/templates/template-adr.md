# ADR-000 — [Decision title: short, specific, verb-noun format]

> **Naming convention:** `ADR-NNN — What-was-decided`, not `ADR-NNN — What-we-considered`.
> Good: `ADR-001 — Use LangGraph for conversation orchestration`
> Bad: `ADR-001 — Orchestration framework evaluation`

**Status:** `Proposed` | `Accepted` | `Deprecated` | `Superseded by ADR-NNN`
**Date:** YYYY-MM-DD
**Decision owner:** [Role — e.g. AI Engineering Lead]
**Participants:** [Roles involved in the decision]

---

## Context

<!--
Describe the situation that makes this decision necessary.
- What is the system trying to do?
- What constraint, requirement, or event forces a decision here?
- What happens if no decision is made?

Write in present tense. Be specific. This section should make sense
to someone who joins the team 6 months from now and has no memory
of the conversation that led to this decision.

Target length: 3–6 sentences.
-->

[Describe the situation, constraint, or requirement that forces this decision.]

---

## Decision

<!--
State the decision in one clear sentence.
Start with "We will..." or "We have decided to..."
Do not explain why here — that belongs in the rationale section.

This sentence should be precise enough that anyone reading it knows
exactly what was decided without reading the rest of the document.
-->

**We will [decision stated clearly and completely].**

---

## Alternatives Considered

<!--
List every option that was seriously evaluated.
For each option, document:
- What it is (1 sentence)
- Why it was considered
- Why it was not chosen

Do not skip alternatives to make the chosen option look obvious.
The value of this section is that it documents the options that were
rejected and why — so future engineers do not re-evaluate them from scratch.

Include the chosen option in this table so the comparison is complete.
-->

| Option | Description | Why considered | Why not chosen |
|---|---|---|---|
| **Option A — [Chosen]** | [What it is] | [Why evaluated] | — Chosen |
| Option B | [What it is] | [Why evaluated] | [Specific reason rejected] |
| Option C | [What it is] | [Why evaluated] | [Specific reason rejected] |

---

## Rationale

<!--
Explain why the chosen option was selected over the alternatives.
Reference the evaluation criteria that mattered most.
Be honest about trade-offs — do not pretend the chosen option has no downsides.

Structure: evaluation criteria → how each option scores → why the chosen option
wins on the criteria that matter most for this specific context.

Target length: 2–4 paragraphs.
-->

[Explain the reasoning. Reference the specific criteria that drove the decision.
Acknowledge the trade-offs accepted by choosing this option.]

---

## Consequences

<!--
Document what changes as a result of this decision.
Split into positive and negative consequences.
Include:
- What becomes easier
- What becomes harder or more constrained
- What technical debt is accepted
- What future decisions this constrains or enables

Be specific. Vague consequences ("this will be more maintainable") are not useful.
Specific consequences ("this adds ~150ms to p95 latency on turns that trigger retrieval")
are useful.
-->

### Positive

- [What this decision enables or makes easier]
- [What risk it eliminates or reduces]

### Negative / Trade-offs

- [What this decision makes harder or more constrained]
- [What technical debt is accepted]
- [What future flexibility is reduced]

### Constraints on future decisions

- [What other decisions this ADR constrains — e.g. "ADR-002 must choose an
  orchestration framework compatible with the LLM's function calling API"]

---

## Compliance Notes

<!--
Optional section. Include only if relevant.
Use for decisions with GDPR, security, licensing, or legal implications.
-->

- [Any compliance or legal considerations this decision introduces or resolves]

---

## Review Triggers

<!--
Under what conditions should this decision be revisited?
Examples:
- "If p95 latency exceeds 3s consistently in production"
- "If monthly LLM API cost exceeds $X"
- "If the chosen vendor changes its pricing or data residency policy"
-->

This decision should be revisited if:

- [Condition 1]
- [Condition 2]

---

## References

<!--
Link to:
- The PRD section or requirement that motivated this decision
- Related ADRs that this decision depends on or constrains
- External documentation, benchmarks, or evaluations consulted
-->

- PRD Section X.X — [relevant section]
- ADR-NNN — [related decision]
- [External reference]

---

*ADRs are immutable once accepted. If this decision is superseded,
create a new ADR and update the Status field above to
`Superseded by ADR-NNN`. Do not edit the body of this document.*
