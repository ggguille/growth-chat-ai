"""Message formatting utilities and tool definitions for the LLM API layer.

Handles conversion between LangGraph message objects, API dicts, and tool
result blocks. No internal graph/ imports — dependency leaf.
"""
from __future__ import annotations

from backend.knowledge.retrieval import RetrievalResult

# ── Tool definition ───────────────────────────────────────────────────────────

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


# ── Message utilities ─────────────────────────────────────────────────────────

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
