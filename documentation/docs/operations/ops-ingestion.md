---
description: "Operations runbook for the Growth Chat knowledge ingestion pipeline — when to run, how to run, and how to verify results."
---

# Knowledge Ingestion Pipeline

The knowledge ingestion pipeline is a **one-off command**, not a persistent service. It reads the Markdown knowledge base, splits documents into chunks, generates vector embeddings, and upserts them into the PostgreSQL knowledge table. It must be re-run whenever the knowledge base content changes.

---

## Knowledge Base

Source documents live in `data/knowledge-base/` — 15 Markdown files covering company services, team, case studies, engagement models, and FAQ. The content is sourced from the corporate website: pages are scraped, converted to Markdown, and committed to this directory. Each file has YAML frontmatter:

```yaml
---
source: "services/ai-engineering"
category: "services"
title: "AI Engineering Services"
description: "Overview of AI engineering offerings"
proactive_eligible: true
---
```

The `proactive_eligible` flag marks chunks that the chat agent may surface proactively (without a direct visitor question). This is used for relevant case study content.

---

## When to Run

Re-run the pipeline after **any change to files in `data/knowledge-base/`**, including updates from re-scraping the corporate website:

- Editing existing document content
- Adding a new document
- Removing a document
- Changing frontmatter fields (especially `proactive_eligible`)

The pipeline is **idempotent**: chunk IDs are derived from a SHA-256 hash of the content. Re-running on unchanged files is safe — it upserts but changes nothing.

---

## How to Run

### Via GitHub Actions (recommended for production)

1. Go to the repository's **Actions** tab.
2. Select the **`ingest-knowledge.yml`** workflow.
3. Click **Run workflow** and confirm.
4. The workflow uses the `production` environment and requires a live database connection and (for production embeddings) an OpenAI API key — both are pre-configured as GitHub secrets.

### Locally (development / testing)

Dev mode uses a local HuggingFace embedding model (`all-MiniLM-L6-v2`, 384-dim). No API key required, but the model (~90 MB) downloads to `~/.cache/huggingface/` on first run.

```bash
# From the repository root
uv sync                       # install workspace deps if not already done
uv run --package ingestion python -m ingestion.pipeline --source data/knowledge-base
```

For production embeddings locally (OpenAI, 1536-dim), set `OPENAI_API_KEY` in the environment before running. See `data/ingestion/.env.example` for all configuration options.

---

## What the Pipeline Does

```text
For each .md file in the source directory:
  1. Strip YAML frontmatter
  2. Split content into overlapping chunks (default: 512 tokens, 64 overlap)
  3. Generate a SHA-256 chunk_id from the content hash
  4. Embed each chunk (HuggingFace in dev, OpenAI in prod)
  5. Upsert into the knowledge table — inserts new chunks, updates changed ones
```

**Dev vs production table:**

| Mode | Embedding model | Dimensions | Table |
| --- | --- | --- | --- |
| Dev (no `OPENAI_API_KEY`) | HuggingFace `all-MiniLM-L6-v2` | 384 | `knowledge_chunks_dev` |
| Prod (with `OPENAI_API_KEY`) | OpenAI `text-embedding-3-small` | 1536 | `knowledge_chunks` |

The backend reads from `knowledge_chunks` in production (set via the `KNOWLEDGE_TABLE_NAME` environment variable).

---

## Verification

After the pipeline completes, verify ingestion was successful:

1. **Check pipeline logs** — the pipeline prints per-file progress and a final chunk count.
2. **Query the database** — connect to Neon and run:

   ```sql
   SELECT COUNT(*) FROM knowledge_chunks;
   -- Expected: ~500 rows for 15 source documents with default chunk settings
   ```

3. **Test retrieval** — send a test question to the live chat API and confirm domain content appears in the response.

If chunk counts are lower than expected, check for frontmatter parse errors in the pipeline logs. If embeddings fail, check the OpenAI API key and quota.

---

## Configuration

All configuration is via environment variables. See `data/ingestion/.env.example` for the full reference.

| Variable | Effect |
| --- | --- |
| Database connection | Which PostgreSQL instance to write to |
| `OPENAI_API_KEY` | If set: use OpenAI embeddings and `knowledge_chunks`; if absent: use HuggingFace and `knowledge_chunks_dev` |
| `CHUNK_SIZE` | Tokens per chunk (default: 512) |
| `CHUNK_OVERLAP` | Token overlap between adjacent chunks (default: 64) |
| `KNOWLEDGE_TABLE_NAME` | Override the target table name |

Chunk size and overlap should match the values used when the HNSW index was calibrated. Changing them requires a full re-ingestion and re-calibration of the RAG relevance threshold (see [evaluation best practices](../evaluation-best-practices.md)).
