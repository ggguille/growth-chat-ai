import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.conversation.models import (
    ChatRequest,
    ErrorCode,
    ErrorDetail,
    GraphState,
    HTTPErrorResponse,
    SSEDoneEvent,
    SSETokenEvent,
)
from backend.limiter import limiter

_log = logging.getLogger(__name__)
router = APIRouter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value, version=4)
        return str(parsed) == value.lower()
    except ValueError:
        return False


@router.post("/chat")
@limiter.limit("20/5 minutes")
async def chat(
    request: Request,
    body: ChatRequest,
    zgc_session_id: Annotated[str, Header(alias="ZGC-Session-ID")],
    zgc_api_key: Annotated[str, Header(alias="ZGC-API-KEY")],
    accept: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    if accept != "text/event-stream":
        raise HTTPException(
            status_code=400,
            detail=HTTPErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.MISSING_ACCEPT_HEADER,
                    message="Accept: text/event-stream is required",
                )
            ).model_dump(),
        )
    if zgc_api_key != settings.zgc_api_key:
        raise HTTPException(
            status_code=401,
            detail=HTTPErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INVALID_API_KEY,
                    message="Invalid or missing API key",
                )
            ).model_dump(),
        )

    if not _is_uuid4(zgc_session_id):
        raise HTTPException(
            status_code=400,
            detail=HTTPErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.INVALID_MESSAGE,
                    message="ZGC-Session-ID must be a valid UUID v4",
                )
            ).model_dump(),
        )

    graph = request.app.state.graph
    return StreamingResponse(
        _stream(body, zgc_session_id, graph),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _stream(body: ChatRequest, session_id: str, graph) -> AsyncGenerator[str, None]:
    config = {"configurable": {"thread_id": session_id}}
    input_state: dict = {
        "session_id": session_id,
        "messages": [{"role": "user", "content": body.message}],
    }

    final_output: dict = {}

    try:
        async for event in graph.astream_events(input_state, config=config, version="v2"):
            kind = event.get("event", "")

            if kind == "on_custom_event" and event.get("name") == "token":
                content = event.get("data", {}).get("content", "")
                if content:
                    yield _sse(SSETokenEvent(content=content).model_dump())

            elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                output = event.get("data", {}).get("output")
                if isinstance(output, dict):
                    final_output = output

    except asyncio.CancelledError:
        _log.warning("stream cancelled for session %s", session_id)
        return  # client disconnected; let the generator exhaust cleanly without a done event
    except Exception:
        _log.exception("stream error for session %s", session_id)

    done = SSEDoneEvent(
        session_id=session_id,
        lead_level=final_output.get("lead_level", "cold"),
        current_stage=final_output.get("current_stage", 1),
        stage3_proposal_issued=bool(final_output.get("stage3_proposals_issued", 0)),
        handoff_reason=final_output.get("handoff_reason"),
        turn_count=final_output.get("turn_counter", 0),
    )
    yield _sse(done.model_dump())
