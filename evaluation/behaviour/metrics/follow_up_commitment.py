from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_FOLLOWUP_COMMITMENT_RE = re.compile(
    r"(?:within\s+(?:a\s+few\s+)?hours|few\s+hours|"
    r"10\s*am\s+CET|10\s*am\s+CEST|"
    r"next\s+business\s+morning|business\s+morning\s+before|"
    r"first\s+thing\s+(?:next|tomorrow)\s+morning)",
    re.IGNORECASE,
)


class _FollowUpCommitmentMetric(BaseMetric):
    """Deterministic: passes if response contains a specific follow-up time commitment.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Follow-up Commitment"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _FOLLOWUP_COMMITMENT_RE.search(text)
        self.score = 1.0 if match else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Time commitment found: '{match.group()}'" if match
            else "No specific time commitment found — vague 'soon'/'asap' fails."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def FollowUpCommitmentMetric() -> BaseMetric:
    """Deterministic check that the response contains a specific follow-up time commitment."""
    return _FollowUpCommitmentMetric()
