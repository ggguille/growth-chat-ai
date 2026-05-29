import logging
from dataclasses import dataclass, field

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    score: float
    source: str
    chunk_index: int


@dataclass
class RetrievalResult:
    status: str  # "ok" | "no_result" | "error"
    chunks: list[RetrievedChunk] = field(default_factory=list)
    reason: str | None = None
    proactive_case_study: bool = False


async def retrieve_knowledge(query: str) -> RetrievalResult:
    """Embed query and search pgvector for relevant knowledge chunks.

    Uses OpenAI embeddings when OPENAI_API_KEY is set, otherwise falls back
    to HuggingFace sentence-transformers (dev only, no API key required).
    """
    try:
        embedding = await _embed_query(query)
    except Exception as exc:
        logger.error("embedding_api_failure: %s", exc)
        return RetrievalResult(status="error", reason="embedding_failure")

    try:
        raw_chunks = await _vector_search(embedding)
    except Exception as exc:
        logger.error("vector_search_failure: %s", exc)
        return RetrievalResult(status="error", reason="search_failure")

    above = [c for c in raw_chunks if c.score >= settings.rag_relevance_threshold]
    if not above:
        return RetrievalResult(status="no_result", reason="below_threshold")

    top = above[: settings.rag_top_k]
    proactive = bool(
        top
        and top[0].source.startswith("case-study-")
        and top[0].score >= settings.rag_relevance_threshold + 0.10
    )
    return RetrievalResult(status="ok", chunks=top, proactive_case_study=proactive)


async def _embed_query(query: str) -> list[float]:
    if settings.openai_api_key:
        return await _openai_embed(query)
    return await _huggingface_embed(query)


async def _openai_embed(query: str) -> list[float]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    return response.data[0].embedding


async def _huggingface_embed(query: str) -> list[float]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is required for local dev embeddings. "
            "Install it or set OPENAI_API_KEY to use OpenAI embeddings."
        )
    import asyncio

    model = SentenceTransformer("all-MiniLM-L6-v2")
    loop = asyncio.get_event_loop()
    vector = await loop.run_in_executor(None, lambda: model.encode(query).tolist())
    return vector


async def _vector_search(embedding: list[float]) -> list[RetrievedChunk]:
    if not settings.checkpoint_db_url:
        return []

    import psycopg  # lazy import — libpq required at runtime only

    table = settings.knowledge_table_name
    vector_str = "[" + ",".join(str(v) for v in embedding) + "]"
    limit = settings.rag_top_k * 2  # fetch extra; threshold filter applied in Python

    async with await psycopg.AsyncConnection.connect(settings.checkpoint_db_url) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT
                    chunk_id::text,
                    content,
                    source,
                    chunk_index,
                    (1 - (embedding <=> %s::vector))::float AS score
                FROM {table}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_str, vector_str, limit),
            )
            rows = await cur.fetchall()
            cols = [desc.name for desc in cur.description]
            return [
                RetrievedChunk(
                    chunk_id=row[cols.index("chunk_id")],
                    content=row[cols.index("content")],
                    score=float(row[cols.index("score")]),
                    source=row[cols.index("source")],
                    chunk_index=row[cols.index("chunk_index")],
                )
                for row in rows
            ]
