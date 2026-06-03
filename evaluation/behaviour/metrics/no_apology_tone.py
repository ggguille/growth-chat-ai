from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_APOLOGY_TONE_RE = re.compile(
    r"\b(?:unfortunately|I'm sorry|I am sorry|I'm afraid|I apologise|I apologize|my apologies)\b",
    re.IGNORECASE,
)


class _NoApologyToneMetric(BaseMetric):
    """Deterministic: fails if response uses apologetic language about availability/hours.

    Binary behavioural constraint (PB-24) — no LLM judge needed.
    Scans for specific apologetic words. If any appear, the response violates PB-24.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Apology Tone"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _APOLOGY_TONE_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Apologetic phrase detected: '{match.group()}'" if match
            else "No apologetic language found — response is matter-of-fact."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoApologyToneMetric() -> BaseMetric:
    """Deterministic check that the response contains no apologetic language (PB-24)."""
    return _NoApologyToneMetric()
