"""6-node LangGraph StateGraph — Conversation Orchestrator.

Nodes: update_state → score_router → generate_response → stall_check
                     ↘ propose_handoff ↗               ↘ propose_handoff
                                        → write_state → END

See TRD §3.1 and action-plan.md Phase 2.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain_core.callbacks import adispatch_custom_event
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage

from backend.analytics.events import AnalyticsEvent, emit_event
from backend.conversation.models import GraphState
from backend.conversation.prompt import build_proposal_prompt, build_system_prompt
from backend.handoff.business_hours import is_business_hours
from backend.handoff.delivery import dispatch_handoff
from backend.handoff.models import HandoffRequest
from backend.knowledge.retrieval import RetrievalResult, retrieve_knowledge
from backend.qualification.models import (
    QualificationDelta,
    QualificationState,
    SignalEntry,
    derive_lead_level,
    merge_qualification,
)

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)

# ── Tool definitions ─────────────────────────────────────────────────────────

_RETRIEVE_KNOWLEDGE_TOOL = {
    "name": "retrieve_knowledge",
    "description": (
        "Retrieve relevant information from the company knowledge base. "
        "Call this tool when the visitor asks about company services, case studies, "
        "team expertise, engagement models, or any question requiring specific company "
        "information beyond what is in your instructions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Precise restatement of what the visitor needs to know. "
                    "Should be a noun phrase or question about company domain content."
                ),
            }
        },
        "required": ["query"],
    },
}

_QUALIFICATION_DELTA_SCHEMA = QualificationDelta.model_json_schema()
_QUALIFICATION_DELTA_SCHEMA["title"] = "QualificationDelta"

_EXTRACTION_SYSTEM = """
You extract qualification signals from a visitor message in a B2B sales chat.

Given the current qualification state and the new visitor message, return a JSON object
with ONLY the fields that have new evidence. Omit fields with no new signal.

Qualification dimensions:
- problem_fit: visitor has a concrete AI engineering problem or initiative
  ("not_detected" → "partially_confirmed" → "confirmed")
- authority_fit: visitor has decision-making authority or budget sign-off
  ("not_detected" → "partially_confirmed" → "confirmed")
- company_fit: company size/stage/sector signals suggesting ICP fit
  ("not_detected" → "partially_confirmed" → "confirmed")
- timing_fit: specific timeline, deadline, or urgency signals
  ("not_detected" → "partially_confirmed" → "confirmed")

Also detect:
- is_negative_persona: true if visitor is a competitor (hypothetical pricing/ops probes,
  no real initiative), researcher, student, or journalist
- is_no_fit: true if visitor is clearly outside ICP (individual contractor scope,
  academic purpose, wrong geography/regulatory context)
- explicit_human_request: true if visitor explicitly asks to speak with a human / book a call
- visitor_email: extract if visible in the message
- visitor_name: extract if visible in the message
- visitor_company: extract company name if mentioned
- visitor_role: extract role/title if mentioned
- is_consultant: true if visitor identifies as a freelancer/consultant evaluating for a client
- referral_mentioned: true if visitor mentions being referred or knowing someone at the company
- signals_observed: list of {dimension, signal_type, evidence, turn_index} for new signals only

Confidence transitions are monotonic (never downgrade). Only include a dimension if you have
new evidence that moves it to the same level or higher than current.

