from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import MemorySaver
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.config import settings
from backend.conversation.graph import build_graph
from backend.conversation.models import ErrorCode, ErrorDetail, HTTPErrorResponse
from backend.conversation.router import router as conversation_router
from backend.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.app_env != "development" and settings.checkpoint_db_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with await AsyncPostgresSaver.from_conn_string(settings.checkpoint_db_url) as cp:
            await cp.setup()
            app.state.graph = build_graph(cp)
            app.state.ready = True
            yield
    else:
        cp = MemorySaver()
        app.state.graph = build_graph(cp)
        app.state.ready = True
        yield

    app.state.ready = False


app = FastAPI(
    title="Growth Chat API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
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
    # Return the detail dict directly so error responses match HTTPErrorResponse shape.
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
