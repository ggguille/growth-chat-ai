import json
from collections.abc import Awaitable, Callable

import anthropic

from backend.llm.base import BaseLLMClient, LLMResponse, LLMUsage


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

        usage = LLMUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return LLMResponse(content=text, tool_call=tool_call, usage=usage, model=self._model)

    async def structured_complete(
        self,
        system: str,
        messages: list[dict],
        schema: dict,
    ) -> tuple[dict, LLMUsage]:
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
        usage = LLMUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        for block in response.content:
            if block.type == "tool_use":
                return block.input, usage
        return {}, usage

    async def stream(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
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
            final = await stream.get_final_message()

        usage = LLMUsage(
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
        )
        return LLMResponse(content=full_text, usage=usage, model=self._model)
