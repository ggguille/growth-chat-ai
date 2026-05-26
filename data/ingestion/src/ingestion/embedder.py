from __future__ import annotations

from langchain_huggingface import HuggingFaceEmbeddings


def get_embeddings(model_name: str | None = None):
    """Return a LangChain Embeddings instance.

    Production: OpenAI text-embedding-3-small (1536-dim) via OPENAI_EMBEDDING_MODEL env var.
    Development: HuggingFace all-MiniLM-L6-v2 (384-dim) when model_name is unset.
    """
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
