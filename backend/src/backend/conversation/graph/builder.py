"""build_graph — assembles the LangGraph StateGraph from its component nodes.

6-node StateGraph:
  update_state → score_router → generate_response → stall_check
                ↘ propose_handoff ↗               ↘ propose_handoff
                                   → write_state → END

See TRD §3.1 and action-plan.md Phase 2.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from backend.conversation.models import GraphState

from .nodes.generate_response import _make_generate_response
from .nodes.propose_handoff import _make_propose_handoff
from .nodes.update_state import _make_update_state
from .nodes.write_state import _make_stall_check, _write_state
from .routing import _route_after_score_router, _score_router

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient


def build_graph(checkpointer, llm_client: "BaseLLMClient"):
    from backend.config import settings  # noqa: PLC0415 — avoids circular import at module init

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
