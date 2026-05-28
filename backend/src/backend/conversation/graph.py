import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

FIXED_RESPONSE = (
    "Hi! I'm the Growth Chat assistant. I help connect you with "
    "Zartis's AI engineering team. What brings you here today?"
)


class GraphState(TypedDict):
    messages: Annotated[list[dict], add_messages]
    session_id: str
    # Additive reducer: router always passes 0 (neutral); node returns 1 (delta).
    turn_count: Annotated[int, operator.add]


def _respond(state: GraphState) -> dict:
    return {
        "messages": [{"role": "assistant", "content": FIXED_RESPONSE}],
        "turn_count": 1,  # delta — added to existing count by the reducer
    }


def build_graph(checkpointer):
    builder = StateGraph(GraphState)
    builder.add_node("respond", _respond)
    builder.add_edge(START, "respond")
    builder.add_edge("respond", END)
    return builder.compile(checkpointer=checkpointer)
