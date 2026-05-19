from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.qualification.models import (
    ConversationStage,
    HandoffReason,
    LeadLevel,
    QualificationState,
)


# ── SSE event types ──────────────────────────────────────────────────────────

class SSETokenEvent(BaseModel):
    type: Literal["token"] = "token"
    content: str


class SSEDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    session_id: str
    lead_level: LeadLevel
    current_stage: ConversationStage
    stage3_proposal_issued: bool
    handoff_reason: HandoffReason | None
    turn_count: int


class SSEErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


# ── HTTP error responses (pre-stream) ────────────────────────────────────────

class ErrorCode(StrEnum):
    INVALID_MESSAGE = "INVALID_MESSAGE"
    MISSING_ACCEPT_HEADER = "MISSING_ACCEPT_HEADER"
    INVALID_API_KEY = "INVALID_API_KEY"
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorDetail(BaseModel):
    code: str
    message: str
    retry_after_seconds: int | None = None


class HTTPErrorResponse(BaseModel):
    error: ErrorDetail


# ── Request ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)

    @field_validator("message", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


# ── Session state (LangGraph thread state) ───────────────────────────────────

@dataclass
class SessionState:
    session_id: str
    turn_count: int = 0
    lead_level: LeadLevel = "cold"
    current_stage: ConversationStage = 1
    qualification: QualificationState = field(default_factory=QualificationState)
    messages: list[dict] = field(default_factory=list)
