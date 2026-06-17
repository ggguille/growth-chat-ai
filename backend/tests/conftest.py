from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from backend.llm.base import BaseLLMClient, LLMResponse, LLMUsage


class FakeLLMClient(BaseLLMClient):
    """Minimal LLM client for unit tests — no real API calls."""

    def __init__(self, response_text: str = "Test response", tool_call: dict | None = None):
        self.response_text = response_text
        self.tool_call = tool_call

    async def complete(self, system: str, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        return LLMResponse(content=self.response_text, tool_call=self.tool_call)

    async def structured_complete(self, system: str, messages: list[dict], schema: dict) -> tuple[dict, LLMUsage]:
        return {}, LLMUsage()

    async def stream(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        if on_token:
            for word in self.response_text.split():
                await on_token(word + " ")
        return LLMResponse(content=self.response_text)


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    from backend import config
    monkeypatch.setattr(config.settings, "zgc_api_key", "")


@pytest.fixture(autouse=True)
def mock_llm_client(monkeypatch):
    """Patch create_llm_client to return FakeLLMClient so tests run without Ollama."""
    import backend.llm.factory as factory_module
    monkeypatch.setattr(factory_module, "create_llm_client", lambda _: FakeLLMClient())


@pytest.fixture(autouse=True)
def mock_dispatch_handoff(monkeypatch):
    """Patch dispatch_handoff to a no-op so tests don't hit Slack/CRM/SMTP."""
    import backend.conversation.graph.nodes.propose_handoff as node
    monkeypatch.setattr(node, "dispatch_handoff", AsyncMock())


@pytest.fixture
async def client():
    from backend.main import app

    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c
