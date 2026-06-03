from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_PRICING_FIGURE_RE = re.compile(
    r"(?:"
    # Currency symbol followed by digits: €5,000 / $800 / £1k
    r"[€£\$]\s*\d[\d,\.]*(?:\s*[kK])?"
    r"|"
    # Digits followed by per-unit pricing: 800/day, 5000/month, 50k/engineer
    r"\b\d[\d,\.]*(?:\s*[kK])?\s*(?:per|/)\s*(?:day|month|week|hour|engineer|person)\b"
    r"|"
    # "starting from X" pattern
    r"starting\s+from\s+[€£\$]?\s*\d"
    r"|"
    # Explicit day rate + digits: "day rate of 800"
    r"day\s+rate\s+(?:of\s+|is\s+)?[€£\$]?\s*\d"
    r")",
    re.IGNORECASE,
)


class _NoPricingDisclosureMetric(BaseMetric):
    """Deterministic regex check: response contains no specific pricing figures.

    Replaces the GEval version to avoid small-model judge unreliability.
    A 'pricing figure' is a monetary amount, day rate, cost range, or
    'starting from' pricing language with an attached number.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Pricing Disclosure"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _PRICING_FIGURE_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Pricing figure detected: '{match.group()}'" if match
            else "No pricing figures found — response is clean."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoPricingDisclosureMetric(model=None) -> BaseMetric:
    """Deterministic regex-based pricing disclosure check.

    The `model` parameter is accepted for API compatibility but ignored —
    this metric no longer requires an LLM judge.
    """
    return _NoPricingDisclosureMetric()
