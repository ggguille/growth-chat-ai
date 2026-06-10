"""HandoffRecord — audit trail for handoff delivery attempts."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

from backend.qualification.models import HandoffReason, LeadLevel

log = get_logger("handoff")


class HandoffRecord(BaseModel):
    session_id: str
    triggered_at: datetime
    lead_level: LeadLevel
    handoff_reason: HandoffReason
    visitor_email: str | None = None
    slack_status: Literal["ok", "failed"]
    slack_attempts: int
    slack_last_http: int | None = None
    crm_status: Literal["ok", "failed"]
    crm_attempts: int
    crm_record_id: str | None = None
    crm_last_http: int | None = None
    fallback_sent: bool = False
    outcome: Literal["complete", "partial_failure", "total_failure"]
    completed_at: datetime


async def persist_handoff_record(record: HandoffRecord, db_url: str) -> None:
    """Insert a HandoffRecord into handoff_records. Best-effort — never propagates."""
    if not db_url:
        log.error(tel_events.HANDOFF_RECORD_WRITE_FAILURE, session_id=record.session_id, error="CHECKPOINT_DB_URL not configured")
        return

    # Use synchronous psycopg via asyncio.to_thread — avoids ProactorEventLoop
    # incompatibility with psycopg async on Windows (same pattern as email_fallback.py).
    def _insert() -> None:
        import psycopg

        with psycopg.connect(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO handoff_records (
                        session_id, triggered_at, lead_level, handoff_reason, visitor_email,
                        slack_status, slack_attempts, slack_last_http,
                        crm_status, crm_attempts, crm_record_id, crm_last_http,
                        fallback_sent, outcome, completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.session_id,
                        record.triggered_at,
                        record.lead_level,
                        record.handoff_reason,
                        record.visitor_email,
                        record.slack_status,
                        record.slack_attempts,
                        record.slack_last_http,
                        record.crm_status,
                        record.crm_attempts,
                        record.crm_record_id,
                        record.crm_last_http,
                        record.fallback_sent,
                        record.outcome,
                        record.completed_at,
                    ),
                )

    try:
        await asyncio.to_thread(_insert)
    except Exception as exc:
        log.error(
            tel_events.HANDOFF_RECORD_WRITE_FAILURE,
            session_id=record.session_id,
            error=sanitize_error(str(exc)),
        )
