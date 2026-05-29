import json
import logging
from collections.abc import Awaitable, Callable

import ollama

from backend.llm.base import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class OllamaLLMClient(BaseLLMClient):
    def __init__(self, model: str, base_url: str) -> None:
        self._model = model
        self._client = ollama.AsyncClient(host=base_url)

    def _prepend_system(self, system: str, messages: list[dict]) -> list[dict]:
        return [{"role": "system", "content": system}] + list(messages)

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        full_messages = self._prepend_system(system, messages)
        kwargs: dict = {"model": self._model, "messages": full_messages}
        if tools:
            # Wrap tools in Ollama's expected format
            kwargs["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]

        response = await self._client.chat(**kwargs)
        msg = response.message

        tool_call = None
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            tool_call = {
                "name": tc.function.name,
                "input": tc.function.arguments or {},
                "id": "ollama-tool-0",
            }

        return LLMResponse(content=msg.content or "", tool_call=tool_call)

    async def structured_complete(
        self,
        system: str,
        messages: list[dict],
        schema: dict,
    ) -> dict:
        full_messages = self._prepend_system(system, messages)
        response = await self._client.chat(
            model=self._model,
            messages=full_messages,
            format=schema,
        )
        try:
            return json.loads(response.message.content or "{}")
        except json.JSONDecodeError:
            logger.warning("ollama structured_complete: failed to parse JSON response")
            return {}

    async def stream(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        full_messages = self._prepend_system(system, messages)
        full_text = ""
        async for chunk in await self._client.chat(
            model=self._model,
            messages=full_messages,
            stream=True,
        ):
            token = chunk.message.content or ""
            full_text += token
            if on_token and token:
                await on_token(token)
        return full_text
