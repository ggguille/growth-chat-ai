from typing import Literal

from pydantic import BaseModel, Field

LeadLevel = Literal["hot", "warm", "cold"]
ConversationStage = Literal[1, 2, 3]
FitLevel = Literal["not_detected", "partially_confirmed", "confirmed"]
HandoffReason = Literal["hot_lead", "warm_lead", "explicit_request", "stall", "llm_failure"]

_LEVEL_ORDER: dict[FitLevel, int] = {
    "not_detected": 0,
    "partially_confirmed": 1,
    "confirmed": 2,
}


class SignalEntry(BaseModel):
    dimension: Literal["problem_fit", "authority_fit", "company_fit", "timing_fit"]
    signal_type: Literal["explicit", "implicit"]
    evidence: str
    turn_index: int


class QualificationState(BaseModel):
    problem_fit: FitLevel = "not_detected"
    authority_fit: FitLevel = "not_detected"
    company_fit: FitLevel = "not_detected"
    timing_fit: FitLevel = "not_detected"
    is_negative_persona: bool = False
    is_no_fit: bool = False
    signals_observed: list[SignalEntry] = Field(default_factory=list)


def merge_qualification(current: QualificationState | None, update: QualificationState) -> QualificationState:
    """Monotonic merge: confidence levels only move upward within a session."""
    if current is None:
        return update

    def _max_level(a: FitLevel, b: FitLevel) -> FitLevel:
        return a if _LEVEL_ORDER[a] >= _LEVEL_ORDER[b] else b

    return QualificationState(
        problem_fit=_max_level(current.problem_fit, update.problem_fit),
        authority_fit=_max_level(current.authority_fit, update.authority_fit),
        company_fit=_max_level(current.company_fit, update.company_fit),
        timing_fit=_max_level(current.timing_fit, update.timing_fit),
        is_negative_persona=current.is_negative_persona or update.is_negative_persona,
        is_no_fit=current.is_no_fit or update.is_no_fit,
        signals_observed=current.signals_observed + update.signals_observed,
    )


def derive_lead_level(q: QualificationState, referral_mentioned: bool = False) -> LeadLevel:
    """Derive lead level from qualification state (TRD §4.2)."""
    if q.is_negative_persona or q.is_no_fit:
        return "cold"

    has_third = (
        q.company_fit in ("partially_confirmed", "confirmed")
        or q.timing_fit in ("partially_confirmed", "confirmed")
    )

    # Standard hot threshold
    if q.problem_fit == "confirmed" and q.authority_fit == "confirmed" and has_third:
        return "hot"

    # P3 referral pattern: authority + one more dimension substitutes for problem_fit
    if referral_mentioned and q.authority_fit == "confirmed" and has_third:
        return "hot"

    # Warm: problem confirmed + at least one other dimension partially confirmed
    if q.problem_fit == "confirmed" and any(
        d in ("partially_confirmed", "confirmed")
        for d in (q.authority_fit, q.company_fit, q.timing_fit)
    ):
        return "warm"

    return "cold"


class QualificationDelta(BaseModel):
    """Partial update to QualificationState from update_state LLM call.

    Only include fields where the visitor message contains evidence.
    Omit fields that have no new signal — they are not changed.
    """
    problem_fit: FitLevel | None = None
    authority_fit: FitLevel | None = None
    company_fit: FitLevel | None = None
    timing_fit: FitLevel | None = None
    is_negative_persona: bool | None = None
    is_no_fit: bool | None = None
    explicit_human_request: bool | None = None
    visitor_email: str | None = None
    visitor_name: str | None = None
    visitor_company: str | None = None
    visitor_role: str | None = None
    is_consultant: bool | None = None
    referral_mentioned: bool | None = None
    signals_observed: list[dict] = []
