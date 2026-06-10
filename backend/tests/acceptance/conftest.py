import os
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

# Load backend/.env for local development — no-op if the file is absent (CI injects secrets directly).
load_dotenv(Path(__file__).parents[2] / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session", autouse=True)
async def require_backend():
    try:
        async with httpx.AsyncClient(base_url=BACKEND_URL) as client:
            r = await client.get("/health", timeout=3.0)
            r.raise_for_status()
    except Exception:
        pytest.skip(f"Backend not reachable at {BACKEND_URL}")
