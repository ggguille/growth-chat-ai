from __future__ import annotations

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase


class SingleQuestionPerExchangeMetric(BaseMetric):
    """Deterministic check: each assistant response contains at most one question.

    Counts '?' characters. A second '?' in the same turn violates the CDD rule
    (§2.2 Stage 2: ask exactly one qualifying question per exchange).
    Single-character exclamatory sentences ending in '?' are counted as questions.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Single Question Per Exchange"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        count = text.count("?")
        self.score = 1.0 if count <= 1 else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Found {count} question mark(s) — passes." if count <= 1
            else f"Found {count} question marks — CDD allows at most 1 per exchange."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success
