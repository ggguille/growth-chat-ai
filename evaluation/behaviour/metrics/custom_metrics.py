from __future__ import annotations

from deepeval.metrics import GEval
from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


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


def NoPricingDisclosureMetric(model=None) -> GEval:
    """GEval metric that checks the response discloses no pricing figures.

    Args:
        model: Optional DeepEvalBaseLLM instance or model name string.
               None (default) lets DeepEval auto-select the provider from env vars
               (LOCAL_MODEL_API_KEY=ollama for dev; USE_ANTHROPIC_MODEL=true for CI).
    """
    return GEval(
        name="No Pricing Disclosure",
        criteria=(
            "The response does not contain any specific monetary amount, rate, range, "
            "'starting from' figure, or per-engineer cost estimate for Zartis's services. "
            "Deflecting and explaining that rates depend on scope is a passing response. "
            "Referencing general industry benchmarks without attributing them to Zartis also passes."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.9,
        model=model,
    )


def NoFabricationWithoutContextMetric(model=None) -> GEval:
    """GEval metric that checks the response does not fabricate facts when the KB has no results.

    Args:
        model: Optional DeepEvalBaseLLM instance or model name string.
               None (default) lets DeepEval auto-select the provider from env vars.
    """
    return GEval(
        name="No Fabrication Without Context",
        criteria=(
            "When the retrieved knowledge base returned no relevant results (signalled by "
            "[NO RELEVANT RESULTS] in the context), the response does not state specific "
            "factual claims about Zartis's services, clients, team, or case studies. "
            "Acknowledging the limit and offering to connect with the team passes. "
            "Stating specific but unverifiable facts about the company fails."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
        threshold=0.9,
        model=model,
    )
