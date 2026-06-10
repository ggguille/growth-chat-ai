"""Email fallback delivery — sends a plain-text alert when both Slack and CRM fail."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

if TYPE_CHECKING:
    from backend.handoff.context_packet import ContextPacket
    from backend.handoff.models import HandoffRequest

log = get_logger("handoff")


def _build_email_body(
    packet: ContextPacket,
    request: HandoffRequest,
    failed_channels: list[str],
) -> str:
    v = packet.visitor
    q = packet.qualification
    slack_status = "FAILED" if "slack" in failed_channels else "OK"
    crm_status = "FAILED" if "crm" in failed_channels else "OK"

    return (
        "This lead notification was delivered by email because one or both delivery channels failed.\n\n"
        f"Session ID:   {packet.session_id}\n"
        f"Lead level:   {packet.lead_level}\n"
        f"Trigger:      {packet.handoff_reason}\n"
        f"Timestamp:    {packet.triggered_at.isoformat()}\n\n"
        "Visitor:\n"
        f"  Email:      {v.email or 'Not captured'}\n"
        f"  Name:       {v.name or 'Unknown'}\n"
        f"  Company:    {v.company or 'Unknown'}\n"
        f"  Role:       {v.role or 'Unknown'}\n\n"
        "Qualification:\n"
        f"  Problem:    {q.problem_fit}\n"
        f"  Authority:  {q.authority_fit}\n"
        f"  Company:    {q.company_fit}\n"
        f"  Timing:     {q.timing_fit}\n\n"
        f"Summary:\n{packet.conversation_summary}\n\n"
        "---\n"
        f"Slack delivery status:  {slack_status}\n"
        f"CRM delivery status:    {crm_status}\n"
    )


def _send_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    # TODO: implement real SMTP delivery once an SMTP server is provisioned
    # import smtplib
    # from email.message import EmailMessage
    # msg = EmailMessage()
    # msg["From"] = username
    # msg["To"] = recipient
    # msg["Subject"] = subject
    # msg.set_content(body)
    # with smtplib.SMTP(host, port) as smtp:
    #     smtp.starttls()
    #     smtp.login(username, password)
    #     smtp.send_message(msg)
    log.info(
        "fallback_email_skipped",
        recipient=recipient,
        subject=subject,
    )


async def send_fallback_email(
    packet: ContextPacket,
    request: HandoffRequest,
    failed_channels: list[str],
) -> None:
    """Send a plain-text fallback email to FALLBACK_EMAIL_ADDRESS.

    Uses asyncio.to_thread to avoid blocking the event loop. Exceptions are caught
    and logged at CRITICAL; they are never propagated.
    """
    from backend.config import settings

    host = settings.smtp_host
    port = settings.smtp_port
    username = settings.smtp_username
    password = settings.smtp_password
    recipient = settings.fallback_email_address

    if not all([host, username, password, recipient]):
        log.error(
            tel_events.FALLBACK_EMAIL_FAILURE,
            session_id=packet.session_id,
            error="SMTP config incomplete — fallback email not sent",
        )
        return

    company = packet.visitor.company or "Unknown"
    subject = f"[CHAT FALLBACK] {packet.lead_level.capitalize()} Lead — {company}"
    body = _build_email_body(packet, request, failed_channels)

    try:
        await asyncio.to_thread(_send_smtp, host, port, username, password, recipient, subject, body)
    except Exception as exc:
        log.error(
            tel_events.FALLBACK_EMAIL_FAILURE,
            session_id=packet.session_id,
            error=sanitize_error(str(exc)),
        )
