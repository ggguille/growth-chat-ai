"""RAGAS 0.4.x compatibility layer — VertexAI stub and lazy import."""
from __future__ import annotations

import sys


def _patch_ragas_vertexai_compat() -> None:
    """RAGAS 0.4.3 imports ChatVertexAI at module load time but langchain-community
    0.4+ removed that submodule. Inject a stub so the import does not fail — we
    never use VertexAI, it only appears in RAGAS's MULTIPLE_COMPLETION_SUPPORTED list.
    """
    from types import ModuleType  # noqa: PLC0415

    if "langchain_community.chat_models.vertexai" in sys.modules:
        return
    try:
        import langchain_community.chat_models.vertexai  # noqa: PLC0415, F401
        return
    except ImportError:
        pass

    stub = ModuleType("langchain_community.chat_models.vertexai")

    class _ChatVertexAIStub:
        pass

    stub.ChatVertexAI = _ChatVertexAIStub  # type: ignore[attr-defined]
    sys.modules["langchain_community.chat_models.vertexai"] = stub
    try:
        import langchain_community.chat_models as _cm  # noqa: PLC0415
        _cm.vertexai = stub  # type: ignore[attr-defined]
    except ImportError:
        pass


def load_ragas():  # noqa: ANN202
    """Lazy-import RAGAS metrics and classes, applying compatibility patches first.

    Returns a 10-tuple:
        (evaluate, EvaluationDataset, SingleTurnSample, LangchainEmbeddingsWrapper,
         LangchainLLMWrapper, faithfulness, answer_relevancy, context_precision,
         context_recall, RunConfig)

    Exits with code 1 if RAGAS is not installed.
    """
    _patch_ragas_vertexai_compat()
    try:
        from ragas import evaluate  # noqa: PLC0415
        from ragas.dataset_schema import EvaluationDataset, SingleTurnSample  # noqa: PLC0415
        from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: PLC0415
        from ragas.llms import LangchainLLMWrapper  # noqa: PLC0415
        from ragas.metrics import (  # noqa: PLC0415
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from ragas.run_config import RunConfig  # noqa: PLC0415
    except ImportError as exc:
        print(f"[error] RAGAS is not installed: {exc}")
        print("        Run `uv sync --package evaluation --extra ragas` from the project root.")
        print("        Note: on Windows with Python 3.14, use Linux/WSL or CI instead.")
        sys.exit(1)

    return (
        evaluate,
        EvaluationDataset,
        SingleTurnSample,
        LangchainEmbeddingsWrapper,
        LangchainLLMWrapper,
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        RunConfig,
    )
