"""Prompt assembly functions.

Combines static layers, session state (Layer 7), and optional Stage 3
instructions into a complete system prompt string for each LLM call.
"""
from __future__ import annotations

from .layers import STATIC_LAYERS
from .stage3 import STAGE3_INSTRUCTIONS
from .state import format_qualification_state


def build_system_prompt(state: dict) -> str:
    """Assemble layers 1–7 for generate_response node.

    Layers 8 (RAG chunks) and 9 (conversation history) are handled via
    the messages array passed to the LLM.
    """
    layer_7 = f"\n\n## LAYER 7 — CURRENT SESSION STATE\n\n```json\n{format_qualification_state(state)}\n```\n"
    return STATIC_LAYERS + layer_7


def build_proposal_prompt(state: dict, reason: str, in_hours: bool) -> str:
    """System prompt for propose_handoff node.

    Layers 1–6 (behaviour) + layer 7 (state) + Stage 3 instruction for this
    specific reason × business hours combination.
    """
    base = build_system_prompt(state)
    instruction = STAGE3_INSTRUCTIONS.get(
        (reason, in_hours),
        STAGE3_INSTRUCTIONS[("hot_lead", in_hours)],
    )
    return base + f"\n\n{instruction}\n"
