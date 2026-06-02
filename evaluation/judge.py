"""Shared LLM-as-judge factory for the evaluation suite.

Provides a single configuration interface for both local (Ollama) and cloud
(Anthropic) judge models used by DeepEval GEval metrics.

Configuration via environment variables:

    # Local dev — Ollama (no API key required; Ollama must be running)
    JUDGE_PROVIDER=ollama
    JUDGE_MODEL=llama3.1:8b
    OLLAMA_BASE_URL=http://localhost:11434   # optional, this is the default

    # CI / pipelines — Anthropic Claude
    JUDGE_PROVIDER=anthropic
    JUDGE_MODEL=claude-haiku-4-5-20251001
    ANTHROPIC_API_KEY=<key>

Usage:
    from judge import judge_available, get_judge_model

    if not judge_available():
        pytest.skip("No JUDGE_PROVIDER configured")
    metric = SomeGEvalMetric(model=get_judge_model())

Design notes:
    - For Anthropic, get_judge_model() returns a model name STRING. DeepEval's
      initialize_model() resolves strings to its native AnthropicModel when
      ANTHROPIC_API_KEY is set. This avoids custom wrapper classes.
    - For Ollama, get_judge_model() returns an _OllamaJudge (DeepEvalBaseLLM)
      that uses ollama.Client (sync, no LangChain) to avoid AsyncLibraryNotFoundError
      when called from within pytest-asyncio + nest_asyncio contexts.
"""

from __future__ import annotations

import json
import os

from deepeval.models.base_model import DeepEvalBaseLLM


def judge_available() -> bool:
    """True when JUDGE_PROVIDER is set to a supported value."""
    return os.getenv("JUDGE_PROVIDER", "").lower() in ("ollama", "anthropic")


def get_judge_model() -> DeepEvalBaseLLM | str | None:
    """Return the configured judge model.

    Returns:
        - str: model name for Anthropic (DeepEval resolves it natively)
        - DeepEvalBaseLLM: _OllamaJudge instance for Ollama
        - None: when JUDGE_PROVIDER is not configured
    """
    provider = os.getenv("JUDGE_PROVIDER", "").lower()
    model_name = os.getenv("JUDGE_MODEL", "")

    if provider == "anthropic":
        return model_name or "claude-haiku-4-5-20251001"

    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return _OllamaJudge(model_name or "llama3.1:8b", base_url)

    return None


class _OllamaJudge(DeepEvalBaseLLM):
    """Judge backed by a locally running Ollama instance.

    Uses ollama.Client (sync, no LangChain) to avoid async context conflicts
    when DeepEval calls generate() from within a nest_asyncio event loop.
    a_generate() runs the sync call in a thread-pool executor.

    Requires: Ollama running at OLLAMA_BASE_URL (default http://localhost:11434).
    """

    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self._model_name = model
        self._base_url = base_url

    def get_model_name(self) -> str:
        return self._model_name

    def load_model(self) -> None:
        return None

    def generate(self, prompt: str, schema=None) -> object:
        import ollama  # noqa: PLC0415

        client = ollama.Client(host=self._base_url)

        if schema is not None:
            fmt = (
                schema.model_json_schema()
                if hasattr(schema, "model_json_schema")
                else schema
            )
            response = client.chat(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                format=fmt,
            )
            try:
                data = json.loads(response.message.content or "{}")
                if hasattr(schema, "model_validate"):
                    return schema.model_validate(data)
                return data
            except Exception:
                return response.message.content or ""

        response = client.chat(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.message.content or ""

    async def a_generate(self, prompt: str, schema=None) -> object:
        import asyncio  # noqa: PLC0415

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.generate(prompt, schema))
