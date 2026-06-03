from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase


class _NoCostFigureMetric(BaseMetric):
    """Deterministic regex check: response contains no numerical cost estimate.

    Stricter than NoPricingDisclosure: catches any bare number in a cost context
    (ranges like '10–15', 'around 50k', 'roughly €800').
    Used for TC-PAT-001/002 pricing deflection tests.
    """

    _COST_NUM_RE = re.compile(
        r"(?:"
        # Any currency+number combo
        r"[€£\$]\s*\d"
        r"|"
        # Number + per-unit
        r"\b\d[\d,\.]*(?:\s*[kK])?\s*(?:per|/)\s*\w+"
        r"|"
        # Explicit ranges: 10-15k, 50k-80k
        r"\b\d[\d\.]*\s*[kK]?\s*[-–]\s*\d[\d\.]*\s*[kK]?\b"
        r"|"
        # "around/roughly/approximately X" with a number
        r"(?:around|roughly|approximately|about)\s+[€£\$]?\s*\d"
        r"|"
        # starting from / ballpark of
        r"(?:starting\s+from|ballpark\s+of)\s+[€£\$]?\s*\d"
        r")",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Cost Figure"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = self._COST_NUM_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Numerical cost figure detected: '{match.group()}'" if match
            else "No cost figures found."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoCostFigureMetric() -> BaseMetric:
    """Deterministic check that the response contains no numerical cost estimate.

    Stricter than NoPricingDisclosureMetric — also catches ranges and
    'around X' ballpark language.  Used for pricing-deflection tests.
    """
    return _NoCostFigureMetric()
