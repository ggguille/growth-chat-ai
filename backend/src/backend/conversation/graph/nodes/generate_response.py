"""generate_response node factory — main LLM call with RAG retrieval and post-processing."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

from langchain_core.callbacks import adispatch_custom_event

from backend.analytics.events import generation_span
from backend.conversation.models import GraphState
from backend.conversation.prompt import build_system_prompt
from backend.handoff.business_hours import is_business_hours
from backend.knowledge.retrieval import retrieve_knowledge

from ..messages import _RETRIEVE_KNOWLEDGE_TOOL, _format_retrieval_result, _to_api_messages
from ..postprocessing import (
    _COMMITMENT_MARKERS,
    _CROSS_SESSION_RE,
    _DEFINITION_CLAUSE_RE,
    _NO_RESULTS_FORWARD_PATH_RE,
    _TECHNICAL_INPUT_RE,
    _TECHNICAL_TERMS_RE,
    _TIMELINE_PREF_RE,
    _enforce_cross_session_ack,
    _enforce_identity_disclosure,
    _enforce_ip_routing,
    _enforce_referral_acknowledgment,
    _enforce_single_question,
    _strip_apology_openers,
    _strip_pricing_figures_for_negative_persona,
    _strip_turn0_contact_requests,
)

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient

log = get_logger("orchestrator")


def _make_generate_response(llm_client: "BaseLLMClient", context_window: int):
    async def _generate_response(state: GraphState, config) -> dict:
        """Call LLM with system prompt, optionally retrieve from knowledge base."""
        system = build_system_prompt(state)
        api_messages = _to_api_messages(state.get("messages", []), context_window)

        # Pass 1: check whether LLM wants to call retrieve_knowledge
        with generation_span(
            name="generate_response_pass1",
            model=getattr(llm_client, "_model", "unknown"),
            input_messages=api_messages,
            metadata={
                "session_id": state.get("session_id"),
                "turn_index": state.get("turn_counter", 0),
            },
        ) as gen:
            try:
                response = await llm_client.complete(
                    system=system,
                    messages=api_messages,
                    tools=[_RETRIEVE_KNOWLEDGE_TOOL],
                )
            except Exception as exc:
                log.error(tel_events.LLM_GENERATION_FAILURE, session_id=state.get("session_id"), turn_index=state.get("turn_counter", 0), error=sanitize_error(str(exc)))
                fallback = "I'm having trouble responding right now — can I connect you with the team directly?"
                await adispatch_custom_event("token", {"content": fallback}, config=config)
                return {
                    "messages": [{"role": "assistant", "content": fallback}],
                    "handoff_reason": "llm_failure",
                }
            if gen is not None:
                gen.update(
                    model=response.model,
                    output=response.content or (response.tool_call.get("name", "") if response.tool_call else ""),
                    usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens}
                    if response.usage else {},
                )

        rag_triggered = bool(response.tool_call and response.tool_call["name"] == "retrieve_knowledge")

        # Determine last user message for guards and post-processing below.
        last_user_msg = next(
            (m["content"] for m in reversed(api_messages) if m["role"] == "user"), ""
        )

        # Cross-session memory guard: suppress RAG so Critical Rule 4 response fires cleanly.
        if rag_triggered and _CROSS_SESSION_RE.search(last_user_msg):
            rag_triggered = False

        # N1/N2 persona guard: suppress retrieve_knowledge except for the explicit N1 exception
        # (named-client lookup). Prevents raw tool-call JSON in Pass 1 content and meta-commentary
        # in Pass 2 when retrieved content doesn't match the N2 general-knowledge query.
        if rag_triggered:
            _qual = state.get("qualification")
            _is_negative = getattr(_qual, "is_negative_persona", False)
            if _is_negative:
                _N1_CLIENT_LOOKUP_RE = re.compile(
                    r"(?:which|what)\s+(?:companies|clients?|brands?|organisations?)"
                    r".*?(?:worked?\s+with|partnered|clients?)",
                    re.IGNORECASE,
                )
                if not _N1_CLIENT_LOOKUP_RE.search(last_user_msg):
                    rag_triggered = False

        if rag_triggered:
            query = response.tool_call["input"].get("query", "")
            retrieval = await retrieve_knowledge(
                query,
                session_id=state.get("session_id"),
                turn_index=state.get("turn_counter", 0),
            )

            is_negative = getattr(state.get("qualification"), "is_negative_persona", False)

            if retrieval.status == "ok" and retrieval.chunks:
                tool_id = response.tool_call.get("id", "tool-0")
                tool_result_block = _format_retrieval_result(tool_id, retrieval)

                # Build messages including the tool use + result
                messages_continued = api_messages + [
                    {"role": "assistant", "content": f"[retrieve_knowledge called with query: {query}]"},
                    {"role": "user", "content": tool_result_block[0]["content"]},
                ]

                # Pass 2: buffer full response without dispatching — post-processing runs first
                with generation_span(
                    name="generate_response_pass2",
                    model=getattr(llm_client, "_model", "unknown"),
                    input_messages=messages_continued,
                    metadata={
                        "session_id": state.get("session_id"),
                        "turn_index": state.get("turn_counter", 0),
                        "rag_query": query,
                    },
                ) as gen:
                    try:
                        stream_response = await llm_client.stream(
                            system=system,
                            messages=messages_continued,
                            on_token=None,
                        )
                        full_text = stream_response.content
                    except Exception as exc:
                        log.error(tel_events.LLM_GENERATION_FAILURE, session_id=state.get("session_id"), turn_index=state.get("turn_counter", 0), error=sanitize_error(str(exc)))
                        full_text = "I'm having trouble responding right now — can I connect you with the team directly?"
                        stream_response = None
                    if gen is not None and stream_response is not None:
                        gen.update(
                            model=stream_response.model,
                            output=full_text,
                            usage_details={"input": stream_response.usage.input_tokens, "output": stream_response.usage.output_tokens}
                            if stream_response.usage else {},
                        )
            else:
                # Retrieval returned no relevant chunks — skip Pass 2 (avoids "Based on the
                # provided text..." meta-commentary). Do a text-only call so the LLM can answer
                # from its own knowledge without the empty-results context poisoning the response.
                with generation_span(
                    name="generate_response_norag",
                    model=getattr(llm_client, "_model", "unknown"),
                    input_messages=api_messages,
                    metadata={
                        "session_id": state.get("session_id"),
                        "turn_index": state.get("turn_counter", 0),
                        "rag_query": query,
                        "rag_miss": True,
                    },
                ) as gen:
                    try:
                        stream_response = await llm_client.stream(
                            system=system,
                            messages=api_messages,
                            on_token=None,
                        )
                        full_text = stream_response.content or ""
                    except Exception as exc:
                        log.error(tel_events.LLM_GENERATION_FAILURE, session_id=state.get("session_id"), turn_index=state.get("turn_counter", 0), error=sanitize_error(str(exc)))
                        full_text = ""
                        stream_response = None
                    if gen is not None and stream_response is not None:
                        gen.update(
                            model=stream_response.model,
                            output=full_text,
                            usage_details={"input": stream_response.usage.input_tokens, "output": stream_response.usage.output_tokens}
                            if stream_response.usage else {},
                        )
                # Guarantee a forward path when RAG was triggered but returned no results (PB-01).
                # RAG being triggered means the LLM identified a company-specific question —
                # always offer the engineer-connection path in this case, regardless of stage.
                if not _NO_RESULTS_FORWARD_PATH_RE.search(full_text):
                    forward = (
                        " You can find more on the website or reach the team via the contact page."
                        if is_negative
                        else " I can connect you with one of our engineers"
                             " who can speak to this from direct experience."
                    )
                    full_text = (full_text.rstrip(" .") + forward) if full_text else forward.lstrip()
        else:
            # No tool use (or RAG suppressed by guard) — use text content from Pass 1.
            full_text = response.content or ""
            # If a guard suppressed RAG but Pass 1 returned only a tool_call (content is empty),
            # do a text-only fallback call so the client gets a real response.
            if not full_text.strip() and response.tool_call:
                with generation_span(
                    name="generate_response_guard_fallback",
                    model=getattr(llm_client, "_model", "unknown"),
                    input_messages=api_messages,
                    metadata={
                        "session_id": state.get("session_id"),
                        "turn_index": state.get("turn_counter", 0),
                        "guard_fallback": True,
                    },
                ) as gen:
                    try:
                        fallback_resp = await llm_client.stream(
                            system=system,
                            messages=api_messages,
                            on_token=None,
                        )
                        full_text = fallback_resp.content or ""
                    except Exception as exc:
                        log.error(tel_events.LLM_GENERATION_FAILURE, session_id=state.get("session_id"), turn_index=state.get("turn_counter", 0), error=sanitize_error(str(exc)))
                        full_text = ""
                        fallback_resp = None
                    if gen is not None and fallback_resp is not None:
                        gen.update(
                            model=fallback_resp.model,
                            output=full_text,
                            usage_details={"input": fallback_resp.usage.input_tokens, "output": fallback_resp.usage.output_tokens}
                            if fallback_resp.usage else {},
                        )

        # Post-process: strip PB-24 apologetic openers (prompt-only failed multiple runs).
        full_text = _strip_apology_openers(full_text)

        # Post-process: strip pricing figures from N1/N2 responses (N1-002).
        # LLM may generate market-rate figures from training memory even when RAG is suppressed.
        _qual_for_pricing = state.get("qualification")
        if getattr(_qual_for_pricing, "is_negative_persona", False):
            full_text = _strip_pricing_figures_for_negative_persona(full_text)

        # Post-process: enforce at most one question (Rule 1 — small models often generate 2)
        full_text = _enforce_single_question(full_text)

        # Post-process: EC-01 authority question fallback (C9).
        # When problem+timing confirmed and authority unknown, the LLM sometimes omits the question.
        # Append the canonical authority question if none is present.
        _ec01_qual = state.get("qualification")
        if (
            not getattr(_ec01_qual, "is_negative_persona", False)
            and getattr(_ec01_qual, "problem_fit", "") == "confirmed"
            and getattr(_ec01_qual, "timing_fit", "") == "confirmed"
            and getattr(_ec01_qual, "authority_fit", "") == "not_detected"
            and "?" not in full_text
        ):
            full_text = full_text.rstrip(" .") + " Who would the engineers be working alongside on your side?"

        # Post-process: enforce Critical Rule 6 identity disclosure (prompt-only failed 3 runs).
        full_text = _enforce_identity_disclosure(last_user_msg, full_text)

        # Post-process: enforce Critical Rule 4 cross-session memory acknowledgment.
        full_text = _enforce_cross_session_ack(last_user_msg, full_text)

        # Post-process: strip definition clauses for technical-jargon inputs (P1 peer register).
        if _TECHNICAL_INPUT_RE.search(last_user_msg):
            full_text = _DEFINITION_CLAUSE_RE.sub("", full_text)

        # Post-process: enforce Critical Rule 7 referral acknowledgment (prompt-only failed 3 runs).
        # Pass last_user_msg so turn-0 referrals are caught before state persistence completes.
        full_text = _enforce_referral_acknowledgment(state, full_text, last_user_msg)

        # Post-process: enforce PB-04 IP/contract routing — runs LAST so it overrides the
        # referral ack prepend above and prevents the mixed referral+IP canonical response.
        full_text = _enforce_ip_routing(last_user_msg, full_text)

        if state.get("turn_counter", 0) == 0:
            # Post-process: strip contact requests (Rule 3 — no contact before value)
            full_text = _strip_turn0_contact_requests(full_text)
            # Post-process: ensure technical depth for technical queries (Rule 2 enforcement)
            if _TECHNICAL_INPUT_RE.search(last_user_msg) and not _TECHNICAL_TERMS_RE.search(full_text):
                full_text = (
                    full_text.rstrip(" .")
                    + " For production RAG systems the key decisions are typically"
                    " around chunking strategy, embedding model selection, and retrieval pipeline tuning."
                )

        # Post-process: enforce clean close when email captured after Stage 3 (Rule 5).
        if state.get("stage3_proposals_issued", 0) > 0 and state.get("visitor_email"):
            has_timeline_pref = _TIMELINE_PREF_RE.search(last_user_msg)
            if has_timeline_pref:
                # Visitor stated a timeline preference — acknowledge their specific date if mentioned.
                date_match = re.search(
                    r"(?:after|until|from)\s+the\s+(\d+(?:th|st|nd|rd)?)", last_user_msg, re.IGNORECASE
                )
                date_ref = f"after the {date_match.group(1)}" if date_match else "after your return"
                full_text = (
                    f"Got it — I've passed your email to the team. "
                    f"We'll reach out {date_ref}, as you mentioned. Looking forward to connecting then!"
                )
            elif not any(m in full_text.lower() for m in _COMMITMENT_MARKERS):
                in_hours = is_business_hours(same_day_followup=True)
                commitment = (
                    "One of our engineers will be in touch within a few hours."
                    if in_hours
                    else "Our team will be in touch first thing tomorrow morning"
                         " — expect to hear from them by 10am CET/CEST."
                )
                full_text = f"Got it, I've passed your email to the team. {commitment}"

        # Single unified dispatch — clients always see post-processed text
        for word in full_text.split(" "):
            if word:
                await adispatch_custom_event("token", {"content": word + " "}, config=config)

        return {"messages": [{"role": "assistant", "content": full_text}]}

    return _generate_response
