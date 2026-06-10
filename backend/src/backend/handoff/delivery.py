"""dispatch_handoff — orchestrates parallel Slack + CRM delivery with retry and fallback."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

from backend.analytics.events import AnalyticsEvent, emit_event
from backend.handoff.context_packet import ContextPacketGenerationError, generate_context_packet
from backend.handoff.crm import PostgresCRMClient
from backend.handoff.email_fallback import send_fallback_email
from backend.handoff.models import (
    CRMContactPayload,
    CRMDeliveryError,
    CRMLeadPayload,
    HandoffRequest,
    LeadCreationResult,
)
from backend.handoff.record import HandoffRecord, persist_handoff_record
from backend.handoff.slack import build_slack_notifier

log = get_logger("handoff")


class _ChannelOutcome(BaseModel):
    ok: bool
    attempts: int
    last_http_status: int | None = None
    record_id: str | None = None


async def _deliver_channel(
    channel: str,
    fn: Callable[[], Awaitable[Any]],
    backoff_seconds: list[float],
    session_id: str,
) -> _ChannelOutcome:
    """Call fn with retry. Returns _ChannelOutcome regardless of success or failure."""
    last_exc: Exception | None = None
    total_attempts = len(backoff_seconds) + 1

    for attempt in range(1, total_attempts + 1):
        try:
            result = await fn()
        except Exception as exc:
            last_exc = exc
            http_status = getattr(exc, "http_status", None)
            log.warn(
                tel_events.HANDOFF_CHANNEL_FAILURE,
                session_id=session_id,
                channel=channel,
                attempt=attempt,
                http_status=http_status,
                error=sanitize_error(str(exc)),
            )
            if attempt < total_attempts:
                await asyncio.sleep(backoff_seconds[attempt - 1])
            continue

        # fn() succeeded — build outcome outside the retry try/except
        raw_id = getattr(result, "crm_record_id", None)
        record_id = raw_id if isinstance(raw_id, str) else None
        return _ChannelOutcome(ok=True, attempts=attempt, record_id=record_id)

    http_status = getattr(last_exc, "http_status", None) if last_exc else None
    return _ChannelOutcome(ok=False, attempts=total_attempts, last_http_status=http_status)


def _build_crm_payload(packet: Any) -> CRMLeadPayload:
    from backend.handoff.context_packet import ContextPacket

    p: ContextPacket = packet
    return CRMLeadPayload(
        contact=CRMContactPayload(
            email=p.visitor.email,
            name=p.visitor.name,
            company=p.visitor.company,
            role=p.visitor.role,
        ),
        lead_level=p.lead_level,
        handoff_reason=p.handoff_reason,
        session_id=p.session_id,
        triggered_at=p.triggered_at,
        problem_fit=p.qualification.problem_fit,
        authority_fit=p.qualification.authority_fit,
        company_fit=p.qualification.company_fit,
        timing_fit=p.qualification.timing_fit,
        is_consultant=p.qualification.is_consultant,
        referral_mentioned=p.qualification.referral_mentioned,
        summary=p.conversation_summary,
        signals_observed=[s.model_dump() for s in p.signals_observed],
        turn_count=p.turn_count,
    )


async def dispatch_handoff(request: HandoffRequest) -> None:
    """Deliver a handoff to Slack and CRM in parallel; record the audit trail."""
    session_id = request.session_id
    state = request.session_state

    # 1. Generate context packet
    try:
        packet = generate_context_packet(state, request)
    except ContextPacketGenerationError as exc:
        log.error(tel_events.CONTEXT_PACKET_GENERATION_FAILURE, session_id=session_id, error=str(exc))
        return
    except Exception as exc:
        log.error(tel_events.CONTEXT_PACKET_GENERATION_FAILURE, session_id=session_id, error=sanitize_error(str(exc)))
        return

    # 2. Emit dispatched event
    await emit_event(AnalyticsEvent(
        name="handoff_dispatched",
        timestamp=datetime.now(UTC),
        payload={
            "session_id": session_id,
            "handoff_reason": request.handoff_reason,
            "lead_level": request.lead_level,
            "business_hours": request.business_hours,
        },
    ))

    # 3. Deliver in parallel
    from backend.config import settings

    backoff = settings.handoff_retry_backoff
    notifier = build_slack_notifier(settings)
    crm = PostgresCRMClient()

    slack_outcome, crm_outcome = await asyncio.gather(
        _deliver_channel(
            channel="slack",
            fn=lambda: notifier.send_notification(packet, request),
            backoff_seconds=backoff,
            session_id=session_id,
        ),
        _deliver_channel(
            channel="crm",
            fn=lambda: crm.create_lead(_build_crm_payload(packet)),
            backoff_seconds=backoff,
            session_id=session_id,
        ),
    )

    # 4. Determine outcome
    if slack_outcome.ok and crm_outcome.ok:
        outcome = "complete"
    elif slack_outcome.ok or crm_outcome.ok:
        outcome = "partial_failure"
    else:
        outcome = "total_failure"

    # 5. Fallback email on any failure
    fallback_sent = False
    if outcome in ("partial_failure", "total_failure"):
        failed_channels = [
            ch for ch, res in [("slack", slack_outcome), ("crm", crm_outcome)] if not res.ok
        ]
        try:
            await send_fallback_email(packet, request, failed_channels)
            fallback_sent = True
        except Exception:
            pass  # send_fallback_email already logs CRITICAL on failure

    # 6. Persist audit record (best-effort — double-guarded; persist_handoff_record also catches)
    record = HandoffRecord(
        session_id=session_id,
        triggered_at=request.triggered_at,
        lead_level=request.lead_level,
        handoff_reason=request.handoff_reason,
        visitor_email=packet.visitor.email,
        slack_status="ok" if slack_outcome.ok else "failed",
        slack_attempts=slack_outcome.attempts,
        slack_last_http=slack_outcome.last_http_status,
        crm_status="ok" if crm_outcome.ok else "failed",
        crm_attempts=crm_outcome.attempts,
        crm_record_id=crm_outcome.record_id,
        crm_last_http=None,
        fallback_sent=fallback_sent,
        outcome=outcome,
        completed_at=datetime.now(UTC),
    )
    try:
        await persist_handoff_record(record, settings.checkpoint_db_url)
    except Exception as exc:
        log.error(tel_events.HANDOFF_RECORD_WRITE_FAILURE, session_id=session_id, error=sanitize_error(str(exc)))

    # 7. Emit outcome analytics event and structured log
    if outcome == "complete":
        await emit_event(AnalyticsEvent(
            name="handoff_delivered",
            timestamp=datetime.now(UTC),
            payload={"session_id": session_id, "slack_ok": True, "crm_ok": True},
        ))
    elif outcome == "partial_failure":
        failed_channel = "slack" if not slack_outcome.ok else "crm"
        log.error(
            tel_events.HANDOFF_PARTIAL_FAILURE,
            session_id=session_id,
            failed_channel=failed_channel,
            fallback_sent=fallback_sent,
        )
        await emit_event(AnalyticsEvent(
            name="handoff_partial_failure",
            timestamp=datetime.now(UTC),
            payload={"session_id": session_id, "failed_channel": failed_channel},
        ))
    else:
        log.error(tel_events.HANDOFF_TOTAL_FAILURE, session_id=session_id, fallback_sent=fallback_sent)
        await emit_event(AnalyticsEvent(
            name="handoff_total_failure",
            timestamp=datetime.now(UTC),
            payload={"session_id": session_id},
        ))
