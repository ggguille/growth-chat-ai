from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    source: str
    chunk_index: int
    content: str
    content_hash: str


def chunk_document(
    source: str,
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    raise NotImplementedError
