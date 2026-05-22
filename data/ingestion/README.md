# ingestion

Knowledge base ingestion pipeline for Growth Chat. Chunks source documents, generates embeddings, and upserts them into the pgvector store.

## Implementation status

| Component | Status |
| --- | --- |
| `chunker.py` | Stub — `chunk_document()` raises `NotImplementedError` |
| `embedder.py` | Stub — `get_embeddings()` raises `NotImplementedError` |
| `pipeline.py` | Stub — `run_pipeline()` raises `NotImplementedError` |

## Embedding models

| Environment | Model | Dimensions | Table |
| --- | --- | --- | --- |
| Production | `text-embedding-3-small` (OpenAI) | 1536 | `knowledge_chunks` |
| Development | `all-MiniLM-L6-v2` (HuggingFace, local) | 384 | `knowledge_chunks_dev` |

Configure via `OPENAI_EMBEDDING_MODEL` and `KNOWLEDGE_TABLE_NAME`. See `trd-infrastructure-requirements.md` for the full variable reference.

## Running the pipeline

Prerequisites: database migrations must have been applied (`data/database`).

```bash
# Local development
uv run --package ingestion python -m ingestion.pipeline --source <docs_dir>

# Production — one-off Fly Machine using the same image as the API
flyctl machine run --app growth-chat-api \
  --image registry.fly.io/growth-chat-api:latest \
  --entrypoint "python -m ingestion.pipeline" \
  -- --source /app/knowledge
```
