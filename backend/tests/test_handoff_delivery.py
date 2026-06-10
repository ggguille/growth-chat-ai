"""Tests for dispatch_handoff — delivery orchestration with mocked channels."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.handoff.delivery import _deliver_channel, dispatch_handoff
from backend.handoff.models import CRMDeliveryError, HandoffRequest, LeadCreationResult
from backend.handoff.slack import SlackDeliveryError
from backend.qualification.models import QualificationState


def _make_request(session_id: str = "sess-001", **kwargs) -> HandoffRequest:
    state = {
        "session_id": session_id,
        "qualification": QualificationState(problem_fit="confirmed", authority_fit="confirmed"),
        "visitor_email": "alice@example.com",
        "visitor_name": "Alice",
        "visitor_company": "Acme",
        "visitor_role": "CTO",
        "is_consultant": False,
        "referral_mentioned": False,
        "turn_counter": 0,
        "stage3_proposals_issued": 1,
        "messages": [HumanMessage(content="Hi"), AIMessage(content="Hello")],
        "handoff_triggered": False,
        "handoff_reason": "hot_lead",
    }
    defaults = {
        "session_id": session_id,
        "handoff_reason": "hot_lead",
        "lead_level": "hot",
        "business_hours": True,
        "session_state": state,
        "triggered_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return HandoffRequest(**defaults)


def _mock_notifier(raises: Exception | None = None) -> AsyncMock:
    """Build a mock SlackNotifier whose send_notification either succeeds or raises."""
    notifier = AsyncMock()
    if raises:
        notifier.send_notification = AsyncMock(side_effect=raises)
    else:
        notifier.send_notification = AsyncMock(return_value=None)
    return notifier


def _patch_slack(notifier=None):
    if notifier is None:
        notifier = _mock_notifier()
    return patch("backend.handoff.delivery.build_slack_notifier", return_value=notifier)


def _patch_persist():
    return patch("backend.handoff.delivery.persist_handoff_record", new_callable=AsyncMock)


def _patch_fallback():
    return patch("backend.handoff.delivery.send_fallback_email", new_callable=AsyncMock)


def _patch_emit():
    return patch("backend.handoff.delivery.emit_event", new_callable=AsyncMock)


def _patch_db_url(monkeypatch):
    monkeypatch.setattr("backend.config.settings.checkpoint_db_url", "postgresql://fake")


# ── Both channels succeed ────────────────────────────────────────────────────

async def test_both_channels_succeed_outcome_complete(monkeypatch):
    _patch_db_url(monkeypatch)
    crm_result = LeadCreationResult(crm_record_id="42", crm_record_url="")

    with (
        _patch_slack(),
        _patch_persist() as mock_persist,
        _patch_fallback() as mock_fallback,
        _patch_emit(),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", new_callable=AsyncMock, return_value=crm_result),
    ):
        await dispatch_handoff(_make_request())

    record = mock_persist.call_args[0][0]
    assert record.outcome == "complete"
    assert record.slack_status == "ok"
    assert record.crm_status == "ok"
    mock_fallback.assert_not_called()


async def test_both_channels_succeed_emits_handoff_delivered(monkeypatch):
    _patch_db_url(monkeypatch)
    crm_result = LeadCreationResult(crm_record_id="1", crm_record_url="")
    emitted = []

    async def capture_event(event):
        emitted.append(event)

    with (
        _patch_slack(),
        _patch_persist(),
        _patch_fallback(),
        patch("backend.handoff.delivery.emit_event", side_effect=capture_event),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", new_callable=AsyncMock, return_value=crm_result),
    ):
        await dispatch_handoff(_make_request())

    event_names = [e.name for e in emitted]
    assert "handoff_dispatched" in event_names
    assert "handoff_delivered" in event_names
    assert "handoff_partial_failure" not in event_names
    assert "handoff_total_failure" not in event_names


async def test_crm_record_id_stored_in_handoff_record(monkeypatch):
    _patch_db_url(monkeypatch)
    crm_result = LeadCreationResult(crm_record_id="99", crm_record_url="")

    with (
        _patch_slack(),
        _patch_persist() as mock_persist,
        _patch_fallback(),
        _patch_emit(),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", new_callable=AsyncMock, return_value=crm_result),
    ):
        await dispatch_handoff(_make_request())

    record = mock_persist.call_args[0][0]
    assert record.crm_record_id == "99"


# ── CRM fails, Slack succeeds → partial_failure ──────────────────────────────

async def test_crm_fails_outcome_partial_failure(monkeypatch):
    _patch_db_url(monkeypatch)
    monkeypatch.setattr("backend.config.settings.handoff_retry_backoff_seconds", "0")

    with (
        _patch_slack(),
        _patch_persist() as mock_persist,
        _patch_fallback() as mock_fallback,
        _patch_emit(),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", side_effect=CRMDeliveryError(None, "DB down")),
    ):
        await dispatch_handoff(_make_request())

    record = mock_persist.call_args[0][0]
    assert record.outcome == "partial_failure"
    assert record.crm_status == "failed"
    assert record.slack_status == "ok"
    mock_fallback.assert_called_once()


async def test_crm_fails_emits_partial_failure_event(monkeypatch):
    _patch_db_url(monkeypatch)
    monkeypatch.setattr("backend.config.settings.handoff_retry_backoff_seconds", "0")
    emitted = []

    async def capture_event(event):
        emitted.append(event)

    with (
        _patch_slack(),
        _patch_persist(),
        _patch_fallback(),
        patch("backend.handoff.delivery.emit_event", side_effect=capture_event),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", side_effect=CRMDeliveryError(None, "DB down")),
    ):
        await dispatch_handoff(_make_request())

    event_names = [e.name for e in emitted]
    assert "handoff_partial_failure" in event_names


# ── Both channels fail → total_failure ───────────────────────────────────────

async def test_both_channels_fail_outcome_total_failure(monkeypatch):
    _patch_db_url(monkeypatch)
    monkeypatch.setattr("backend.config.settings.handoff_retry_backoff_seconds", "0")

    with (
        _patch_slack(_mock_notifier(raises=SlackDeliveryError(500, "Slack down"))),
        _patch_persist() as mock_persist,
        _patch_fallback() as mock_fallback,
        _patch_emit(),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", side_effect=CRMDeliveryError(None, "DB down")),
    ):
        await dispatch_handoff(_make_request())

    record = mock_persist.call_args[0][0]
    assert record.outcome == "total_failure"
    assert record.slack_status == "failed"
    assert record.crm_status == "failed"
    mock_fallback.assert_called_once()


async def test_both_channels_fail_emits_total_failure_event(monkeypatch):
    _patch_db_url(monkeypatch)
    monkeypatch.setattr("backend.config.settings.handoff_retry_backoff_seconds", "0")
    emitted = []

    async def capture_event(event):
        emitted.append(event)

    with (
        _patch_slack(_mock_notifier(raises=SlackDeliveryError(500, "Slack down"))),
        _patch_persist(),
        _patch_fallback(),
        patch("backend.handoff.delivery.emit_event", side_effect=capture_event),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", side_effect=CRMDeliveryError(None, "DB down")),
    ):
        await dispatch_handoff(_make_request())

    event_names = [e.name for e in emitted]
    assert "handoff_total_failure" in event_names


# ── context_packet generation failure aborts delivery ────────────────────────

async def test_context_packet_failure_aborts_delivery(monkeypatch):
    _patch_db_url(monkeypatch)

    with (
        _patch_slack(),
        _patch_persist() as mock_persist,
        _patch_fallback() as mock_fallback,
        _patch_emit() as mock_emit,
        patch(
            "backend.handoff.delivery.generate_context_packet",
            side_effect=Exception("state corrupted"),
        ),
    ):
        await dispatch_handoff(_make_request())

    mock_persist.assert_not_called()
    mock_fallback.assert_not_called()
    mock_emit.assert_not_called()


# ── HandoffRecord persist failure does not propagate ─────────────────────────

async def test_persist_failure_does_not_propagate(monkeypatch):
    _patch_db_url(monkeypatch)
    crm_result = LeadCreationResult(crm_record_id="1", crm_record_url="")

    with (
        _patch_slack(),
        patch("backend.handoff.delivery.persist_handoff_record", side_effect=RuntimeError("db error")),
        _patch_fallback(),
        _patch_emit(),
        patch("backend.handoff.delivery.PostgresCRMClient.create_lead", new_callable=AsyncMock, return_value=crm_result),
    ):
        # Must not raise even though persist_handoff_record raises
        await dispatch_handoff(_make_request())


# ── _deliver_channel retry behaviour ─────────────────────────────────────────

async def test_deliver_channel_succeeds_on_first_attempt():
    call_count = 0

    async def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    outcome = await _deliver_channel("test", succeed, backoff_seconds=[], session_id="s1")
    assert outcome.ok is True
    assert outcome.attempts == 1
    assert call_count == 1


async def test_deliver_channel_retries_and_succeeds():
    attempts = []

    async def fail_then_succeed():
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("transient")

    outcome = await _deliver_channel("test", fail_then_succeed, backoff_seconds=[0], session_id="s1")
    assert outcome.ok is True
    assert outcome.attempts == 2


async def test_deliver_channel_exhausts_retries_returns_not_ok():
    async def always_fail():
        raise RuntimeError("always fails")

    outcome = await _deliver_channel("test", always_fail, backoff_seconds=[0, 0], session_id="s1")
    assert outcome.ok is False
    assert outcome.attempts == 3  # len(backoff_seconds) + 1
