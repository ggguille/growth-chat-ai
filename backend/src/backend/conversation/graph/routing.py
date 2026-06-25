"""Score routing and lead qualification logic for the conversation graph.

Contains the _score_router node, conditional edge function, and the
_is_hot_lead helper. Authority detection lives here because it is the
primary input to the hot-lead threshold decision.

No internal graph/ imports — dependency leaf.
"""
from __future__ import annotations

from backend.conversation.models import GraphState
from backend.qualification.models import QualificationState, derive_lead_level

# ── Authority detection ───────────────────────────────────────────────────────

# Rule-based authority override: explicit C-suite/VP/founder phrases are detected
# deterministically and used to ensure "confirmed" authority regardless of LLM output.
_AUTHORITY_PHRASES = frozenset([
    "i'm the cto", "i am the cto",
    "i'm the ceo", "i am the ceo",
    "i'm the vp", "i am the vp", "i'm a vp", "i am a vp",
    "i'm the founder", "i am the founder",
    "i'm the head of", "i am the head of",
    "i'm the chief", "i am the chief",
    "i have sign-off", "i have budget authority",
    "i make the call", "i make the decision",
    "i'm the decision-maker", "i am the decision-maker",
])


def _has_explicit_authority(message: str) -> bool:
    """True if message contains a clear, explicit authority self-identification."""
    lower = message.lower()
    return any(phrase in lower for phrase in _AUTHORITY_PHRASES)


# ── Lead qualification ────────────────────────────────────────────────────────

def _is_hot_lead(state: dict) -> bool:
    qual: QualificationState = state.get("qualification", QualificationState())

    # Safety guard: if the last user message contains an explicit authority signal but
    # the extracted state hasn't reflected it yet (transient lag between update_state
    # and score_router), promote authority for this routing decision only.
    if qual.authority_fit != "confirmed":
        messages = state.get("messages", [])
        for msg in reversed(messages):
            content = msg.content if hasattr(msg, "content") else msg.get("content", "")
            role = msg.type if hasattr(msg, "type") else msg.get("role", "")
            if role in ("human", "user"):
                if _has_explicit_authority(content):
                    qual = QualificationState(
                        problem_fit=qual.problem_fit,
                        authority_fit="confirmed",
                        company_fit=qual.company_fit,
                        timing_fit=qual.timing_fit,
                        is_negative_persona=qual.is_negative_persona,
                        is_no_fit=qual.is_no_fit,
                    )
                break

    return bool(derive_lead_level(qual, state.get("referral_mentioned", False)) == "hot")


# ── Graph routing nodes ───────────────────────────────────────────────────────

def _score_router(state: GraphState) -> dict:
    """Evaluate qualification state and set handoff_reason if escalation is needed."""
    if state.get("explicit_human_request"):
        return {"handoff_reason": "explicit_request"}

    # N1/N2 guard: never escalate through qualification-based routes (stall, hot_lead, warm_lead).
    # derive_lead_level already returns "cold" for is_negative_persona, but this explicit guard
    # prevents future stall-path regressions and signals intent clearly. (TC-ADV-013, TC-ADV-014)
    stored_qual: QualificationState = state.get("qualification", QualificationState())
    if stored_qual.is_negative_persona or stored_qual.is_no_fit:
        return {}

    # Consultant guard: when is_consultant is set and no Stage 3 proposal has been issued yet,
    # route to generate_response so EC-03 guidance can ask about the client's context (TC-ADV-015).
    if state.get("is_consultant") and state.get("stage3_proposals_issued", 0) == 0:
        return {}

    # Problem-fit guard: never escalate unless problem_fit is confirmed in the stored state.
    # LLM extraction can over-infer problem_fit from urgency/budget/authority signals alone (TC-ADV-018).
    # P3 referral path is exempted — referral substitutes for problem_fit (CDD §2.1).
    if stored_qual.problem_fit != "confirmed" and not state.get("referral_mentioned"):
        return {}

    if _is_hot_lead(state):
        # Downgrade to warm_lead when timing is not fully confirmed and no referral urgency.
        # "not_detected" and "partially_confirmed" both indicate no committed budget/deadline.
        # LLM extraction can set "partially_confirmed" for weak urgency signals like
        # "board knows about it but we haven't committed budget" — those should stay warm.
        # Only "confirmed" timing (explicit Q3 deadline, approved budget) justifies hot_lead.
        if stored_qual.timing_fit != "confirmed" and not state.get("referral_mentioned"):
            return {"handoff_reason": "warm_lead"}
        return {"handoff_reason": "hot_lead"}
    return {}


def _route_after_score_router(state: GraphState) -> str:
    reason = state.get("handoff_reason")
    if reason in ("explicit_request", "hot_lead", "warm_lead"):
        # Visitor declined a Stage 3 proposal → return to conversation, do not re-propose.
        if state.get("stage3_declined"):
            return "generate_response"
        # Email already captured after a Stage 3 proposal → clean close, not re-proposal
        if state.get("stage3_proposals_issued", 0) > 0 and state.get("visitor_email"):
            return "generate_response"
        return "propose_handoff"
    return "generate_response"
