---
description: Create Architecture Decision Records (ADRs) using the project template
allowed-tools: Read, Write, Bash
---

# Rule: Create Architecture Decision Records (ADRs)

Whenever you are asked to create an ADR, architecture decision record, or document a technical decision, follow this rule exactly.

## File naming and location

- Place ADRs in `docs/adr/` (create the directory if it does not exist).
- File name format: `ADR-NNN-short-slug.md` where `NNN` is zero-padded (e.g. `ADR-001-use-langgraph-for-orchestration.md`).
- Determine the next available number by listing existing files in `docs/adr/`.
- The slug must reflect the decision made, not the topic evaluated.
  - ✅ `ADR-003-use-postgres-for-session-storage.md`
  - ❌ `ADR-003-database-evaluation.md`

## Template

Always generate the ADR using exactly this template. Fill in every section — never leave placeholder text like `[Describe the situation...]` in the output.

```markdown
# ADR-NNN — [Decision title: short, specific, verb-noun format]

**Status:** Proposed
**Date:** YYYY-MM-DD
**Decision owner:** [Role]
**Participants:** [Roles involved]

---

## Context

[3–6 sentences. Present tense. Describe the situation, constraint, or
requirement that forces this decision. What is the system trying to do?
What happens if no decision is made? Should make sense to someone who
joins the team 6 months from now with no prior context.]

---

## Decision

**We will [decision stated clearly and completely].**

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
|---|---|---|---|
| **Option A — [Chosen]** | [What it is] | [Why evaluated] | — Chosen |
| Option B | [What it is] | [Why evaluated] | [Specific reason rejected] |
| Option C | [What it is] | [Why evaluated] | [Specific reason rejected] |

---

## Rationale

[2–4 paragraphs. Explain why the chosen option was selected. Reference
the evaluation criteria that mattered most. Be honest about trade-offs —
do not pretend the chosen option has no downsides.]

---

## Consequences

### Positive

- [What this decision enables or makes easier]
- [What risk it eliminates or reduces]

### Negative / Trade-offs

- [What this decision makes harder or more constrained]
- [What technical debt is accepted]
- [What future flexibility is reduced]

### Constraints on future decisions

- [What other decisions this ADR constrains or enables]

---

## Compliance Notes

- [Any GDPR, security, licensing, or legal considerations. Remove section if not applicable.]

---

## Review Triggers

This decision should be revisited if:

- [Condition 1 — be specific, e.g. "p95 latency exceeds 3s consistently in production"]
- [Condition 2 — e.g. "vendor changes pricing or data residency policy"]

---

## References

- PRD Section X.X — [relevant section]
- ADR-NNN — [related decision]
- [External reference, benchmark, or evaluation consulted]

---

*ADRs are immutable once accepted. If this decision is superseded,
create a new ADR and update the Status field above to
`Superseded by ADR-NNN`. Do not edit the body of this document.*
```

## Rules for filling in the template

**Title:** Use verb-noun format. Describes what was decided, not what was evaluated.

**Status:** Start as `Proposed`. Only change to `Accepted` when explicitly instructed.

**Date:** Use today's date in `YYYY-MM-DD` format.

**Context:** Write in present tense. 3–6 sentences minimum. Be specific enough that a new team member understands the situation without asking questions.

**Decision:** One sentence starting with "We will…" or "We have decided to…". No reasoning here — that belongs in Rationale.

**Alternatives Considered:** Include the chosen option in the table. Never omit alternatives to make the decision look obvious. Document rejected options so future engineers do not re-evaluate them from scratch. Always include at least 2 alternatives beyond the chosen option.

**Rationale:** Reference specific evaluation criteria. Acknowledge the downsides of the chosen option honestly. Do not write marketing copy for the decision.

**Consequences:** Be specific. "This will be more maintainable" is not useful. "This removes the need for a separate cache invalidation job, reducing operational surface by one service" is useful.

**Review Triggers:** Must be measurable or observable conditions, not vague statements like "if things change".

**Compliance Notes:** Include only if there are genuine GDPR, security, IP, or licensing implications. Remove the section entirely if not applicable — do not leave it with placeholder text.

## What NOT to do

- Do not title an ADR after the topic evaluated ("Database Evaluation"). Title it after the decision made ("Use PostgreSQL for Session Storage").
- Do not leave any section with unfilled placeholder text in the final output.
- Do not omit the Alternatives Considered table to save space.
- Do not write vague consequences or review triggers.
- Do not add sections beyond the template. The template is designed to be comprehensive — if you find yourself adding a new section, it's likely that content belongs in one of the existing sections instead.
- Do not edit an ADR marked `Accepted` — create a new one and update the status of the old one to `Superseded by ADR-NNN`.