from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from behaviour.metrics.custom_metrics import SingleQuestionPerExchangeMetric

load_dotenv()

# Configure Langfuse integration when keys are present — DeepEval auto-detects
_langfuse_key = os.getenv("LANGFUSE_PUBLIC_KEY")
if _langfuse_key:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", _langfuse_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", os.getenv("LANGFUSE_SECRET_KEY", ""))
    os.environ.setdefault("LANGFUSE_HOST", os.getenv("LANGFUSE_HOST", "https://eu.cloud.langfuse.com"))


def _llm_judge_available() -> bool:
    """True when at least one LLM-as-judge provider is configured.

    Supported providers (checked in order of precedence):
    - Ollama: LOCAL_MODEL_API_KEY=ollama + LOCAL_MODEL_NAME  (dev, offline)
    - Anthropic: USE_ANTHROPIC_MODEL=true + ANTHROPIC_API_KEY  (CI/production)
    - OpenAI: OPENAI_API_KEY  (legacy fallback)
    """
    return bool(
        os.getenv("LOCAL_MODEL_API_KEY") == "ollama"  # dev: Ollama
        or os.getenv("USE_ANTHROPIC_MODEL")           # CI: Claude Haiku
    )


_NO_JUDGE_MSG = (
    "No LLM-as-judge provider configured. "
    "Dev: set LOCAL_MODEL_API_KEY=ollama + LOCAL_MODEL_NAME in evaluation/.env. "
    "CI: set USE_ANTHROPIC_MODEL=true + ANTHROPIC_API_KEY in evaluation/.env."
)


@pytest.fixture
def single_question_per_exchange() -> SingleQuestionPerExchangeMetric:
    return SingleQuestionPerExchangeMetric()


@pytest.fixture
def no_pricing_disclosure():
    if not _llm_judge_available():
        pytest.skip(_NO_JUDGE_MSG)
    from behaviour.metrics.custom_metrics import NoPricingDisclosureMetric
    return NoPricingDisclosureMetric()


@pytest.fixture
def no_fabrication_without_context():
    if not _llm_judge_available():
        pytest.skip(_NO_JUDGE_MSG)
    from behaviour.metrics.custom_metrics import NoFabricationWithoutContextMetric
    return NoFabricationWithoutContextMetric()
