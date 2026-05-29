from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str
    tool_call: dict | None = None
    # tool_call shape: {"name": str, "input": dict, "id": str}


class BaseLLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Non-streaming completion. Returns text and optional tool_call."""

    @abstractmethod
    async def structured_complete(
        self,
        system: str,
        messages: list[dict],
        schema: dict,
    ) -> dict:
        """Forced structured output matching the given JSON schema."""

    @abstractmethod
    async def stream(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Streaming completion. Calls on_token for each chunk. Returns full text."""
