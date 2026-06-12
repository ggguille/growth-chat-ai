"""RAGAS evaluator factories — LLM, embeddings, and run configuration."""
from __future__ import annotations

import os
from typing import Any


def make_evaluator_llm(LangchainLLMWrapper: Any) -> Any:  # noqa: N803
    """Return a RAGAS-compatible LLM using Claude Haiku."""
    from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

    model = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-haiku-4-5-20251001")
    return LangchainLLMWrapper(ChatAnthropic(model=model, max_retries=6))


def make_evaluator_embeddings(LangchainEmbeddingsWrapper: Any, mode: str) -> Any:  # noqa: N803
    """Return RAGAS-compatible embeddings matching the ingestion embedder."""
    from langchain_core.embeddings import Embeddings  # noqa: PLC0415

    if mode == "prod":
        from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

        return LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    # Dev: sentence-transformers, same model as ingestion pipeline
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    class _STEmbeddings(Embeddings):
        def __init__(self) -> None:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self._model.encode(texts, convert_to_numpy=True).tolist()

        def embed_query(self, text: str) -> list[float]:
            return self._model.encode(text, convert_to_numpy=True).tolist()

    return LangchainEmbeddingsWrapper(_STEmbeddings())


def make_run_config(RunConfig: Any) -> Any:  # noqa: N803
    """Build a RAGAS RunConfig that respects the Anthropic rate limit.

    Default max_workers=2 keeps concurrent judge calls well within the 50 req/min
    Haiku tier limit. Increase RAGAS_MAX_WORKERS carefully if you have a higher tier.
    """
    max_workers = int(os.environ.get("RAGAS_MAX_WORKERS", "2"))
    return RunConfig(
        max_workers=max_workers,
        max_retries=10,
        max_wait=60,
        timeout=300,
    )
