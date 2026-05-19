from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from backend.qualification.models import FitLevel, HandoffReason, LeadLevel

if TYPE_CHECKING:
    from backend.conversation.models import SessionState


@dataclass
class HandoffRequest:
    session_id: str
    handoff_reason: HandoffReason
    lead_level: LeadLevel
    business_hours: bool
    session_state: SessionState
    triggered_at: datetime


@dataclass
class CRMContactPayload:
    email: str | None
    name: str | None
    company: str | None
    role: str | None


@dataclass
class CRMLeadPayload:
    contact: CRMContactPayload
    lead_level: LeadLevel
    handoff_reason: HandoffReason
    session_id: str
    triggered_at: datetime
    problem_fit: FitLevel
    authority_fit: FitLevel
    company_fit: FitLevel
    timing_fit: FitLevel
    is_consultant: bool
    referral_mentioned: bool
    summary: str
    signals_observed: list[dict]
    turn_count: int


@dataclass
class LeadCreationResult:
    crm_record_id: str
    crm_record_url: str


@dataclass
class CRMDeliveryError(Exception):
    http_status: int | None
    message: str
