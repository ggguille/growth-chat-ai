"""propose_handoff node factory — Stage 3 proposal generation and handoff dispatch."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain_core.callbacks import adispatch_custom_event

from backend.conversation.models import GraphState
from backend.conversation.prompt import build_proposal_prompt
from backend.handoff.business_hours import is_business_hours
from backend.handoff.delivery import dispatch_handoff
from backend.handoff.models import HandoffRequest
from backend.qualification.models import QualificationState, derive_lead_level

from ..messages import _to_api_messages
from ..postprocessing import (
    _COMMITMENT_MARKERS,
    _STAGE3_PROPOSAL_RE,
    _enforce_single_question_email_priority,
    _strip_apology_openers,
)

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


def _make_propose_handoff(llm_client: "BaseLLMClient"):
    async def _propose_handoff(state: GraphState, config) -> dict:
        """Generate Stage 3 proposal and (stub) dispatch handoff request."""
        reason = state.get("handoff_reason") or "hot_lead"
        in_hours = is_business_hours(same_day_followup=(reason != "stall"))

        system = build_proposal_prompt(state, reason, in_hours)
        api_messages = _to_api_messages(state.get("messages", []))

        try:
            response = await llm_client.complete(system=system, messages=api_messages)
            full_text = response.content
        except Exception as exc:
            logger.error("propose_handoff llm_failure: %s", exc)
            full_text = "Let me connect you with the team directly. What's the best email to reach you on?"

        # Post-process BEFORE dispatching tokens so clients see the corrected text.
        full_text = _strip_apology_openers(full_text)
        # Small models often generate a qualifying question here instead of the call proposal.
        full_text = _enforce_single_question_email_priority(full_text)
        # Guarantee email ask is present — strip any remaining non-email questions, then append.
        if not re.search(r"\bemail\b", full_text, re.IGNORECASE):
            non_q_sentences = [s for s in re.split(r"(?<=[.!?])\s+", full_text) if "?" not in s]
            base = " ".join(non_q_sentences).rstrip(" .") if non_q_sentences else ""
            full_text = (base + " What email address should I send the introduction to?").lstrip()
        # Guarantee a proposal word is present — prepend connection framing if missing.
        if not _STAGE3_PROPOSAL_RE.search(full_text):
            full_text = "I'll connect you with one of our engineers. " + full_text
        # Guarantee a follow-up time commitment is present for explicit/hot-lead proposals.
        # Mirrors the clean-close enforcement pattern; reuses _COMMITMENT_MARKERS and in_hours.
        if reason != "stall" and not any(m in full_text.lower() for m in _COMMITMENT_MARKERS):
            commitment = (
                "One of our engineers will be in touch within a few hours."
                if in_hours
                else "They will reach out first thing next business morning before 10am CET."
            )
            sentences = re.split(r"(?<=[.!?])\s+", full_text)
            non_q = [s for s in sentences if "?" not in s]
            q_sents = [s for s in sentences if "?" in s]
            base = " ".join(non_q).rstrip() if non_q else full_text
            q_part = " " + " ".join(q_sents) if q_sents else ""
            full_text = f"{base} {commitment}{q_part}".strip()

        # Dispatch post-processed text as tokens
        for word in full_text.split(" "):
            if word:
                await adispatch_custom_event("token", {"content": word + " "}, config=config)

        # Phase 2: stub handoff dispatch (Phase 3 implements Slack + CRM)
        qual = state.get("qualification", QualificationState())
        lead_level = derive_lead_level(qual, state.get("referral_mentioned", False))

        # CDD PB-10/PB-11/EC-05: never route negative persona visitors to sales CRM/Slack.
        # N1/N2 explicit requests are honoured with a public contact response only.
        is_negative = qual.is_negative_persona or qual.is_no_fit
        if not is_negative:
            handoff_req = HandoffRequest(
                session_id=state.get("session_id", ""),
                handoff_reason=reason,
                lead_level=lead_level,
                business_hours=in_hours,
                session_state=state,
                triggered_at=datetime.now(UTC),
            )
            await dispatch_handoff(handoff_req)

        proposals_issued = state.get("stage3_proposals_issued", 0) + 1
        return {
            "messages": [{"role": "assistant", "content": full_text}],
            "turn_counter": 0,
            "stage3_proposals_issued": proposals_issued,
            "lead_level": lead_level,
            "current_stage": 3,
        }

    return _propose_handoff
