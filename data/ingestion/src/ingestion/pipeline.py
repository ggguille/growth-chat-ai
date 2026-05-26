from __future__ import annotations

import os
import re
from pathlib import Path

import psycopg
import yaml

from ingestion.chunker import Chunk, chunk_document
from ingestion.embedder import get_embeddings

_TABLE = "knowledge_chunks_dev"
_FM = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FM.match(text)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)), text[m.end():]


async def run_pipeline(source_dir: str, db_url: str) -> None:
    """Chunk, embed, and upsert all documents from source_dir into pgvector."""
    chunk_size = int(os.environ.get("CHUNK_SIZE", "512"))
    chunk_overlap = int(os.environ.get("CHUNK_OVERLAP", "64"))

    all_chunks: list[Chunk] = []
    source_path = Path(source_dir)

    print(f"Scanning {source_path.resolve()} ...")
    for md_file in sorted(source_path.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        source             = meta.get("source") or md_file.stem
        category           = meta.get("category", "")
        title              = meta.get("title", "")
        description        = meta.get("description", "")
        proactive_eligible = bool(meta.get("proactive_eligible", False))
        chunks = chunk_document(
            source, body, chunk_size, chunk_overlap,
            category=category,
            title=title,
            description=description,
            proactive_eligible=proactive_eligible,
        )
        all_chunks.extend(chunks)
        print(f"  {md_file.relative_to(source_path)}: {len(chunks)} chunk(s)  [source={source}]")

    if not all_chunks:
        print("No chunks produced — check that source_dir contains .md files.")
        return

    print(f"\nEmbedding {len(all_chunks)} chunks with all-MiniLM-L6-v2 ...")
    embedder = get_embeddings()
    vectors = embedder.embed_documents([c.content for c in all_chunks])

    print(f"Upserting into {_TABLE} ...")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for chunk, vector in zip(all_chunks, vectors):
                vector_str = "[" + ",".join(str(x) for x in vector) + "]"
                cur.execute(
                    f"""
                    INSERT INTO {_TABLE}
                        (chunk_id, source, chunk_index, content, content_hash, embedding,
                         category, title, description, proactive_eligible)
                    VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s)
                    ON CONFLICT (source, chunk_index) DO UPDATE SET
                        content            = EXCLUDED.content,
                        content_hash       = EXCLUDED.content_hash,
                        embedding          = EXCLUDED.embedding,
                        category           = EXCLUDED.category,
                        title              = EXCLUDED.title,
                        description        = EXCLUDED.description,
                        proactive_eligible = EXCLUDED.proactive_eligible
                    """,
                    (
                        chunk.chunk_id,
                        chunk.source,
                        chunk.chunk_index,
                        chunk.content,
                        chunk.content_hash,
                        vector_str,
                        chunk.category,
                        chunk.title,
                        chunk.description,
                        chunk.proactive_eligible,
                    ),
                )
        conn.commit()

    print(f"Done — {len(all_chunks)} chunks upserted into {_TABLE}.")


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Knowledge base ingestion pipeline (dev mode).")
    parser.add_argument("--source", required=True, help="Directory containing .md knowledge base files.")
    args = parser.parse_args()

    db_url = os.environ.get("CHECKPOINT_DB_URL")
    if not db_url:
        raise SystemExit("CHECKPOINT_DB_URL environment variable is required.")

    asyncio.run(run_pipeline(args.source, db_url))
