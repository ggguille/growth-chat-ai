from dataclasses import dataclass, field
from datetime import UTC, datetime

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

from backend.analytics.events import AnalyticsEvent, emit_event
from backend.config import settings

log = get_logger("rag")


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


async def retrieve_knowledge(
    query: str,
    session_id: str | None = None,
    turn_index: int | None = None,
) -> RetrievalResult:
    """Embed query and search pgvector for relevant knowledge chunks.

    Uses OpenAI embeddings when OPENAI_API_KEY is set, otherwise falls back
    to HuggingFace sentence-transformers (dev only, no API key required).
    """
    try:
        embedding = await _embed_query(query)
    except Exception as exc:
        log.warn(tel_events.EMBEDDING_API_FAILURE, session_id=session_id, turn_index=turn_index, error=sanitize_error(str(exc)))
        return RetrievalResult(status="error", reason="embedding_failure")

    try:
        raw_chunks = await _vector_search(embedding)
    except Exception as exc:
        log.error(tel_events.VECTOR_SEARCH_FAILURE, session_id=session_id, turn_index=turn_index, error=str(exc))
        return RetrievalResult(status="error", reason="search_failure")

    above = [c for c in raw_chunks if c.score >= settings.rag_relevance_threshold]
    now = datetime.now(UTC)
    if not above:
        await emit_event(AnalyticsEvent(
            name="rag_no_result",
            session_id=session_id or "",
            timestamp=now,
            payload={"turn_index": turn_index},
        ))
        return RetrievalResult(status="no_result", reason="below_threshold")

    top = above[: settings.rag_top_k]
    proactive = bool(
        top
        and top[0].source.startswith("case-study-")
        and top[0].score >= settings.rag_relevance_threshold + 0.10
    )
    await emit_event(AnalyticsEvent(
        name="rag_retrieved",
        session_id=session_id or "",
        timestamp=now,
        payload={
            "query_length": len(query),
            "chunks_returned": len(top),
            "top_score": top[0].score,
            "turn_index": turn_index,
        },
    ))
    return RetrievalResult(status="ok", chunks=top, proactive_case_study=proactive)


async def _embed_query(query: str) -> list[float]:
    from knowledge_base import get_embeddings

    return await get_embeddings().aembed_query(query)


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
