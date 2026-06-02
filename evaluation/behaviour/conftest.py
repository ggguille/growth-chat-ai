from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from behaviour.metrics.custom_metrics import SingleQuestionPerExchangeMetric
from judge import get_judge_model, judge_available

load_dotenv()

# Configure Langfuse integration when keys are present — DeepEval auto-detects
_langfuse_key = os.getenv("LANGFUSE_PUBLIC_KEY")
if _langfuse_key:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", _langfuse_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", os.getenv("LANGFUSE_SECRET_KEY", ""))
    os.environ.setdefault("LANGFUSE_HOST", os.getenv("LANGFUSE_HOST", "https://eu.cloud.langfuse.com"))

_NO_JUDGE_MSG = (
    "No LLM-as-judge provider configured. "
    "Set JUDGE_PROVIDER=ollama (dev) or JUDGE_PROVIDER=anthropic (CI) in evaluation/.env. "
    "See evaluation/.env.example for full configuration."
)


@pytest.fixture(autouse=True)
def _inject_judge_model(monkeypatch):
    """Inject the configured judge into DeepEval's model resolution for GEval metrics.

    Patches initialize_model in the g_eval module namespace so that any
    GEval(model=None) call receives the project judge instead of GPTModel(OpenAI).

    Patching initialize_model (not GEval.__init__) keeps the GEval signature intact,
    which is required by DeepEval's copy_metrics() that introspects __init__ via
    inspect.signature to re-create metric instances during assert_test.

    Reverts automatically after each test via monkeypatch.
    """
    if not judge_available():
        return

    import deepeval.metrics.g_eval.g_eval as _geval_mod  # noqa: PLC0415

    original_initialize = _geval_mod.initialize_model
    judge = get_judge_model()

    def _patched(model=None):
        if model is None:
            if isinstance(judge, str):
                # Anthropic: pass the model string to DeepEval's native resolver
                return original_initialize(judge)
            # Ollama: return our DeepEvalBaseLLM instance directly
            return judge, False
        return original_initialize(model)

    monkeypatch.setattr(_geval_mod, "initialize_model", _patched)


@pytest.fixture
def single_question_per_exchange() -> SingleQuestionPerExchangeMetric:
    return SingleQuestionPerExchangeMetric()


@pytest.fixture
def no_pricing_disclosure():
    from behaviour.metrics.custom_metrics import NoPricingDisclosureMetric
    return NoPricingDisclosureMetric()


@pytest.fixture
def no_fabrication_without_context():
    if not judge_available():
        pytest.skip(_NO_JUDGE_MSG)
    from behaviour.metrics.custom_metrics import NoFabricationWithoutContextMetric
    return NoFabricationWithoutContextMetric(model=get_judge_model())
