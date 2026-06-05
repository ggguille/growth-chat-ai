# ingestion

Knowledge base ingestion pipeline for Growth Chat. Chunks source documents, generates embeddings, and upserts them into the pgvector store.

## Implementation status

| Component | Status |
| --- | --- |
| `chunker.py` | Implemented — `RecursiveCharacterTextSplitter`, deterministic `chunk_id` |
| `embedder.py` | Implemented — dev and production modes via `get_embeddings()` factory |
| `pipeline.py` | Implemented — walks source dir, strips frontmatter, chunks, embeds, upserts |

## Embedding models

| Environment | Model | Dimensions | Table |
| --- | --- | --- | --- |
| Development | `all-MiniLM-L6-v2` (HuggingFace, local) | 384 | `knowledge_chunks_dev` |
| Production | `text-embedding-3-small` (OpenAI) | 1536 | `knowledge_chunks` |

The dev model runs in-process with no API key. On first run it downloads ~90 MB to `~/.cache/huggingface/`. HuggingFace packages (`langchain-huggingface`, `sentence-transformers`) are in the `dev` dependency group — installed automatically by `uv sync` locally, but absent in production runs (`--no-dev`).

## Running the pipeline

Prerequisites: Docker Compose running, database migrations applied.

### Development (HuggingFace, no API key)

```bash
# 1. Start local Postgres
docker compose up -d

# 2. Apply migrations
uv run --package database python -m database.migrate

# 3. Copy env file and set your connection string
cp data/ingestion/.env.example data/ingestion/.env
# edit data/ingestion/.env as needed

# 4. Run ingestion (writes to knowledge_chunks_dev)
uv run --package ingestion python -m ingestion.pipeline --source data/knowledge-base
```

### Production (OpenAI, 1536-dim)

```bash
# Writes to knowledge_chunks; OPENAI_API_KEY auto-selects the table
OPENAI_API_KEY=sk-... uv run --package ingestion python -m ingestion.pipeline --source data/knowledge-base
```

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `CHECKPOINT_DB_URL` | Yes | — | psycopg3 connection string (`postgresql://...`) |
| `OPENAI_API_KEY` | Production | — | Enables OpenAI `text-embedding-3-small` (1536-dim) |
| `KNOWLEDGE_TABLE_NAME` | No | auto | Target table; auto-detected from `OPENAI_API_KEY` (`knowledge_chunks` or `knowledge_chunks_dev`) |
| `CHUNK_SIZE` | No | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | No | `64` | Token overlap between adjacent chunks |

Copy `.env.example` to `.env` — the pipeline loads it automatically on startup. Production values are set as GitHub Actions secrets; no `.env` file is used there.

## Verifying the result

```sql
-- Dev table (HuggingFace):
SELECT source, COUNT(*) AS chunks
FROM knowledge_chunks_dev
GROUP BY source ORDER BY source;

-- Production table (OpenAI):
SELECT source, COUNT(*) AS chunks
FROM knowledge_chunks
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
