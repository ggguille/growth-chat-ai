import asyncio
import json
import uuid

from telemetry import get_logger, set_session_id
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.analytics import analytics_provider
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

log = get_logger("api")
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

    set_session_id(zgc_session_id)
    graph = request.app.state.graph
    return StreamingResponse(
        _stream(body, zgc_session_id, graph),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _stream(body: ChatRequest, session_id: str, graph) -> AsyncGenerator[str, None]:
    with analytics_provider.request_context(session_id):
        handler = analytics_provider.get_callback_handler()
        config: dict = {"configurable": {"thread_id": session_id}}
        if handler:
            config["callbacks"] = [handler]
        input_state: dict = {
            "session_id": session_id,
            "messages": [{"role": "user", "content": body.message}],
        }

        final_output: dict = {}
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def _heartbeat() -> None:
            # Keeps the Fly.io proxy from treating the upstream connection as idle while
            # the LLM pipeline (two sequential Anthropic calls + optional RAG) runs before
            # the first token is emitted. SSE comment lines are ignored by clients.
            while True:
                await asyncio.sleep(15)
                queue.put_nowait(": heartbeat\n\n")

        async def _run_graph() -> None:
            nonlocal final_output
            try:
                async for event in graph.astream_events(input_state, config=config, version="v2"):
                    kind = event.get("event", "")
                    if kind == "on_custom_event" and event.get("name") == "token":
                        content = event.get("data", {}).get("content", "")
                        if content:
                            queue.put_nowait(_sse(SSETokenEvent(content=content).model_dump()))
                    elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                        output = event.get("data", {}).get("output")
                        if isinstance(output, dict):
                            final_output = output
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("stream_error", session_id=session_id, error=str(exc))
            finally:
                queue.put_nowait(None)  # sentinel — always unblocks the consumer

        hb_task = asyncio.create_task(_heartbeat())
        graph_task = asyncio.create_task(_run_graph())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        except asyncio.CancelledError:
            log.warn("stream_cancelled", session_id=session_id)
            return  # client disconnected; no done event
        finally:
            hb_task.cancel()
            graph_task.cancel()

        done = SSEDoneEvent(
            session_id=session_id,
            lead_level=final_output.get("lead_level", "cold"),
            current_stage=final_output.get("current_stage", 1),
            stage3_proposal_issued=bool(final_output.get("stage3_proposals_issued", 0)),
            handoff_reason=final_output.get("handoff_reason"),
            turn_count=final_output.get("turn_counter", 0),
        )
        yield _sse(done.model_dump())
