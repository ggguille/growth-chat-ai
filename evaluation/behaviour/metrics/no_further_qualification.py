from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_EMAIL_KEYWORD_RE = re.compile(r"\bemail\b|\baddress\b", re.IGNORECASE)


class _NoFurtherQualificationMetric(BaseMetric):
    """Deterministic: Stage 3 response may ask for email only — no qualifying questions.

    PASS: no '?' in response, or every question sentence contains an email keyword.
    FAIL: any question sentence without an email keyword (qualifying question present).
    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Further Qualification"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        qualifying_qs = [s for s in sentences if "?" in s and not _EMAIL_KEYWORD_RE.search(s)]
        self.score = 0.0 if qualifying_qs else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Qualifying question(s) detected: {qualifying_qs}" if qualifying_qs
            else "No qualifying questions found — response is email-ask only or question-free."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoFurtherQualificationMetric() -> BaseMetric:
    """Deterministic check that Stage 3 asks for email only, with no qualifying questions."""
    return _NoFurtherQualificationMetric()
