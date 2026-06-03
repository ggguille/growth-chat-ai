from __future__ import annotations

import re

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase

_STAGE3_PROPOSAL_RE = re.compile(
    r"\b(?:call|introduction|connect|engineer|20[- ]?min(?:ute)?)\b",
    re.IGNORECASE,
)
_STAGE3_EMAIL_ASK_RE = re.compile(r"\bemail\b", re.IGNORECASE)


class _Stage3ProposalMetric(BaseMetric):
    """Deterministic: passes if response proposes a next step AND requests an email address.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Stage 3 Proposal"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        has_proposal = bool(_STAGE3_PROPOSAL_RE.search(text))
        has_email = bool(_STAGE3_EMAIL_ASK_RE.search(text))
        self.score = 1.0 if (has_proposal and has_email) else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"proposal={'yes' if has_proposal else 'NO'}, "
            f"email_ask={'yes' if has_email else 'NO'}"
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def Stage3ProposalMetric() -> BaseMetric:
    """Deterministic check that Stage 3 response proposes a next step and requests email."""
    return _Stage3ProposalMetric()
