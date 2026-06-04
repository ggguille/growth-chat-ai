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
    - For Anthropic, get_judge_model() returns _AnthropicJudge (DeepEvalBaseLLM)
      backed by the anthropic SDK directly. This avoids DeepEval's initialize_model()
      string resolution, which may fall through to GPTModel in newer DeepEval versions.
    - For Ollama, get_judge_model() returns an _OllamaJudge (DeepEvalBaseLLM)
      that uses ollama.Client (sync, no LangChain) to avoid AsyncLibraryNotFoundError
      when called from within pytest-asyncio + nest_asyncio contexts.
"""

from __future__ import annotations

import json
import os

from deepeval.models.base_model import DeepEvalBaseLLM


def judge_available() -> bool:
    """True when JUDGE_PROVIDER is set to a supported value AND the required credentials are present."""
    provider = os.getenv("JUDGE_PROVIDER", "").lower()
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "ollama":
        return True  # no API key required
    return False


def get_judge_model() -> DeepEvalBaseLLM | None:
    """Return the configured judge model.

    Returns:
        - DeepEvalBaseLLM: _AnthropicJudge or _OllamaJudge instance
        - None: when JUDGE_PROVIDER is not configured
    """
    provider = os.getenv("JUDGE_PROVIDER", "").lower()
    model_name = os.getenv("JUDGE_MODEL", "")

    if provider == "anthropic":
        return _AnthropicJudge(model_name or "claude-haiku-4-5-20251001")

    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return _OllamaJudge(model_name or "qwen2.5:7b", base_url)

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


class _AnthropicJudge(DeepEvalBaseLLM):
    """Judge backed by Anthropic via the anthropic SDK directly.

    Returns a concrete DeepEvalBaseLLM instance so DeepEval never needs to
    resolve a model string — avoiding the GPTModel fallback in initialize_model().
    a_generate() runs the sync call in a thread-pool executor (same pattern as
    _OllamaJudge) to avoid async context conflicts in pytest-asyncio.
    """

    def __init__(self, model: str) -> None:
        self._model_name = model

    def get_model_name(self) -> str:
        return self._model_name

    def load_model(self) -> None:
        return None

    def generate(self, prompt: str, schema=None) -> object:
        import anthropic  # noqa: PLC0415

        client = anthropic.Anthropic()
        if schema is not None:
            tool_schema = (
                schema.model_json_schema()
                if hasattr(schema, "model_json_schema")
                else schema
            )
            response = client.messages.create(
                model=self._model_name,
                max_tokens=1024,
                tools=[{"name": "output", "input_schema": tool_schema}],
                tool_choice={"type": "tool", "name": "output"},
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    data = block.input
                    if hasattr(schema, "model_validate"):
                        return schema.model_validate(data)
                    return data
            return {}
        response = client.messages.create(
            model=self._model_name,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else ""

    async def a_generate(self, prompt: str, schema=None) -> object:
        import asyncio  # noqa: PLC0415

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.generate(prompt, schema))
