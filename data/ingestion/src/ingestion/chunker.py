from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    chunk_id: str
    source: str
    chunk_index: int
    content: str
    content_hash: str
    category: str = ""
    title: str = ""
    description: str = ""
    proactive_eligible: bool = False


def chunk_document(
    source: str,
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    *,
    category: str = "",
    title: str = "",
    description: str = "",
    proactive_eligible: bool = False,
) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    texts = splitter.split_text(text)
    chunks = []
    for i, t in enumerate(texts):
        chunk_id = sha256(f"{source}:{i}".encode()).hexdigest()[:32]
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                source=source,
                chunk_index=i,
                content=t,
                content_hash=sha256(t.encode()).hexdigest(),
                category=category,
                title=title,
                description=description,
                proactive_eligible=proactive_eligible,
            )
        )
    return chunks
