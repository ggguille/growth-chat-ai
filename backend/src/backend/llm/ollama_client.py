import json
from collections.abc import Awaitable, Callable

import ollama

from telemetry import get_logger

from backend.llm.base import BaseLLMClient, LLMResponse, LLMUsage

log = get_logger("orchestrator")


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
            # Convert Anthropic-format tools (input_schema) to OpenAI/Ollama format (parameters)
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", t.get("parameters", {})),
                    },
                }
                for t in tools
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

        usage = LLMUsage(
            input_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
        )
        return LLMResponse(content=msg.content or "", tool_call=tool_call, usage=usage, model=self._model)

    async def structured_complete(
        self,
        system: str,
        messages: list[dict],
        schema: dict,
    ) -> tuple[dict, LLMUsage]:
        full_messages = self._prepend_system(system, messages)
        response = await self._client.chat(
            model=self._model,
            messages=full_messages,
            format=schema,
        )
        usage = LLMUsage(
            input_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
        )
        try:
            return json.loads(response.message.content or "{}"), usage
        except json.JSONDecodeError:
            log.warn("ollama_json_parse_failure", session_id=None, error="failed to parse JSON response")
            return {}, usage

    async def stream(
        self,
        system: str,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        full_messages = self._prepend_system(system, messages)
        full_text = ""
        input_tokens = 0
        output_tokens = 0
        async for chunk in await self._client.chat(
            model=self._model,
            messages=full_messages,
            stream=True,
        ):
            token = chunk.message.content or ""
            full_text += token
            if on_token and token:
                await on_token(token)
            if chunk.done:
                input_tokens = chunk.prompt_eval_count or 0
                output_tokens = chunk.eval_count or 0
        usage = LLMUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        return LLMResponse(content=full_text, usage=usage, model=self._model)
