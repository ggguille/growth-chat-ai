"""Tests for slack.py — SlackNotifier protocol and NullSlackNotifier."""
from datetime import UTC, datetime

from backend.handoff.context_packet import ContextPacket, ContextPacketQualification, ContextPacketVisitor
from backend.handoff.models import HandoffRequest
from backend.handoff.slack import NullSlackNotifier, SlackNotifier, WebhookSlackNotifier, build_slack_notifier
from backend.qualification.models import QualificationState


def _make_packet() -> ContextPacket:
    return ContextPacket(
        session_id="sess-001",
        triggered_at=datetime.now(UTC),
        lead_level="hot",
        handoff_reason="hot_lead",
        qualification=ContextPacketQualification(
            problem_fit="confirmed",
            authority_fit="confirmed",
            company_fit="not_detected",
            timing_fit="not_detected",
            is_consultant=False,
            referral_mentioned=False,
        ),
        visitor=ContextPacketVisitor(email="test@example.com", company="Acme"),
        turn_count=3,
        stage3_proposals_issued=1,
        signals_observed=[],
        conversation_summary="Test summary.",
    )


def _make_request(**kwargs) -> HandoffRequest:
    defaults = {
        "session_id": "sess-001",
        "handoff_reason": "hot_lead",
        "lead_level": "hot",
        "business_hours": True,
        "session_state": {},
        "triggered_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return HandoffRequest(**defaults)


# ── NullSlackNotifier ────────────────────────────────────────────────────────

async def test_null_notifier_completes_without_error():
    notifier = NullSlackNotifier()
    await notifier.send_notification(_make_packet(), _make_request())


async def test_null_notifier_is_slack_notifier():
    notifier = NullSlackNotifier()
    assert isinstance(notifier, SlackNotifier)


async def test_null_notifier_logs_skipped_event(caplog):
    import logging
    notifier = NullSlackNotifier()
    with caplog.at_level(logging.INFO):
        await notifier.send_notification(_make_packet(), _make_request())
    assert any("slack_notification_skipped" in r.message for r in caplog.records)


# ── build_slack_notifier factory ─────────────────────────────────────────────

def test_build_slack_notifier_returns_null_when_url_absent(monkeypatch):
    from backend import config
    monkeypatch.setattr(config.settings, "slack_webhook_url", "")
    notifier = build_slack_notifier(config.settings)
    assert isinstance(notifier, NullSlackNotifier)


def test_build_slack_notifier_returns_webhook_when_url_set(monkeypatch):
    from backend import config
    monkeypatch.setattr(config.settings, "slack_webhook_url", "https://hooks.slack.com/fake")
    notifier = build_slack_notifier(config.settings)
    assert isinstance(notifier, WebhookSlackNotifier)


# ── WebhookSlackNotifier stub ─────────────────────────────────────────────────

async def test_webhook_notifier_logs_skipped_without_error(caplog):
    import logging
    notifier = WebhookSlackNotifier("https://hooks.slack.com/fake")
    with caplog.at_level(logging.INFO):
        await notifier.send_notification(_make_packet(), _make_request())
    assert any("slack_notification_skipped" in r.message for r in caplog.records)
