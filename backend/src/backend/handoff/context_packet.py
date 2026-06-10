"""ContextPacket — deterministic representation of a handoff event.

Generated from GraphState + HandoffRequest; no LLM, no I/O.
Used by both Slack delivery and CRM insert.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.qualification.models import FitLevel, HandoffReason, LeadLevel, QualificationState, SignalEntry

if TYPE_CHECKING:
    from backend.conversation.models import GraphState
    from backend.handoff.models import HandoffRequest


class ContextPacketGenerationError(Exception):
    pass


class ContextPacketVisitor(BaseModel):
    email: str | None = None
    name: str | None = None
    company: str | None = None
    role: str | None = None


class ContextPacketQualification(BaseModel):
    problem_fit: FitLevel
    authority_fit: FitLevel
    company_fit: FitLevel
    timing_fit: FitLevel
    is_consultant: bool
    referral_mentioned: bool


class ContextPacket(BaseModel):
    session_id: str
    triggered_at: datetime
    lead_level: LeadLevel
    handoff_reason: HandoffReason
    qualification: ContextPacketQualification
    visitor: ContextPacketVisitor
    turn_count: int
    stage3_proposals_issued: int
    signals_observed: list[SignalEntry]
    conversation_summary: str


def build_summary(state: GraphState) -> str:
    """Build a 2–4 sentence deterministic summary from session state."""
    qual: QualificationState = state.get("qualification") or QualificationState()
    role = state.get("visitor_role")
    company = state.get("visitor_company")
    is_consultant = state.get("is_consultant", False)
    messages = state.get("messages", [])
    turn_count = sum(1 for m in messages if getattr(m, "type", "") == "human")

    visitor_desc = "A consultant" if is_consultant else (f"A {role}" if role else "A visitor")
    from_part = f" from {company}" if company else " from an unspecified company"

    problem_signals = [s.evidence for s in qual.signals_observed if s.dimension == "problem_fit"]
    problem_part = f" regarding {problem_signals[0]}" if problem_signals else ""

    turn_word = "turn" if turn_count == 1 else "turns"
    turn_sentence = f"The conversation ran {turn_count} {turn_word}."

    qual_parts = []
    if qual.problem_fit == "confirmed":
        qual_parts.append("problem fit confirmed")
    if qual.authority_fit == "confirmed":
        qual_parts.append("decision authority confirmed")
    if qual.company_fit in ("partially_confirmed", "confirmed"):
        qual_parts.append("company context identified")
    if qual.timing_fit in ("partially_confirmed", "confirmed"):
        qual_parts.append("active timeline indicated")

    qual_sentence = f"Qualification signals: {', '.join(qual_parts)}." if qual_parts else ""

    parts = [f"{visitor_desc}{from_part} reached out{problem_part}.", turn_sentence]
    if qual_sentence:
        parts.append(qual_sentence)
    return " ".join(parts)


def generate_context_packet(state: GraphState, request: HandoffRequest) -> ContextPacket:
    """Build a ContextPacket from session state and handoff request.

    Raises ContextPacketGenerationError if required fields are missing.
    """
    session_id = state.get("session_id", "")
    if not session_id:
        raise ContextPacketGenerationError("session_id is required")
    if request.handoff_reason is None:
        raise ContextPacketGenerationError("handoff_reason is required")
    if request.lead_level not in ("hot", "warm", "cold"):
        raise ContextPacketGenerationError(f"Invalid lead_level: {request.lead_level!r}")

    qual: QualificationState = state.get("qualification") or QualificationState()

    try:
        summary = build_summary(state)
    except Exception:
        summary = "A visitor reached out. Refer to session signals for details."

    messages = state.get("messages", [])
    turn_count = sum(1 for m in messages if getattr(m, "type", "") == "human")

    return ContextPacket(
        session_id=session_id,
        triggered_at=request.triggered_at,
        lead_level=request.lead_level,
        handoff_reason=request.handoff_reason,
        qualification=ContextPacketQualification(
            problem_fit=qual.problem_fit,
            authority_fit=qual.authority_fit,
            company_fit=qual.company_fit,
            timing_fit=qual.timing_fit,
            is_consultant=state.get("is_consultant", False),
            referral_mentioned=state.get("referral_mentioned", False),
        ),
        visitor=ContextPacketVisitor(
            email=state.get("visitor_email"),
            name=state.get("visitor_name"),
            company=state.get("visitor_company"),
            role=state.get("visitor_role"),
        ),
        turn_count=turn_count,
        stage3_proposals_issued=state.get("stage3_proposals_issued", 0),
        signals_observed=qual.signals_observed,
        conversation_summary=summary,
    )
