from __future__ import annotations


async def run_pipeline(source_dir: str, db_url: str) -> None:
    """Chunk, embed, and upsert all documents from source_dir into pgvector."""
    raise NotImplementedError
