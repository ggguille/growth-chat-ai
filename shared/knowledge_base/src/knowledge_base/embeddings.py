from __future__ import annotations

import os

from langchain_core.embeddings import Embeddings


def get_embeddings() -> Embeddings:
    """Return a LangChain Embeddings instance.

    Production (OPENAI_API_KEY set): OpenAIEmbeddings text-embedding-3-small (1536-dim).
    Development (no key): HuggingFaceEmbeddings all-MiniLM-L6-v2 (384-dim).

    The returned object exposes:
      embed_documents(list[str]) -> list[list[float]]  — sync, used by ingestion
      aembed_query(str) -> list[float]                 — async, used by backend
    """
    if os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model="text-embedding-3-small")

    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
