---
description: Create Technical Requirements Documents (TRDs) using the project template
allowed-tools: Read, Write, Glob, Bash
---

# Rule: Create Technical Requirements Documents (TRDs)

Whenever you are asked to create a TRD, technical requirements document, or specify the technical implementation of a feature, follow this rule exactly.

## File naming and location

- Place TRDs in `documentation/docs/technical-requirements/` (create the directory if it does not exist).
- File name format: `trd-short-slug.md` (e.g. `trd-conversation-orchestrator.md`).
- The slug must reflect the system or feature being specified, not the document type.
  - ✅ `trd-conversation-orchestrator.md`
  - ✅ `trd-knowledge-retrieval.md`
  - ❌ `trd-technical-spec.md`
  - ❌ `trd-v1.md`

## Inputs to consult before writing

A TRD is downstream of other documents. Before writing, read:

1. `documentation/docs/templates/template-trd.md` — the authoritative structure. Section numbering, headings, and tables must match it exactly.
2. The project PRD (`product-requirements-document.md` or equivalent) — the product requirements this TRD implements.
3. The engineering review (`pdr-engineering-review.md` or equivalent) — every Engineering Concern (`EC-NN`) listed here must be resolved in section 11 of the TRD or explicitly marked out of scope.
4. All `ADR-*.md` files in `docs/adr/` — these record decisions. The TRD specifies the *implementation* of those decisions; it does not re-justify them.
5. Any architecture diagram referenced by the project (e.g. `chat-orchestrator-diagram.md`).

If a decision needed by the TRD is not yet recorded in an ADR, do not invent it. Add it to section 12 (Open Questions) as `TRD-OQ-NN` and tell the user an ADR is needed.

## Template

The authoritative TRD template lives in the project at:

```text
documentation/docs/templates/template-trd.md
```

Read it on every invocation — it is the single source of truth and may be updated. Do not paraphrase it from memory and do not embed a copy of it in this rule.

The structure has 13 sections, in this order:

1. Purpose and Scope
2. System Architecture
3. Component Specifications
4. Data Models
5. API Specifications
6. Infrastructure Requirements
7. Performance Requirements
8. Security Requirements
9. Observability
10. Resilience and Degradation
11. Engineering Concerns Resolution
12. Open Questions
13. Revision History

Every section must appear, in this order, with the same numbering. If a section does not apply to the system being specified, keep the heading and write *"Not applicable for this TRD — [one-line reason]."* Do not delete sections.

## Rules for filling in the template

**Title and metadata block:** Set `Version: 1.0`, `Status: Draft`, `Last updated:` to today's date in `YYYY-MM-DD`, and leave `Author:` and `Reviewers:` as role placeholders unless the user has named them.

**Section 1 — Purpose and Scope:** State what the TRD specifies and what it does not. The "Inputs" table must list the PRD, every ADR the TRD implements (by ID and title), and the engineering review.

**Section 2 — System Architecture:** Include a diagram. ASCII, Mermaid, or a link to an existing diagram file in the project. Prose-only descriptions are acceptable only when the data flow is genuinely linear and trivial.

**Section 3 — Component Specifications:** One subsection per major component. Each must specify inputs, outputs, internal logic (pseudocode or numbered steps), and error handling. Be precise enough that an engineer can implement it without further clarification.

**Section 4 — Data Models:** Define every persistent or significant transient data structure with field names, types, and constraints. State objects must specify the persistence backend (referencing the relevant ADR), session lifetime, and disposal behaviour.

**Section 5 — API Specifications:** For each endpoint, specify method, path, authentication, request schema, response schema, and the full error response table.

**Section 6 — Infrastructure Requirements:** Compute, storage, networking, and environment variables. Do not include actual secret values — this is a specification, not a config file.

**Section 7 — Performance Requirements:** Be precise. Distinguish TTFT from full response time. Always specify the percentile (p50 / p95 / p99) and the load condition under which the target applies. "Fast" is not a target.

**Section 8 — Security Requirements:** Cover authentication, authorisation, encryption at rest and in transit, PII handling, rate limiting, and GDPR compliance.

**Section 9 — Observability:** Logging, metrics, and analytics events must each be defined as full schemas — not just names. Field names and types must be consistent across frontend and backend.

**Section 10 — Resilience and Degradation:** Each fallback must be independently operable. A fallback that depends on the failed component is not a fallback — flag it.

**Section 11 — Engineering Concerns Resolution:** Mandatory. Every `EC-NN` from the engineering review that falls within the scope of this TRD must appear here with a resolution that points to a specific section number in this document. ECs out of scope must be listed with the document that will resolve them.

**Section 12 — Open Questions:** Any value, schema, or behaviour you cannot specify concretely from the inputs goes here as `TRD-OQ-NN`, with an owner and a "needed by" date or phase. Never silently invent values to fill the template.

**Section 13 — Revision History:** Seed with a single row: version 1.0, today's date, author, "Initial version".

## Cross-cutting rules

**Reference, do not duplicate.** When a decision is recorded in an ADR, cite it (`ADR-NNN`) in the relevant cell. Do not restate the rationale. The TRD specifies *what is built*, not *why it was chosen*.

**No placeholders in the final output.** Every `[bracketed]` placeholder from the template must be replaced with concrete content. Remove every HTML comment (`<!-- ... -->`) — those are author guidance, not document content.

**Match the project's voice.** Precise, declarative, no marketing language. Match the tone of the PRD and existing ADRs.

## Verification before reporting completion

Before telling the user the TRD is done, check:

- Every section 1–13 from the template is present, in order, with the same numbering.
- No `[placeholder]` text or HTML comments remain.
- Every ADR referenced exists in the project. If one is referenced but missing, that is a blocker — surface it.
- Every `EC-NN` from the engineering review is either resolved in section 11 or explicitly marked out of scope with a destination document.
- All values that could not be specified concretely from the inputs are listed in section 12 as `TRD-OQ-NN`.

After writing the file, output:

- The path of the created TRD.
- A short summary: which `TRD-OQ` open questions were raised, which ECs were marked out of scope, and any ADRs the TRD assumes but that don't yet exist.

## What NOT to do

- Do not name a TRD after the document type (`trd-v1.md`, `trd-technical-spec.md`). Name it after the system or feature it specifies.
- Do not leave any section with unfilled placeholder text in the final output.
- Do not skip section 11 (Engineering Concerns Resolution) — it is the explicit handshake with the engineering review.
- Do not invent values, schemas, or thresholds when the inputs do not provide them. Raise them as `TRD-OQ-NN` instead.
- Do not duplicate ADR rationale in the TRD. Reference the ADR by ID.
- Do not modify `documentation/docs/templates/template-trd.md`, the PRD, the engineering review, or any ADR while writing a TRD. Those documents are read-only inputs.
- Do not add sections beyond the 13 in the template. If content does not fit any existing section, it likely belongs in one of them — or it belongs in a separate ADR.
