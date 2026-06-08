import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

os.environ["OTEL_SERVICE_NAME"] = os.environ.get("OTEL_SERVICE_NAME") or "growth-chat-api"

from telemetry import configure_logging

configure_logging()

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.config import settings
from backend.conversation.graph import build_graph
from backend.conversation.models import ErrorCode, ErrorDetail, HTTPErrorResponse
from backend.conversation.router import router as conversation_router
from backend.limiter import limiter
from backend.llm.factory import create_llm_client


_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("backend.qualification.models", "QualificationState"),
        ("backend.qualification.models", "SignalEntry"),
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from backend.analytics.langfuse_client import initialize_langfuse
    initialize_langfuse()
    llm_client = create_llm_client(settings)

    if settings.app_env != "development" and settings.checkpoint_db_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with await AsyncPostgresSaver.from_conn_string(settings.checkpoint_db_url, serde=_SERDE) as cp:
            await cp.setup()
            app.state.graph = build_graph(cp, llm_client)
            app.state.ready = True
            yield
    else:
        cp = MemorySaver(serde=_SERDE)
        app.state.graph = build_graph(cp, llm_client)
        app.state.ready = True
        yield

    app.state.ready = False
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        try:
            from langfuse import get_client
            get_client().flush()
        except Exception:
            pass


app = FastAPI(
    title="Growth Chat API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "Accept", "ZGC-Session-ID", "ZGC-API-KEY"],
    allow_credentials=False,
)
app.include_router(conversation_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    if getattr(request.app.state, "ready", False):
        return JSONResponse({"status": "ready"})
    return JSONResponse({"status": "not_ready"}, status_code=503)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=HTTPErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.RATE_LIMITED,
                message="Rate limit exceeded. Try again in 5 minutes.",
                retry_after_seconds=300,
            )
        ).model_dump(),
        headers={"Retry-After": "300"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=HTTPErrorResponse(
            error=ErrorDetail(code=ErrorCode.INVALID_MESSAGE, message="Invalid request payload")
        ).model_dump(),
    )
