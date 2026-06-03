from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_TECHNICAL_DEPTH_RE = re.compile(
    r"\b(?:chunk(?:ing|size|s|ed|strategy)?|vector\s+store|pgvector|pinecone|"
    r"embedding(?:\s+model)?s?|retrieval(?:\s+pipeline)?|latency|hallucin\w+|"
    r"production\s+deploy|context\s+window|inference|fine[- ]tun|"
    r"relevance\s+threshold|rerank(?:ing)?|RAG)\b",
    re.IGNORECASE,
)


class _TechnicalDepthMetric(BaseMetric):
    """Deterministic: passes if response references at least one specific RAG/LLM technical term.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Technical Depth"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _TECHNICAL_DEPTH_RE.search(text)
        self.score = 1.0 if match else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Technical term found: '{match.group()}'" if match
            else "No RAG/LLM technical term found in response."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def TechnicalDepthMetric() -> BaseMetric:
    """Deterministic check that the response references at least one RAG/LLM technical term."""
    return _TechnicalDepthMetric()
