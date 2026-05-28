from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.conversation.graph import FIXED_RESPONSE, build_graph


async def test_first_turn_returns_assistant_message():
    graph = build_graph(MemorySaver())
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "Hello"}], "session_id": "t0", "turn_count": 0},
        config={"configurable": {"thread_id": "t0"}},
    )
    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    assert last.content == FIXED_RESPONSE


async def test_first_turn_sets_turn_count_to_one():
    graph = build_graph(MemorySaver())
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "Hello"}], "session_id": "t1", "turn_count": 0},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert result["turn_count"] == 1


async def test_second_turn_increments_turn_count():
    graph = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t2"}}
    await graph.ainvoke(
        {"messages": [{"role": "user", "content": "Hi"}], "session_id": "t2", "turn_count": 0},
        config=cfg,
    )
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "Tell me more"}], "session_id": "t2", "turn_count": 0},
        config=cfg,
    )
    assert result["turn_count"] == 2


async def test_different_threads_are_isolated():
    graph = build_graph(MemorySaver())
    r1 = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "A"}], "session_id": "ta", "turn_count": 0},
        config={"configurable": {"thread_id": "ta"}},
    )
    r2 = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "B"}], "session_id": "tb", "turn_count": 0},
        config={"configurable": {"thread_id": "tb"}},
    )
    assert r1["turn_count"] == r2["turn_count"] == 1
