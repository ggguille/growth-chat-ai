import json
from collections.abc import Awaitable, Callable

import anthropic

from backend.llm.base import BaseLLMClient, LLMResponse


class AnthropicLLMClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._client.messages.create(**kwargs)

        tool_call = None
        text = ""
        for block in response.content:
            if block.type == "tool_use":
                tool_call = {"name": block.name, "input": block.input, "id": block.id}
            elif block.type == "text":
                text = block.text

        return LLMResponse(content=text, tool_call=tool_call)

    async def structured_complete(
        self,
        system: str,
        messages: list[dict],
        schema: dict,
    ) -> dict:
        tool_name = schema.get("title", "structured_output").lower().replace(" ", "_")
        tool_def = {
            "name": tool_name,
            "description": "Return structured data matching the schema.",
            "input_schema": schema,
        }
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=messages,
            tools=[tool_def],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        return {}

    async def stream(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        full_text = ""
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_text += text
                if on_token:
                    await on_token(text)
        return full_text
