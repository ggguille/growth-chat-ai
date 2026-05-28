import json
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
    HTTPErrorResponse,
    SSEDoneEvent,
    SSETokenEvent,
)
from backend.limiter import limiter

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
    initial_state = {
        "messages": [{"role": "user", "content": body.message}],
        "session_id": session_id,
        "turn_count": 0,
    }
    result = await graph.ainvoke(initial_state, config=config)
    content: str = result["messages"][-1].content
    for word in content.split(" "):
        yield _sse(SSETokenEvent(content=word + " ").model_dump())
    done = SSEDoneEvent(
        session_id=session_id,
        lead_level="cold",
        current_stage=1,
        stage3_proposal_issued=False,
        handoff_reason=None,
        turn_count=result["turn_count"],
    )
    yield _sse(done.model_dump())
