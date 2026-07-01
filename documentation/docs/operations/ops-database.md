---
description: "Operations runbook for the Growth Chat PostgreSQL database — schema, migrations, backup strategy, PITR, recovery, and data retention."
---

# Database

The system uses a single Neon Serverless PostgreSQL instance in Frankfurt. It serves four distinct roles: vector knowledge index (pgvector), LangGraph session state, human handoff audit log, and CRM substitute (leads table).

---

## Platform

| Parameter | Value |
| --- | --- |
| Provider | Neon Serverless PostgreSQL |
| PostgreSQL version | 17 |
| Region | Frankfurt (`eu-central-1`) |
| Plan | Free tier (MVP) |
| Extensions | `pgvector` — installed via migration `0001` |
| Connection | Via `CHECKPOINT_DB_URL` Fly.io secret; `sslmode=require` enforced |
| Free tier limits | 512 MB storage, 24-hour PITR |

The connection pool in the backend is configured for 1–5 connections with `autocommit` mode (required by LangGraph's checkpointer).

---

## Schema Overview

| Table | Role | Retention |
| --- | --- | --- |
| `knowledge_chunks` | Production vector index — 1536-dim OpenAI embeddings | Indefinite (static content) |
| `knowledge_chunks_dev` | Dev vector index — 384-dim HuggingFace embeddings | Indefinite |
| `checkpoints` | LangGraph session state (latest snapshot) | 90 days from last activity |
| `checkpoint_writes` | LangGraph write-ahead log | 90 days from last activity |
| `handoff_records` | Human handoff audit trail | Indefinite (GDPR erasure by request) |
| `leads` | CRM substitute — structured lead records | Indefinite (GDPR erasure by request) |
| `schema_migrations` | Applied migration tracking (managed by the runner) | Indefinite |

Full DDL is in `data/database/migrations/`. Schema decisions are documented in ADR-003, ADR-004, and ADR-009.

---

## Schema Migrations

Migrations are plain SQL files numbered sequentially (`0001`–`0007`). Each has a paired `.down.sql` rollback file. The runner tracks applied versions in the `schema_migrations` table.

**Migrations run automatically** in the backend deploy pipeline (`migrate` job), before the Docker build and deploy steps. A migration failure blocks the entire deploy.

**To apply migrations manually** (e.g. during a recovery or hotfix):

```bash
# Preview what would be applied (no changes made)
uv run --package database python -m database.migrate --dry-run

# Apply pending migrations
uv run --package database python -m database.migrate

# Roll back the last N migrations (uses .down.sql files)
uv run --package database python -m database.migrate --rollback N
```

These commands require `CHECKPOINT_DB_URL` to be set in the environment. Run from the repository root.

**Migration history:**

| Migration | Change |
| --- | --- |
| `0001` | Install `pgvector` extension |
| `0002` | Create `knowledge_chunks` table (1536-dim HNSW index, cosine similarity) |
| `0003` | Create `knowledge_chunks_dev` table (384-dim, same structure) |
| `0004` | Create `handoff_records` table (audit trail, composite PK) |
| `0005` | Create `leads` table (structured lead records) |
| `0006` | Add `category`, `title`, `description`, `proactive_eligible` columns to both knowledge tables |
| `0007` | Add `warm_lead` to `leads.handoff_reason` check constraint |

---

## HNSW Vector Index

The `knowledge_chunks` table uses an HNSW index for fast approximate nearest-neighbour search.

| Parameter | Value |
| --- | --- |
| Index type | HNSW |
| Distance metric | Cosine similarity |
| `m` (build parameter) | `16` |
| `ef_construction` | `64` |
| `ef_search` | Configurable via backend environment variable (default `40`) |

A full index rebuild is triggered by running the [Knowledge Ingestion pipeline](./ops-ingestion.md). No manual `REINDEX` is needed under normal operation.

---

## Backup Strategy

::: callout warning "Not yet implemented"
The automated backup job described below is specified in the TRD but has not been implemented. Currently the only recovery option is Neon's built-in 24-hour PITR. Implementing this job is required before the system enters production under any data-retention SLA.
:::

Neon free tier provides **24-hour point-in-time recovery (PITR)**. The TRD specifies an additional daily backup job to bridge the gap to the required 90-day retention:

1. A scheduled Fly.io machine runs daily at **02:00 CET/CEST**.
2. It executes `pg_dump` against the Neon database and compresses the output.
3. The archive is uploaded to object storage under a `backups/` prefix, named `backup-YYYY-MM-DD.sql.gz`.
4. A 90-day lifecycle policy on the storage bucket deletes archives automatically.

When implemented, a backup job failure should generate a Fly.io machine exit event routed to the alerting system (see [Observability runbook](./ops-observability.md)).

---

## Recovery Procedures

### Data loss within 24 hours

Use Neon's built-in PITR:

1. Open the Neon console and navigate to the project.
2. Create a new branch from a point in time before the loss.
3. Verify the restored data on the new branch.
4. If the branch is good, promote it or update the connection string in Fly.io secrets.

### Data loss beyond 24 hours

::: callout warning "Backup job not yet implemented"
Until the automated daily backup job is in place, recovery beyond the 24-hour PITR window is not possible. See the Backup Strategy section above.
:::

Once the backup job is implemented, the recovery procedure is:

1. Download the most recent daily archive from the `backups/` prefix in object storage.
2. Restore to a new Neon database branch:

   ```bash
   gunzip -c backup-YYYY-MM-DD.sql.gz | psql <new-branch-connection-string>
   ```

3. Verify row counts and data integrity.
4. Update `CHECKPOINT_DB_URL` in Fly.io secrets to point to the restored branch.
5. Restart the backend to pick up the new connection string.

Specific connection strings, bucket names, and Neon project details are maintained in the team's private runbook.

---

## Data Retention

| Data | Retention period | Deletion trigger |
| --- | --- | --- |
| Session state (`checkpoints`, `checkpoint_writes`) | 90 days from last activity | Automated cleanup job (runs weekly) |
| Handoff records | Indefinite | Manual GDPR erasure request only |
| Lead records | Indefinite | Manual GDPR erasure request only |
| Knowledge chunks | Indefinite | Re-ingestion or manual deletion |
| Application logs | 30 days | Managed by the log provider |

**GDPR erasure requests** targeting `handoff_records` or `leads` must be processed manually by the data controller. The request must identify the session ID or visitor email. The relevant rows are deleted, not anonymised, as they may contain PII in structured and free-text fields.

---

## Accepted Risk

At MVP, up to **24 hours of conversation data** may be unrecoverable in a catastrophic failure that exceeds PITR coverage. This is an accepted trade-off on the free tier.

**Upgrade path** if the system enters production under formal SLA commitments: upgrade to the Neon Launch plan (~$19/month), which provides 7-day PITR. No application code changes are required. See ADR-006 for the full review trigger criteria.
