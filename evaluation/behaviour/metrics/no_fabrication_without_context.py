from __future__ import annotations

from deepeval.metrics import GEval
from deepeval.test_case import SingleTurnParams


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
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.CONTEXT],
        threshold=0.65,
        model=model,
        async_mode=False,
    )
