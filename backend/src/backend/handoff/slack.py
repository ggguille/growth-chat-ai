"""Slack notifier — Protocol + NullSlackNotifier (Phase 3) + WebhookSlackNotifier stub (future).

NullSlackNotifier is used when SLACK_WEBHOOK_URL is absent; it logs the event and
returns successfully. WebhookSlackNotifier (real Block Kit + retry) is implemented
in a future phase when Slack delivery is activated.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from telemetry import get_logger
from telemetry import events as tel_events

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.handoff.context_packet import ContextPacket
    from backend.handoff.models import HandoffRequest

log = get_logger("handoff")


class SlackDeliveryError(Exception):
    def __init__(self, http_status: int | None, message: str) -> None:
        self.http_status = http_status
        self.message = message
        super().__init__(message)


@runtime_checkable
class SlackNotifier(Protocol):
    async def send_notification(self, context_packet: ContextPacket, request: HandoffRequest) -> None: ...


class NullSlackNotifier:
    """No-op notifier used when SLACK_WEBHOOK_URL is absent."""

    async def send_notification(self, context_packet: ContextPacket, request: HandoffRequest) -> None:
        log.info(
            tel_events.SLACK_NOTIFICATION_SKIPPED,
            session_id=context_packet.session_id,
            lead_level=context_packet.lead_level,
            handoff_reason=context_packet.handoff_reason,
            business_hours=request.business_hours,
        )


class WebhookSlackNotifier:
    """Real Slack webhook notifier (Block Kit + retry). Implemented in a future phase."""

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    async def send_notification(self, context_packet: ContextPacket, request: HandoffRequest) -> None:
        # TODO: implement real Slack webhook delivery once Block Kit payload is designed
        # import httpx
        # payload = _build_block_kit_payload(context_packet, request)
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(self._webhook_url, json=payload)
        #     if response.status_code != 200:
        #         raise SlackDeliveryError(response.status_code, response.text)
        log.info(
            tel_events.SLACK_NOTIFICATION_SKIPPED,
            session_id=context_packet.session_id,
            lead_level=context_packet.lead_level,
            handoff_reason=context_packet.handoff_reason,
            business_hours=request.business_hours,
        )


def build_slack_notifier(settings: Settings) -> SlackNotifier:
    """Return the appropriate notifier based on config."""
    if settings.slack_webhook_url:
        return WebhookSlackNotifier(settings.slack_webhook_url)
    return NullSlackNotifier()
