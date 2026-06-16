from datetime import datetime
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, field_validator

from backend.qualification.models import (
    ConversationStage,
    HandoffReason,
    LeadLevel,
    QualificationState,
    merge_qualification,
)


# ── LangGraph graph state ────────────────────────────────────────────────────

class GraphState(TypedDict, total=False):
    """Full session state (TRD §4.1 SessionState schema).

    total=False so nodes can return partial updates.
    All fields accessed via state.get(field, default) inside nodes.
    """
    # Session identity
    session_id: str
    created_at: datetime | None
    last_updated_at: datetime | None

    # Conversation history — LangGraph add_messages reducer (append-only merge)
    messages: Annotated[list, add_messages]

    # Qualification — monotonic merge reducer (confidence levels never downgrade)
    qualification: Annotated[QualificationState, merge_qualification]

    # Session control
    lead_level: LeadLevel
    current_stage: ConversationStage
    turn_counter: int
    stage3_proposals_issued: int
    explicit_human_request: bool

    # Visitor data
    visitor_email: str | None
    visitor_name: str | None
    visitor_company: str | None
    visitor_role: str | None
    is_consultant: bool
    referral_mentioned: bool
    stage3_declined: bool

    # Session outcome
    handoff_triggered: bool
    handoff_reason: HandoffReason | None
    termination_type: str | None


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

class ErrorCode:
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
