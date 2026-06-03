from __future__ import annotations

import os
import threading

import pytest
from dotenv import load_dotenv

from behaviour.metrics.custom_metrics import SingleQuestionPerExchangeMetric
from judge import get_judge_model, judge_available

load_dotenv()

_langfuse_key = os.getenv("LANGFUSE_PUBLIC_KEY")

# Thread-local storage for the current test node ID, used by _make_langfuse_assert_test.
_test_context = threading.local()


def _make_langfuse_assert_test(original_fn):
    """Return a wrapper around assert_test that logs metric scores to Langfuse.

    Follows the Langfuse external evaluation pipeline pattern:
    create a trace per test, then call create_score(trace_id=...) for each metric.
    GEval metrics carry a .reason string that is passed as the score comment.
    """
    def _wrapper(test_case, metrics, **kwargs):
        try:
            original_fn(test_case, metrics, **kwargs)
        finally:
            if not _langfuse_key:
                return
            from langfuse import Langfuse  # noqa: PLC0415
            lf = Langfuse()
            test_name = getattr(_test_context, "test_name", "unknown")
            trace_id = lf.create_trace_id()
            with lf.start_as_current_observation(name=test_name, trace_context={"trace_id": trace_id}):
                for m in metrics:
                    score = getattr(m, "score", None)
                    if score is None:
                        continue
                    lf.create_score(
                        trace_id=trace_id,
                        name=f"{getattr(m, "name", None)} ({type(m).__name__})",
                        value=float(score),
                        comment=getattr(m, "reason", None),
                    )
            lf.flush()
    return _wrapper


def pytest_itemcollected(item):
    """Patch assert_test in each test module's namespace to enable Langfuse logging.

    Test files use `from deepeval import assert_test` (direct import), so the fix
    must replace the name in the test module's own __dict__ rather than in deepeval.
    Runs once per module at collection time — before any test executes.
    """
    if not _langfuse_key:
        return
    module = getattr(item, "module", None)
    if module is None or getattr(module, "_lf_patched", False):
        return
    if not hasattr(module, "assert_test"):
        return
    module.assert_test = _make_langfuse_assert_test(module.assert_test)
    module._lf_patched = True


_NO_JUDGE_MSG = (
    "No LLM-as-judge provider configured. "
    "Set JUDGE_PROVIDER=ollama (dev) or JUDGE_PROVIDER=anthropic (CI) in evaluation/.env. "
    "See evaluation/.env.example for full configuration."
)


@pytest.fixture(autouse=True)
def _set_test_context(request):
    """Store the current test node ID so _make_langfuse_assert_test can name the trace."""
    _test_context.test_name = request.node.nodeid
    yield
    _test_context.test_name = None


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
