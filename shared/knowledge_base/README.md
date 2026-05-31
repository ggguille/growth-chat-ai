# knowledge_base

Shared embedding factory used by `backend` (query-time retrieval) and `data/ingestion` (document ingestion). Provides a single `get_embeddings()` function that returns a [`langchain_core.embeddings.Embeddings`](https://python.langchain.com/docs/concepts/embedding_models/) instance, switching between dev and production providers based on the environment.

## Embedding modes

| Mode | Condition | Model | Dimensions | Cost |
| --- | --- | --- | --- | --- |
| Development | `OPENAI_API_KEY` not set | HuggingFace `all-MiniLM-L6-v2` | 384 | Free (local inference) |
| Production | `OPENAI_API_KEY` set | OpenAI `text-embedding-3-small` | 1536 | ~$0.02 / 1M tokens |

> **The embedding model and the pgvector table must always match.** Dev embeddings (384-dim) go into `knowledge_chunks_dev`; production embeddings (1536-dim) go into `knowledge_chunks`. Querying the wrong table returns no results — pgvector silently mismatches dimensions.

## Usage

```python
from knowledge_base import get_embeddings

# Sync — used by the ingestion pipeline
embedder = get_embeddings()
vectors = embedder.embed_documents(["chunk one", "chunk two"])

# Async — used by the backend retrieval layer
vector = await get_embeddings().aembed_query("What services does Zartis offer?")
```

## API

### `get_embeddings() -> Embeddings`

Returns a LangChain `Embeddings` instance. The choice of provider is made once per call based on `OPENAI_API_KEY`. All standard LangChain embedding methods are available on the returned object:

| Method | Signature | Notes |
| --- | --- | --- |
| `embed_documents` | `(list[str]) -> list[list[float]]` | Sync batch embed |
| `embed_query` | `(str) -> list[float]` | Sync single embed |
| `aembed_documents` | `async (list[str]) -> list[list[float]]` | Async batch embed |
| `aembed_query` | `async (str) -> list[float]` | Async single embed |

## Dependencies

| Package | Purpose |
| --- | --- |
| `langchain-core>=1.4.0` | `Embeddings` base class and async fallback via `run_in_executor` |
| `langchain-huggingface>=1.2.2` | Dev provider (`HuggingFaceEmbeddings`) |
| `langchain-openai>=1.2.2` | Production provider (`OpenAIEmbeddings`) |
| `sentence-transformers>=5.5.1` | Runtime backend for HuggingFace embeddings (lazy import; ~90 MB model download on first use, cached to `~/.cache/huggingface/`) |
