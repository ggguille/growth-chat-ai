"""write_state node and stall_check node factory for the conversation graph."""
from __future__ import annotations

from datetime import UTC, datetime

from backend.analytics.events import AnalyticsEvent, emit_event
from backend.conversation.models import GraphState
from backend.qualification.models import QualificationState, derive_lead_level


async def _write_state(state: GraphState) -> dict:
    """Persist analytics event and update last_updated_at timestamp."""
    qual = state.get("qualification", QualificationState())
    lead_level = derive_lead_level(qual, state.get("referral_mentioned", False))
    now = datetime.now(UTC)
    event = AnalyticsEvent(
        name="qualification_state_changed",
        timestamp=now,
        payload={
            "lead_level": lead_level,
            "turn_index": state.get("turn_counter", 0),
            "stage3_proposals_issued": state.get("stage3_proposals_issued", 0),
        },
    )
    await emit_event(event)
    stage = (
        3 if state.get("stage3_proposals_issued", 0) > 0
        else 2 if lead_level == "warm"
        else 1
    )
    return {"last_updated_at": now, "lead_level": lead_level, "current_stage": stage}


def _make_stall_check(stall_threshold: int):
    def _stall_check(state: GraphState) -> dict:
        new_count = state.get("turn_counter", 0) + 1
        update: dict = {"turn_counter": new_count}
        is_stall = new_count >= stall_threshold and state.get("stage3_proposals_issued", 0) == 0
        if is_stall:
            update["handoff_reason"] = "stall"
        return update

    def _route_after_stall_check(state: GraphState) -> str:
        return "propose_handoff" if state.get("handoff_reason") == "stall" else "write_state"

    return _stall_check, _route_after_stall_check
