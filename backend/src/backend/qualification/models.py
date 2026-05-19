from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LeadLevel = Literal["hot", "warm", "cold"]
ConversationStage = Literal[1, 2, 3]
FitLevel = Literal["not_detected", "partially_confirmed", "confirmed"]
HandoffReason = Literal["hot_lead", "explicit_request", "stall", "llm_failure"]


@dataclass
class QualificationState:
    problem_fit: FitLevel = "not_detected"
    authority_fit: FitLevel = "not_detected"
    company_fit: FitLevel = "not_detected"
    timing_fit: FitLevel = "not_detected"
    is_consultant: bool = False
    referral_mentioned: bool = False
