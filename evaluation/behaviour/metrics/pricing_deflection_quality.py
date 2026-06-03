from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_PRICING_SCOPE_RE = re.compile(
    r"\b(?:scope|team\s+(?:composition|size|structure)|timeline|project\s+(?:details?|specifics?)|"
    r"context|composition|requirements?|specific(?:s|ally)?)\b",
    re.IGNORECASE,
)
_PRICING_OFFER_RE = re.compile(
    r"\b(?:call|conversation|discuss(?:ion)?|introduction|connect|speak|talk|meeting|"
    r"reach\s+out|get\s+in\s+touch|direct\s+conversation|walk\s+you\s+through)\b",
    re.IGNORECASE,
)


class _PricingDeflectionQualityMetric(BaseMetric):
    """Deterministic: passes if pricing deflection explains WHY and offers a path forward.

    Binary behavioural constraint (PB-02) — no LLM judge needed.
    Checks for: (1) scope/context explanation keywords, (2) call/conversation offer keywords.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Pricing Deflection Quality"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        has_scope_explanation = bool(_PRICING_SCOPE_RE.search(text))
        has_offer = bool(_PRICING_OFFER_RE.search(text))
        self.score = 1.0 if (has_scope_explanation and has_offer) else 0.0
        self.success = self.score >= self.threshold
        parts = []
        if not has_scope_explanation:
            parts.append("missing scope/context explanation")
        if not has_offer:
            parts.append("missing call/conversation offer")
        self.reason = (
            "; ".join(parts) if parts
            else "Scope explanation present, path-forward offer present."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def PricingDeflectionQualityMetric() -> BaseMetric:
    """Deterministic check that pricing deflection explains WHY and offers a conversation path."""
    return _PricingDeflectionQualityMetric()
