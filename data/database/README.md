# database

Migration runner and schema tooling for Growth Chat. Manages all custom PostgreSQL tables via plain SQL files; the LangGraph checkpointer tables (`checkpoints`, `checkpoint_writes`) are handled separately by `AsyncPostgresSaver.setup()` at backend startup.

## Local development

Copy the env file and start the local Postgres container (requires Docker, uses `pgvector/pgvector:pg17`):

```bash
cp data/database/.env.example data/database/.env
docker compose up -d
```

Apply all pending migrations:

```bash
uv run --package database python -m database.migrate
```

`CHECKPOINT_DB_URL` is loaded from `data/database/.env`. In CI, it is read from the `CHECKPOINT_DB_URL` GitHub Actions secret — no `.env` file is used there.

### All commands

| Command | Description |
| --- | --- |
| `python -m database.migrate` | Apply all pending migrations |
| `python -m database.migrate --dry-run` | Print pending migrations without applying |
| `python -m database.migrate --rollback 1` | Roll back the last applied migration |
| `python -m database.migrate --rollback N` | Roll back the last N applied migrations |
| `python -m database.migrate --rollback N --dry-run` | Preview rollback without executing |

## Migrations

SQL files live in `migrations/`. Every migration has a companion `.down.sql` file for rollback. Applied versions are tracked in a `schema_migrations` table created automatically on first run.

| Migration | Description |
| --- | --- |
| `0001_pgvector_extension` | Enables the pgvector extension |
| `0002_knowledge_chunks` | Production knowledge store — 1536-dim HNSW index |
| `0003_knowledge_chunks_dev` | Dev knowledge store — 384-dim HNSW index |
| `0004_handoff_records` | Human handoff audit trail |
| `0005_leads` | CRM substitute — lead records |
| `0006_knowledge_chunks_metadata` | Adds `category`, `title`, `description`, `proactive_eligible` to both knowledge tables |

**Rollback ordering:** `0001` (pgvector extension) cannot be rolled back while `knowledge_chunks` tables exist. Roll back `0003` and `0002` first.

## Seeds

`seeds/dev_seed.sql` is a placeholder for local development data. Run manually after migrations:

```bash
psql postgresql://growth:growth@localhost:5432/growth_chat -f data/database/seeds/dev_seed.sql
```

## CI/CD

Migrations run in `deploy-backend.yml` before the Docker image is deployed. The `CHECKPOINT_DB_URL` secret must be set in the `production` GitHub environment. The migration step is currently commented out — enable it once the secret is configured.
