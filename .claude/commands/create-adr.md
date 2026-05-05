---
description: Create Architecture Decision Records (ADRs) using the project template
allowed-tools: Read, Write, Glob, Bash
---

# Rule: Create Architecture Decision Records (ADRs)

Whenever you are asked to create an ADR, architecture decision record, or document a technical decision, follow this rule exactly.

## File naming and location

- Place ADRs in `documentation/docs/architecture-decisions/` (create the directory if it does not exist).
- File name format: `ADR-NNN-short-slug.md` where `NNN` is zero-padded (e.g. `ADR-001-use-langgraph-for-orchestration.md`).
- Determine the next available number by listing existing files in `documentation/docs/architecture-decisions/`.
- The slug must reflect the decision made, not the topic evaluated.
  - ✅ `ADR-003-use-postgres-for-session-storage.md`
  - ❌ `ADR-003-database-evaluation.md`

## Template

The authoritative ADR template lives in the project at:

```text
documentation/docs/templates/template-adr.md
```

Read it on every invocation — it is the single source of truth and may be updated. Do not paraphrase it from memory and do not embed a copy of it in this rule.

The structure has these sections, in this order:

1. Title and metadata block (Status, Date, Decision owner, Participants)
2. Context
3. Decision
4. Alternatives Considered
5. Rationale
6. Consequences (Positive / Negative / Constraints on future decisions)
7. Compliance Notes
8. Review Triggers
9. References

Every section must appear, in this order, with the same headings used in the template.

## Rules for filling in the template

**Title:** Use verb-noun format. Describes what was decided, not what was evaluated. Replace `ADR-000` in the template heading with the next available number.

**Status:** Start as `Proposed`. Only change to `Accepted` when explicitly instructed. Other values (`Deprecated`, `Superseded by ADR-NNN`) are only set when an existing ADR is being retired.

**Date:** Use today's date in `YYYY-MM-DD` format.

**Context:** Write in present tense. 3–6 sentences minimum. Be specific enough that a new team member understands the situation without asking questions.

**Decision:** One sentence starting with "We will…" or "We have decided to…". No reasoning here — that belongs in Rationale.

**Alternatives Considered:** Include the chosen option in the table. Never omit alternatives to make the decision look obvious. Document rejected options so future engineers do not re-evaluate them from scratch. Always include at least 2 alternatives beyond the chosen option.

**Rationale:** Reference specific evaluation criteria. Acknowledge the downsides of the chosen option honestly. Do not write marketing copy for the decision.

**Consequences:** Be specific. "This will be more maintainable" is not useful. "This removes the need for a separate cache invalidation job, reducing operational surface by one service" is useful.

**Compliance Notes:** Include only if there are genuine GDPR, security, IP, or licensing implications. Remove the section entirely if not applicable — do not leave it with placeholder text.

**Review Triggers:** Must be measurable or observable conditions, not vague statements like "if things change".

## Cross-cutting rules

**No placeholders in the final output.** Every `[bracketed]` placeholder from the template must be replaced with concrete content. Remove every HTML comment (`<!-- ... -->`) — those are author guidance for the template, not document content.

**Match the project's voice.** Precise, declarative, no marketing language.

## What NOT to do

- Do not title an ADR after the topic evaluated ("Database Evaluation"). Title it after the decision made ("Use PostgreSQL for Session Storage").
- Do not leave any section with unfilled placeholder text or HTML comments in the final output.
- Do not omit the Alternatives Considered table to save space.
- Do not write vague consequences or review triggers.
- Do not add sections beyond those in the template. The template is comprehensive — if you find yourself adding a new section, that content likely belongs in one of the existing sections instead.
- Do not edit an ADR marked `Accepted` — create a new one and update the status of the old one to `Superseded by ADR-NNN`.
- Do not modify `documentation/docs/templates/template-adr.md` while writing an ADR. The template is a read-only input.
