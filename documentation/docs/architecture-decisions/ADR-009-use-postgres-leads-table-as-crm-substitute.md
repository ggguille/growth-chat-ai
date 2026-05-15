---
description: "ADR-009: Decision to use a PostgresCRMClient implementation of the existing CRMClient interface to persist lead records to a PostgreSQL leads table in v1, deferring external CRM integration to v2 — covers alternatives considered, rationale, schema, and impact on existing specifications."
---

# ADR-009 — Use PostgreSQL leads table as CRM substitute

**Status:** `Accepted`
**Date:** 2026-05-15
**Decision owner:** AI Engineering Lead
**Participants:** AI Engineering Lead, Product Owner

---

## Context

The PRD (M10, FR-19) requires that at every handoff the system creates a structured lead record pre-populated with the full context packet. The Human Handoff Subsystem (TRD §3.4) was designed assuming an external CRM as the record destination, with the specific platform left unresolved in OQ-04. This project is an AI engineering study — there is no commercial sales operation, no existing CRM subscription, and no operational team that would consume lead records from an external system. Integrating a real CRM platform would add a third-party dependency, an external API contract, authentication secrets, and significant Phase 3 implementation effort for a capability that provides no practical value in this context. A decision on OQ-04 is required before Phase 3 build begins (Week 0).

---

## Decision

**We will not integrate an external CRM in v1. Lead records will be persisted to a `leads` table in the existing PostgreSQL instance (Neon) via a `PostgresCRMClient` — a concrete implementation of the existing `CRMClient` interface defined in TRD §5.2. The interface, its method signatures, and its position in the Human Handoff Subsystem remain unchanged; only the backing implementation differs from the originally anticipated external API client.**

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **PostgreSQL `leads` table (chosen)** | Persist the full `ContextPacket` as a structured row in a new `leads` table in the existing Neon instance | Reuses the already-provisioned PostgreSQL instance; zero new services; schema mirrors a CRM lead record | — Chosen |
| External CRM (HubSpot, Pipedrive, etc.) | Integrate a real CRM via its REST API; create a lead record per handoff | Specified in the original PRD; provides a real lead management UI | No commercial operation exists to consume the records; adds external API dependency, authentication secrets, and third-party account management for no practical gain in an engineering study project |
| Object storage bucket (S3 / Cloudflare R2) | Write each `ContextPacket` as a JSON file to an object storage bucket | Low cost, no schema required, easy to inspect files | Adds a new service (R2 or S3) not present in the current infrastructure; no queryability without additional tooling; file-per-lead model is harder to audit than a relational table; PostgreSQL is already provisioned and better suited |
| No lead persistence beyond `HandoffRecord` | Rely solely on the existing `handoff_records` audit table and the Slack notification | Simplest possible option; no new schema | `HandoffRecord` is an audit artefact for delivery status, not a lead record — it does not contain the full `ContextPacket` and cannot substitute for a lead store; Slack messages are ephemeral and not queryable |

---

## Rationale

The core requirement behind OQ-04 is that lead data captured during a handoff must be persisted in a structured, queryable form — not just delivered ephemerally to Slack. An external CRM fulfils that requirement in a commercial context, but this project has no commercial context. The requirement reduces to: store the `ContextPacket` in a durable, structured, inspectable location.

PostgreSQL already satisfies all of those properties and is already provisioned (ADR-003, ADR-004). Adding a `leads` table is an incremental schema migration — a single `CREATE TABLE` — not a new service. The `ContextPacket` schema maps naturally to relational columns: scalar qualification fields become typed columns; `signals_observed` is stored as `JSONB`; the `conversation_summary` is a `TEXT` field. The resulting table is queryable with standard SQL, inspectable via any Postgres client, and auditable alongside the `handoff_records` table.

The object storage alternative (R2 / S3) would introduce a new infrastructure service for a use case that PostgreSQL handles without additional cost or complexity. The no-persistence alternative is rejected because `HandoffRecord` does not contain the full `ContextPacket` and was not designed as a lead store.

The critical design constraint is that the `CRMClient` interface in TRD §5.2 is preserved exactly as specified — same name, same method signatures (`create_lead(context_packet: ContextPacket) -> str`), same position in the Human Handoff Subsystem. What changes is the concrete implementation behind it: `PostgresCRMClient` writes to the `leads` table instead of calling an external HTTP API. In v2, swapping to a `HubSpotCRMClient` or `PipedriveCRMClient` requires no changes to the Human Handoff Subsystem or any upstream component — only the implementation class changes.

---

## `leads` Table Schema

```sql
CREATE TABLE leads (
    id                  SERIAL PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Lead classification
    lead_level          TEXT NOT NULL CHECK (lead_level IN ('hot', 'warm', 'cold')),
    handoff_reason      TEXT NOT NULL CHECK (handoff_reason IN ('hot_lead', 'explicit_request', 'stall', 'llm_failure')),

    -- Visitor data (PII — see Compliance Notes)
    visitor_email       TEXT,
    visitor_name        TEXT,
    visitor_company     TEXT,
    visitor_role        TEXT,

    -- Qualification state
    problem_fit         TEXT NOT NULL,
    authority_fit       TEXT NOT NULL,
    company_fit         TEXT NOT NULL,
    timing_fit          TEXT NOT NULL,
    is_consultant       BOOLEAN NOT NULL DEFAULT FALSE,
    referral_mentioned  BOOLEAN NOT NULL DEFAULT FALSE,

    -- Conversation metadata
    turn_count          INTEGER NOT NULL,
    signals_observed    JSONB NOT NULL DEFAULT '[]',

    -- Summary
    conversation_summary TEXT NOT NULL
);

CREATE INDEX leads_created_at_idx ON leads (created_at DESC);
CREATE INDEX leads_lead_level_idx ON leads (lead_level);
CREATE INDEX leads_session_id_idx ON leads (session_id);
```