Return JSON matching QualificationDelta schema. All fields are optional.
""".strip()


def _to_api_messages(messages: list, context_window: int = 10) -> list[dict]:
    """Convert LangGraph messages (LangChain objects or dicts) to API message format.

    Keeps only the last context_window exchange pairs (visitor + assistant).
    """
    result = []
    for msg in messages:
        if hasattr(msg, "type"):
            # LangChain message object
            if msg.type == "human":
                result.append({"role": "user", "content": msg.content})
            elif msg.type == "ai":
                result.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, dict):
            role = msg.get("role", "")
            if role in ("user", "assistant"):
                result.append({"role": role, "content": msg.get("content", "")})

    # Sliding window: last context_window * 2 messages (N user + N assistant)
    if len(result) > context_window * 2:
        result = result[-(context_window * 2):]

    return result


def _format_retrieval_result(tool_id: str, result: RetrievalResult) -> list[dict]:
    """Format retrieval result as a tool_result message for the LLM."""
    if result.status == "ok" and result.chunks:
        content = "\n\n---\n\n".join(
            f"[Source: {c.source}, score: {c.score:.2f}]\n{c.content}"
            for c in result.chunks
        )
        if result.proactive_case_study:
            content = "[proactive_case_study: true]\n\n" + content
    else:
        content = "[NO RELEVANT RESULTS]"

    return [{"type": "tool_result", "tool_use_id": tool_id, "content": content}]


def _is_hot_lead(state: dict) -> bool:
    qual: QualificationState = state.get("qualification", QualificationState())
    return bool(derive_lead_level(qual, state.get("referral_mentioned", False)) == "hot")


# ── Node implementations ─────────────────────────────────────────────────────

def _make_update_state(llm_client: "BaseLLMClient", context_window: int):
    async def _update_state(state: GraphState) -> dict:
        """Extract qualification signals from the latest visitor message (LLM call)."""
        messages = state.get("messages", [])
        if not messages:
            return {}

        # Find the last user message
        last_user = ""
        for msg in reversed(messages):
            content = msg.content if hasattr(msg, "content") else msg.get("content", "")
            role = msg.type if hasattr(msg, "type") else msg.get("role", "")
            if role in ("human", "user"):
                last_user = content
                break

        if not last_user:
            return {}

        qual = state.get("qualification", QualificationState())
        turn_index = len([m for m in messages if (
            (hasattr(m, "type") and m.type == "human") or
            (isinstance(m, dict) and m.get("role") == "user")
        )])

        user_msg = (
            f"Current qualification state:\n"
            f"problem_fit={qual.problem_fit}, authority_fit={qual.authority_fit}, "
            f"company_fit={qual.company_fit}, timing_fit={qual.timing_fit}, "
            f"is_negative_persona={qual.is_negative_persona}, is_no_fit={qual.is_no_fit}\n\n"
            f"Turn index: {turn_index}\n\n"
            f"New visitor message:\n{last_user}"
        )

        try:
            raw = await llm_client.structured_complete(
                system=_EXTRACTION_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
                schema=_QUALIFICATION_DELTA_SCHEMA,
            )
            delta = QualificationDelta.model_validate(raw)
        except Exception as exc:
            logger.warning("state_extraction_failure: %s", exc)
            return {}

        update: dict = {}

        # Build updated QualificationState from delta
        new_qual = QualificationState(
            problem_fit=delta.problem_fit or "not_detected",
            authority_fit=delta.authority_fit or "not_detected",
            company_fit=delta.company_fit or "not_detected",
            timing_fit=delta.timing_fit or "not_detected",
            is_negative_persona=bool(delta.is_negative_persona),
            is_no_fit=bool(delta.is_no_fit),
            signals_observed=[
                SignalEntry(
                    dimension=s.get("dimension", "problem_fit"),
                    signal_type=s.get("signal_type", "implicit"),
                    evidence=s.get("evidence", ""),
                    turn_index=s.get("turn_index", turn_index),
                )
                for s in (delta.signals_observed or [])
            ],
        )
        # merge_qualification is the reducer — we just return the partial update
        update["qualification"] = new_qual

        if delta.explicit_human_request:
            update["explicit_human_request"] = True
        if delta.visitor_email:
            update["visitor_email"] = delta.visitor_email
        if delta.visitor_name:
            update["visitor_name"] = delta.visitor_name
        if delta.visitor_company:
            update["visitor_company"] = delta.visitor_company
        if delta.visitor_role:
            update["visitor_role"] = delta.visitor_role
        if delta.is_consultant:
            update["is_consultant"] = True
        if delta.referral_mentioned:
            update["referral_mentioned"] = True

        if not state.get("created_at"):
            update["created_at"] = datetime.now(UTC)

        return update

    return _update_state


def _score_router(state: GraphState) -> dict:
    """Evaluate qualification state and set handoff_reason if escalation is needed."""
    if state.get("explicit_human_request"):
        return {"handoff_reason": "explicit_request"}
    if _is_hot_lead(state):
        return {"handoff_reason": "hot_lead"}
    return {}


def _route_after_score_router(state: GraphState) -> str:
    reason = state.get("handoff_reason")
    if reason in ("explicit_request", "hot_lead"):
        return "propose_handoff"
    return "generate_response"


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

            # Pass 2: stream final response with retrieved context
            try:
                full_text = await llm_client.stream(
                    system=system,
                    messages=messages_continued,
                    on_token=lambda t: adispatch_custom_event("token", {"content": t}, config=config),
                )
            except Exception as exc:
                logger.error("llm_generation_failure (pass 2): %s", exc)
                full_text = "I'm having trouble responding right now — can I connect you with the team directly?"
                await adispatch_custom_event("token", {"content": full_text}, config=config)
        else:
            # No tool use — dispatch text as tokens (simulate streaming)
            full_text = response.content
            for word in full_text.split(" "):
                if word:
                    await adispatch_custom_event("token", {"content": word + " "}, config=config)

        return {"messages": [{"role": "assistant", "content": full_text}]}

    return _generate_response


def _make_stall_check(stall_threshold: int):
    def _stall_check(state: GraphState) -> dict:
        new_count = state.get("turn_counter", 0) + 1
        update: dict = {"turn_counter": new_count}
        is_stall = new_count >= stall_threshold and state.get("stage3_proposals_issued", 0) == 0
        if is_stall:
            update["handoff_reason"] = "stall"
        return update

    def _route_after_stall_check(state: GraphState) -> str:
        return "propose_handoff" if state.get("handoff_reason") == "stall" else "write_state"

    return _stall_check, _route_after_stall_check


def _make_propose_handoff(llm_client: "BaseLLMClient"):
    async def _propose_handoff(state: GraphState, config) -> dict:
        """Generate Stage 3 proposal and (stub) dispatch handoff request."""
        reason = state.get("handoff_reason") or "hot_lead"
        in_hours = is_business_hours(same_day_followup=(reason != "stall"))

        system = build_proposal_prompt(state, reason, in_hours)
        api_messages = _to_api_messages(state.get("messages", []))

        try:
            full_text = await llm_client.stream(
                system=system,
                messages=api_messages,
                on_token=lambda t: adispatch_custom_event("token", {"content": t}, config=config),
            )
        except Exception as exc:
            logger.error("propose_handoff llm_failure: %s", exc)
            full_text = "Let me connect you with the team directly. What's the best email to reach you on?"
            await adispatch_custom_event("token", {"content": full_text}, config=config)

        # Phase 2: stub handoff dispatch (Phase 3 implements Slack + CRM)
        qual = state.get("qualification", QualificationState())
        handoff_req = HandoffRequest(
            session_id=state.get("session_id", ""),
            handoff_reason=reason,
            lead_level=derive_lead_level(qual, state.get("referral_mentioned", False)),
            business_hours=in_hours,
            session_state=state,
            triggered_at=datetime.now(UTC),
        )
        await dispatch_handoff(handoff_req)

        proposals_issued = state.get("stage3_proposals_issued", 0) + 1
        return {
            "messages": [{"role": "assistant", "content": full_text}],
            "turn_counter": 0,
            "stage3_proposals_issued": proposals_issued,
            "lead_level": derive_lead_level(qual, state.get("referral_mentioned", False)),
        }

    return _propose_handoff


async def _write_state(state: GraphState) -> dict:
    """Persist analytics event and update last_updated_at timestamp."""
    now = datetime.now(UTC)
    event = AnalyticsEvent(
        name="turn_completed",
        session_id=state.get("session_id", ""),
        timestamp=now,
        payload={
            "lead_level": state.get("lead_level", "cold"),
            "turn_counter": state.get("turn_counter", 0),
            "stage3_proposals_issued": state.get("stage3_proposals_issued", 0),
        },
    )
    await emit_event(event)
    return {"last_updated_at": now}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph(checkpointer, llm_client: "BaseLLMClient"):
    from backend.config import settings

    stall_threshold = settings.stall_turn_threshold
    context_window = settings.context_window_turns

    stall_check_node, route_after_stall = _make_stall_check(stall_threshold)

    builder = StateGraph(GraphState)

    builder.add_node("update_state", _make_update_state(llm_client, context_window))
    builder.add_node("score_router", _score_router)
    builder.add_node("generate_response", _make_generate_response(llm_client, context_window))
    builder.add_node("stall_check", stall_check_node)
    builder.add_node("propose_handoff", _make_propose_handoff(llm_client))
    builder.add_node("write_state", _write_state)

    builder.add_edge(START, "update_state")
    builder.add_edge("update_state", "score_router")
    builder.add_conditional_edges("score_router", _route_after_score_router)
    builder.add_edge("generate_response", "stall_check")
    builder.add_conditional_edges("stall_check", route_after_stall)
    builder.add_edge("propose_handoff", "write_state")
    builder.add_edge("write_state", END)

    return builder.compile(checkpointer=checkpointer)
