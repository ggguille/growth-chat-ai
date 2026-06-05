from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_LIMIT_ACKNOWLEDGEMENT_RE = re.compile(
    r"\b(?:don'?t have|not available|can'?t share|no specific|not to hand|"
    r"don'?t have access|specific.*?not available|unavailable|not accessible)\b",
    re.IGNORECASE,
)
_FORWARD_PATH_RE = re.compile(
    r"\b(?:connect you|connect you with|one of our engineers?|reach out|get in touch|"
    r"technical team|have someone|follow[- ]?up|set up a call|introduction)\b",
    re.IGNORECASE,
)
_LATENCY_FIGURE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ms\b|milliseconds?\b|seconds?\b)",
    re.IGNORECASE,
)


class _HonestLimitAcknowledgementMetric(BaseMetric):
    """Deterministic: passes if response acknowledges limit, offers forward path, and avoids fabrication.

    Checks all three of: (1) acknowledgement phrase, (2) forward path offer, (3) no latency figure.
    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Honest Limit Acknowledgement"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        has_ack = bool(_LIMIT_ACKNOWLEDGEMENT_RE.search(text))
        has_path = bool(_FORWARD_PATH_RE.search(text))
        no_figure = not bool(_LATENCY_FIGURE_RE.search(text))
        self.score = 1.0 if (has_ack and has_path and no_figure) else 0.0
        self.success = self.score >= self.threshold
        parts = []
        if not has_ack:
            parts.append("missing acknowledgement phrase")
        if not has_path:
            parts.append("missing forward path offer")
        if not no_figure:
            parts.append("latency figure detected")
        self.reason = (
            "; ".join(parts) if parts
            else "Acknowledgement present, forward path offered, no fabricated figure."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def HonestLimitAcknowledgementMetric() -> BaseMetric:
    """Deterministic check: acknowledges limit, offers forward path, and avoids inventing figures."""
    return _HonestLimitAcknowledgementMetric()
