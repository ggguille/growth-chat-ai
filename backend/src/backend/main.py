import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.conversation.models import ErrorCode, ErrorDetail, HTTPErrorResponse
from backend.conversation.router import router as conversation_router

_production = os.getenv("APP_ENV", "development") == "production"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(
    title="Growth Chat API",
    lifespan=lifespan,
    docs_url="/docs", # None if _production else "/docs", REVERT when development done
    redoc_url=None if _production else "/redoc",
)
app.include_router(conversation_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=HTTPErrorResponse(
            error=ErrorDetail(code=ErrorCode.INVALID_MESSAGE, message="Invalid request payload")
        ).model_dump(),
    )
