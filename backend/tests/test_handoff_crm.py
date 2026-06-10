"""Tests for PostgresCRMClient — mocks the psycopg async connection."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.handoff.crm import PostgresCRMClient
from backend.handoff.models import CRMContactPayload, CRMDeliveryError, CRMLeadPayload


def _make_payload(**kwargs) -> CRMLeadPayload:
    defaults = {
        "contact": CRMContactPayload(email="alice@example.com", name="Alice", company="Acme", role="CTO"),
        "lead_level": "hot",
        "handoff_reason": "hot_lead",
        "session_id": "sess-001",
        "triggered_at": datetime.now(UTC),
        "problem_fit": "confirmed",
        "authority_fit": "confirmed",
        "company_fit": "not_detected",
        "timing_fit": "not_detected",
        "is_consultant": False,
        "referral_mentioned": False,
        "summary": "Test summary.",
        "signals_observed": [],
        "turn_count": 3,
    }
    defaults.update(kwargs)
    return CRMLeadPayload(**defaults)


def _mock_psycopg_connection(row_id: int = 42):
    """Return a context manager mock that yields a connection with a cursor returning row_id."""
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchone = AsyncMock(return_value=(row_id,))
    cur.__aenter__ = AsyncMock(return_value=cur)
    cur.__aexit__ = AsyncMock(return_value=False)

    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cur)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    connect_coro = AsyncMock(return_value=conn)
    return connect_coro, cur


async def test_create_lead_returns_record_id(monkeypatch):
    connect_coro, _ = _mock_psycopg_connection(row_id=99)
    monkeypatch.setattr("backend.config.settings.checkpoint_db_url", "postgresql://fake")

    with patch("psycopg.AsyncConnection.connect", connect_coro):
        client = PostgresCRMClient()
        result = await client.create_lead(_make_payload())

    assert result.crm_record_id == "99"


async def test_create_lead_crm_record_url_is_empty_in_v1(monkeypatch):
    connect_coro, _ = _mock_psycopg_connection(row_id=1)
    monkeypatch.setattr("backend.config.settings.checkpoint_db_url", "postgresql://fake")

    with patch("psycopg.AsyncConnection.connect", connect_coro):
        client = PostgresCRMClient()
        result = await client.create_lead(_make_payload())

    assert result.crm_record_url == ""


async def test_create_lead_raises_crm_delivery_error_on_db_failure(monkeypatch):
    monkeypatch.setattr("backend.config.settings.checkpoint_db_url", "postgresql://fake")

    async def boom(*args, **kwargs):
        raise RuntimeError("connection refused")

    with patch("psycopg.AsyncConnection.connect", boom):
        client = PostgresCRMClient()
        with pytest.raises(CRMDeliveryError) as exc_info:
            await client.create_lead(_make_payload())

    assert exc_info.value.http_status is None
    assert "connection refused" in exc_info.value.message


async def test_create_lead_raises_when_db_url_not_configured(monkeypatch):
    monkeypatch.setattr("backend.config.settings.checkpoint_db_url", "")
    client = PostgresCRMClient()
    with pytest.raises(CRMDeliveryError) as exc_info:
        await client.create_lead(_make_payload())
    assert "CHECKPOINT_DB_URL" in exc_info.value.message
