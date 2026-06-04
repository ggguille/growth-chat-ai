"""generate_response node factory — main LLM call with RAG retrieval and post-processing."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from langchain_core.callbacks import adispatch_custom_event

from backend.conversation.models import GraphState
from backend.conversation.prompt import build_system_prompt
from backend.handoff.business_hours import is_business_hours
from backend.knowledge.retrieval import retrieve_knowledge

from ..messages import _RETRIEVE_KNOWLEDGE_TOOL, _format_retrieval_result, _to_api_messages
from ..postprocessing import (
    _COMMITMENT_MARKERS,
    _NO_RESULTS_FORWARD_PATH_RE,
    _TECHNICAL_INPUT_RE,
    _TECHNICAL_TERMS_RE,
    _enforce_single_question,
    _strip_turn0_contact_requests,
)

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


def _make_generate_response(llm_client: "BaseLLMClient", context_window: int):
    async def _generate_response(state: GraphState, config) -> dict:
        """Call LLM with system prompt, optionally retrieve from knowledge base."""
        system = build_system_prompt(state)
        api_messages = _to_api_messages(state.get("messages", []), context_window)

        # Pass 1: check whether LLM wants to call retrieve_knowledge
        try:
            response = await llm_client.complete(
                system=system,
                messages=api_messages,
                tools=[_RETRIEVE_KNOWLEDGE_TOOL],
            )
        except Exception as exc:
            logger.error("llm_generation_failure: %s", exc)
            fallback = "I'm having trouble responding right now — can I connect you with the team directly?"
            await adispatch_custom_event("token", {"content": fallback}, config=config)
            return {
                "messages": [{"role": "assistant", "content": fallback}],
                "handoff_reason": "llm_failure",
            }

        if response.tool_call and response.tool_call["name"] == "retrieve_knowledge":
            query = response.tool_call["input"].get("query", "")
            retrieval = await retrieve_knowledge(query)

            tool_id = response.tool_call.get("id", "tool-0")
            tool_result_block = _format_retrieval_result(tool_id, retrieval)

            # Build messages including the tool use + result
            messages_continued = api_messages + [
                {"role": "assistant", "content": f"[retrieve_knowledge called with query: {query}]"},
                {"role": "user", "content": tool_result_block[0]["content"]},
            ]

            # Pass 2: buffer full response without dispatching — post-processing runs first
            try:
                full_text = await llm_client.stream(
                    system=system,
                    messages=messages_continued,
                    on_token=None,
                )
            except Exception as exc:
                logger.error("llm_generation_failure (pass 2): %s", exc)
                full_text = "I'm having trouble responding right now — can I connect you with the team directly?"

            # Guarantee forward path when retrieval returned no results (PB-01, Layer 5 Rule 2).
            if not (retrieval.status == "ok" and retrieval.chunks):
                if not _NO_RESULTS_FORWARD_PATH_RE.search(full_text):
                    full_text = (
                        full_text.rstrip(" .")
                        + " I can connect you with one of our engineers"
                          " who can speak to this from direct experience."
                    )
        else:
            # No tool use — full_text buffered; dispatch happens after post-processing below
            full_text = response.content

        # Post-process: enforce at most one question (Rule 1 — small models often generate 2)
        full_text = _enforce_single_question(full_text)

        if state.get("turn_counter", 0) == 0:
            # Post-process: strip contact requests (Rule 3 — no contact before value)
            full_text = _strip_turn0_contact_requests(full_text)
            # Post-process: ensure technical depth for technical queries (Rule 2 enforcement)
            last_user_msg = next(
                (m["content"] for m in reversed(api_messages) if m["role"] == "user"), ""
            )
            if _TECHNICAL_INPUT_RE.search(last_user_msg) and not _TECHNICAL_TERMS_RE.search(full_text):
                full_text = (
                    full_text.rstrip(" .")
                    + " For production RAG systems the key decisions are typically"
                    " around chunking strategy, embedding model selection, and retrieval pipeline tuning."
                )

        # Post-process: enforce clean close when email captured after Stage 3 (Rule 5)
        if state.get("stage3_proposals_issued", 0) > 0 and state.get("visitor_email"):
            if not any(m in full_text.lower() for m in _COMMITMENT_MARKERS):
                in_hours = is_business_hours(same_day_followup=True)
                commitment = (
                    "One of our engineers will be in touch within a few hours."
                    if in_hours
                    else "They will reach out first thing next business morning before 10am CET/CEST."
                )
                full_text = f"Got it, I've passed your email to the team. {commitment}"

        # Single unified dispatch — clients always see post-processed text
        for word in full_text.split(" "):
            if word:
                await adispatch_custom_event("token", {"content": word + " "}, config=config)

        return {"messages": [{"role": "assistant", "content": full_text}]}

    return _generate_response