The `id` returned by the `INSERT` is used as the `crm_record_id` field in the `HandoffRecord` (TRD §4.4), preserving the audit link between delivery outcome and lead record.

---

## Impact on Existing Specifications

| Document | Section | Change required |
| --- | --- | --- |
| TRD §5.2 | CRM Interface | No interface change. Add `PostgresCRMClient` as the v1 concrete implementation; document that it writes to the `leads` table instead of an external API |
| TRD §3.4 | Human Handoff Subsystem | No structural change. `crm_record_id` populated with `leads.id` (cast to string) on successful insert |
| TRD §4.4 | HandoffRecord schema | `crm_record_id` interpretation updated: contains `leads.id` (integer as string) rather than an external CRM record identifier |
| trd-infrastructure-requirements.md | Human Handoff env vars | Remove `CRM_API_URL` and `CRM_API_KEY`; no replacement vars required — `CHECKPOINT_DB_URL` already covers the Neon connection |
| PRD §9 OQ-04 | Open Questions | Mark as resolved |

---

## Consequences

### Positive

- OQ-04 is resolved with zero new infrastructure — no new service, no new secrets, no new external dependency
- Phase 3 build is unblocked immediately
- The `leads` table is queryable with standard SQL; any Postgres client can inspect, filter, and export lead records
- The `CRMClient` interface is preserved unchanged — v2 CRM integration is a drop-in implementation swap with no application-layer changes required
- `crm_record_id` in `HandoffRecord` continues to function as an audit link — it now points to `leads.id`

### Negative / Trade-offs

- No CRM UI — lead records are visible only via SQL queries or a Postgres client; there is no lead management interface in v1
- No CRM-side deduplication, assignment rules, or pipeline automation — features that a real CRM would provide
- The `leads` table is co-located with operational data (vector store, session state) in the same Postgres instance; a large volume of leads would marginally increase storage, though at the scale of an engineering study this is negligible

### Constraints on future decisions

- The `CRMClient` interface must not be modified to accommodate Postgres-specific behaviour; any implementation detail that requires leaking storage concerns into the interface is a sign the `PostgresCRMClient` implementation needs refactoring, not the interface
- If the project is extended into a real commercial deployment, OQ-04 must be re-opened and a real CRM selected; this ADR does not constitute a long-term architecture decision for a production sales system
- The `CHECKPOINT_DB_URL` connection string used for session state (ADR-004) is reused for the `leads` table; the two concerns share a connection pool — this is acceptable at current concurrency levels but should be monitored if load increases significantly

---

## Compliance Notes

- The `leads` table stores PII (visitor email, name, company, role). The same GDPR data handling requirements that apply to `SessionState` (TRD §8 — Data Minimisation and Retention) apply here: retention must be bounded, PII columns must be clearable on deletion request, and access must be logged.
- No new data category is introduced — the same PII already flows through `SessionState` and `HandoffRecord`. The `leads` table is an additional persistence target for data already collected.

---

## Review Triggers

This decision should be revisited if:

- The project transitions from an engineering study to a commercial deployment — at that point a real CRM platform must be evaluated and OQ-04 re-opened
- The `leads` table exceeds 50,000 rows — at that scale a dedicated data store or CRM with search and filtering capabilities becomes more appropriate than raw SQL
- A CRM platform is adopted for another business purpose, making integration available at low marginal cost

---

## References

- [PRD §4.1 M10 — CRM lead record creation requirement](../product-requirements/index.md#product-requirements-document-prd-4-feature-scope-moscow)
- [PRD §5.4 FR-19 — Handoff delivery to Slack and CRM](../product-requirements/index.md#product-requirements-document-prd-5-functional-requirements-54-handoff-and-capture)
- [PRD §9 OQ-04 — Open question resolved by this ADR](../product-requirements/index.md#product-requirements-document-prd-9-open-questions)
- [TRD §3 — Human Handoff Subsystem](../technical-requirements/trd-component-specifications.md#component-specifications-human-handoff-subsystem)
- [TRD §4 — HandoffRecord schema](../technical-requirements/trd-data-model.md#data-models-handoffrecord)
- [TRD §5.2 — CRM Interface](../technical-requirements/trd-api-specification.md#api-specifications-handoff-delivery-interfaces-crm-delivery) (to be updated per Impact section above)
- [ADR-003 — Use pgvector and OpenAI Embeddings for Knowledge Retrieval](./ADR-003-use-pgvector-and-openai-embeddings-for-knowledge-retrieval.md) (establishes the PostgreSQL instance this ADR reuses)
- [ADR-004 — Use MemorySaver and PostgreSQL for state persistence](./ADR-004-use-memorysaver-and-postgres-for-state-persistence.md) (establishes the Neon connection string this ADR reuses)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
