"""Retrieve KB chunks from pgvector for RAGAS context evaluation.

Connects directly to the same pgvector table the backend queries, so the
evaluation uses the real retrieval path without going through the chat API.

Environment variables
---------------------
RAGAS_DB_URL
    psycopg3 connection string, e.g.
    ``postgresql+psycopg://user:pass@host:5432/dbname``.
    If unset, falls back to ``CHECKPOINT_DB_URL`` (backend convention).
RAGAS_EMBEDDING_MODE
    ``dev``  — sentence-transformers ``all-MiniLM-L6-v2`` (384-dim),
               matches ``knowledge_chunks_dev`` table.
    ``prod`` — OpenAI ``text-embedding-3-small`` (1536-dim),
               matches ``knowledge_chunks`` table.
    Default: ``dev``.
RAGAS_TOP_K
    Number of chunks to retrieve per question.  Default: ``3``.
OPENAI_API_KEY
    Required only when ``RAGAS_EMBEDDING_MODE=prod``.
"""

from __future__ import annotations

import os
from functools import lru_cache

import psycopg

# ── Embedding helpers ─────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_st_model():
    """Load sentence-transformers model once and cache it."""
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    return SentenceTransformer("all-MiniLM-L6-v2")


def _embed_dev(text: str) -> list[float]:
    """Embed *text* using the dev sentence-transformers model (384-dim)."""
    model = _get_st_model()
    return model.encode(text, convert_to_numpy=True).tolist()


def _embed_prod(text: str) -> list[float]:
    """Embed *text* using OpenAI text-embedding-3-small (1536-dim)."""
    from openai import OpenAI  # noqa: PLC0415

    client = OpenAI()  # reads OPENAI_API_KEY from env
    response = client.embeddings.create(model="text-embedding-3-small", input=text)
    return response.data[0].embedding


# ── Public API ────────────────────────────────────────────────────────────────


def embed_question(question: str, mode: str) -> list[float]:
    """Return the embedding vector for *question* using the configured mode."""
    if mode == "prod":
        return _embed_prod(question)
    return _embed_dev(question)


def retrieve_contexts(question: str, *, mode: str | None = None, top_k: int | None = None) -> list[str]:
    """Return the top-K chunk content strings most similar to *question*.

    Args:
        question: The visitor question to retrieve context for.
        mode:     Embedding mode — ``"dev"`` or ``"prod"``.  Falls back to
                  ``RAGAS_EMBEDDING_MODE`` env var, defaulting to ``"dev"``.
        top_k:    Number of chunks to return.  Falls back to ``RAGAS_TOP_K``
                  env var, defaulting to ``3``.

    Returns:
        List of chunk content strings ordered by relevance (most relevant first).
        Returns an empty list if the database is unreachable or no chunks exist.
    """
    mode = mode or os.environ.get("RAGAS_EMBEDDING_MODE", "dev")
    top_k = top_k or int(os.environ.get("RAGAS_TOP_K", "3"))
    table = "knowledge_chunks" if mode == "prod" else "knowledge_chunks_dev"

    db_url = os.environ.get("RAGAS_DB_URL") or os.environ.get("CHECKPOINT_DB_URL")
    if not db_url:
        raise RuntimeError(
            "RAGAS_DB_URL (or CHECKPOINT_DB_URL) must be set to run the RAGAS evaluation."
        )

    # psycopg3 uses postgresql:// URI; strip the +psycopg dialect hint if present
    conn_str = db_url.replace("postgresql+psycopg://", "postgresql://")

    embedding = embed_question(question, mode)
    # Format the vector as a PostgreSQL-compatible literal for the <=> operator
    vector_literal = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT content
                FROM {table}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_literal, top_k),
            )
            rows = cur.fetchall()

    return [row[0] for row in rows]
