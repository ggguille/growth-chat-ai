from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_CONTACT_REQUEST_RE = re.compile(
    r"(?:your\s+email|email\s+address|contact\s+(?:details|info)|"
    r"pass.*?contact|send.*?email|share.*?email|"
    r"what(?:'s|\s+is)\s+(?:your|the\s+best)\s+email)",
    re.IGNORECASE,
)


class _NoContactRequestMetric(BaseMetric):
    """Deterministic: fails if response asks for email or contact details.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Contact Request"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _CONTACT_REQUEST_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Contact request detected: '{match.group()}'" if match
            else "No contact request found — response is clean."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoContactRequestMetric() -> BaseMetric:
    """Deterministic check that the response does not ask for contact details."""
    return _NoContactRequestMetric()
