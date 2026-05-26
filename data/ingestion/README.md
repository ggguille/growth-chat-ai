# ingestion

Knowledge base ingestion pipeline for Growth Chat. Chunks source documents, generates embeddings, and upserts them into the pgvector store.

## Implementation status

| Component | Status |
| --- | --- |
| `chunker.py` | Implemented — `RecursiveCharacterTextSplitter`, deterministic `chunk_id` |
| `embedder.py` | Implemented — dev mode (`HuggingFaceEmbeddings`, 384-dim) |
| `pipeline.py` | Implemented — walks source dir, strips frontmatter, chunks, embeds, upserts |

## Embedding models

| Environment | Model | Dimensions | Table |
| --- | --- | --- | --- |
| Development | `all-MiniLM-L6-v2` (HuggingFace, local) | 384 | `knowledge_chunks_dev` |
| Production | `text-embedding-3-small` (OpenAI) | 1536 | `knowledge_chunks` |

The dev model runs in-process with no API key. On first run it downloads ~90 MB to `~/.cache/huggingface/`.

## Running the pipeline (dev)

Prerequisites: Docker Compose running, database migrations applied.

```bash
# 1. Start local Postgres
docker compose up -d

# 2. Apply migrations
uv run --package database python -m database.migrate

# 3. Run ingestion
# Bash
CHECKPOINT_DB_URL=postgresql://growth:growth@localhost:5432/growth_chat \
uv run --package ingestion python -m ingestion.pipeline --source data/knowledge-base

# PowerShell
$env:CHECKPOINT_DB_URL = "postgresql://growth:growth@localhost:5432/growth_chat"
uv run --package ingestion python -m ingestion.pipeline --source data/knowledge-base
```

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `CHECKPOINT_DB_URL` | Yes | — | psycopg3 connection string (`postgresql://...`) |
| `CHUNK_SIZE` | No | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | No | `64` | Token overlap between adjacent chunks |

Copy `.env.example` to `.env` as a reference — variables must be exported manually, not loaded automatically.

## Verifying the result

```sql
SELECT source, COUNT(*) AS chunks
FROM knowledge_chunks_dev
GROUP BY source ORDER BY source;
```

Expected: one row per source document, each with 1–5 chunks.

## Document format

Source files must be Markdown (`.md`). Files with YAML frontmatter are supported — the pipeline strips the frontmatter before chunking and uses the `source` field as the chunk identifier:

```yaml
---
source: my-document-slug
category: services
---
```

If no frontmatter is present, the filename stem is used as the source.
