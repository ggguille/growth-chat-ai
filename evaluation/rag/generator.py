"""Generate grounded LLM answers for RAGAS sample construction.

Uses Claude Haiku (the project's standard inference model, per ADR-001) with a
minimal RAG grounding prompt — separate from the full agent system prompt so the
generator isolates retrieval quality from conversation-layer effects.

Environment variables
---------------------
ANTHROPIC_API_KEY
    Required.  Set in ``evaluation/.env`` or as a CI secret.
ANTHROPIC_MODEL_NAME
    Claude model to use.  Default: ``claude-haiku-4-5-20251001``.
"""

from __future__ import annotations

import os

import anthropic

_SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions about an AI engineering company called Zartis.
Answer ONLY from the provided context excerpts below.
If the context does not contain enough information to answer the question, respond:
"I don't have specific information about that."
Do not fabricate facts or draw on knowledge outside the provided context.
Keep answers concise (2-4 sentences)."""

_NO_CONTEXT_PROMPT = """\
You are a helpful assistant that answers questions about an AI engineering company called Zartis.
No relevant information was found in the knowledge base for this question.
Respond by acknowledging that you don't have that specific information.
Keep the response to one sentence."""


def generate_answer(question: str, contexts: list[str]) -> str:
    """Generate a grounded answer for *question* given *contexts*.

    Args:
        question: The visitor question.
        contexts: Retrieved chunk content strings.  Pass an empty list when
                  no relevant chunk is expected (``no_relevant_chunk`` items).

    Returns:
        The model's text response.
    """
    model = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-haiku-4-5-20251001")
    client = anthropic.Anthropic()

    if contexts:
        context_block = "\n\n---\n\n".join(f"Context {i + 1}:\n{c}" for i, c in enumerate(contexts))
        user_content = f"{context_block}\n\nQuestion: {question}"
        system = _SYSTEM_PROMPT
    else:
        user_content = f"Question: {question}"
        system = _NO_CONTEXT_PROMPT

    message = client.messages.create(
        model=model,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text
