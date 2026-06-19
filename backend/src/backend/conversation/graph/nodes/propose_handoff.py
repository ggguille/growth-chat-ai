"""propose_handoff node factory — Stage 3 proposal generation and handoff dispatch."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from telemetry import get_logger, sanitize_error
from telemetry import events as tel_events

from langchain_core.callbacks import adispatch_custom_event

from backend.analytics.events import generation_span
from backend.conversation.models import GraphState
from backend.conversation.prompt import build_proposal_prompt
from backend.handoff.business_hours import is_business_hours
from backend.handoff.delivery import dispatch_handoff
from backend.handoff.models import HandoffRequest
from backend.qualification.models import QualificationState, derive_lead_level

from ..messages import _to_api_messages
from ..postprocessing import (
    _COMMITMENT_MARKERS,
    _HOT_LEAD_PROPOSAL_RE,
    _STAGE3_PROPOSAL_RE,
    _enforce_identity_disclosure,
    _enforce_referral_acknowledgment,
    _enforce_single_question_email_priority,
    _strip_apology_openers,
)

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient

log = get_logger("orchestrator")


def _make_propose_handoff(llm_client: "BaseLLMClient"):
    async def _propose_handoff(state: GraphState, config) -> dict:
        """Generate Stage 3 proposal and (stub) dispatch handoff request."""
        reason = state.get("handoff_reason") or "hot_lead"
        in_hours = is_business_hours(same_day_followup=(reason != "stall"))

        # RC-A: Identity question guard — "Are you a real person?" is a disclosure question,
        # not a handoff request. LLM extraction sometimes flags these as explicit_human_request=True.
        # Intercept before cold_explicit routing so _enforce_identity_disclosure fires correctly.
        last_user_msg = next(
            (m["content"] if isinstance(m, dict) else m.content
             for m in reversed(state.get("messages", []))
             if (m.get("role") if isinstance(m, dict) else getattr(m, "type", "")) in ("human", "user")),
            "",
        )
        identity_check = _enforce_identity_disclosure(last_user_msg, "")
        if identity_check:
            for word in identity_check.split(" "):
                if word:
                    await adispatch_custom_event("token", {"content": word + " "}, config=config)
            return {"messages": [{"role": "assistant", "content": identity_check}], "current_stage": 1}

        # N1/N2 explicit requests OR cold explicit requests (no prior qualification context):
        # bypass standard proposal, return public contact only.
        # Cold explicit = first-contact "can I speak to someone?" with no problem/authority
        # signals established yet. Avoids routing anonymous visitors to sales CRM.
        qual = state.get("qualification", QualificationState())
        is_negative = qual.is_negative_persona or qual.is_no_fit
        cold_explicit = (
            reason == "explicit_request"
            and qual.problem_fit == "not_detected"
            and qual.authority_fit == "not_detected"
            and not state.get("referral_mentioned")
        )
        # N1-005: N1/N2 visitors must NEVER be routed to the sales pipeline regardless of reason.
        # Any handoff reason (explicit_request, stall, warm_lead, hot_lead) for a negative persona
        # returns the public contact page only — no email capture, no CRM record.
        if is_negative:
            public_contact = (
                "You can reach the Zartis team directly via the contact page on the website — "
                "they'll be able to point you to the right person."
            )
            for word in public_contact.split(" "):
                if word:
                    await adispatch_custom_event("token", {"content": word + " "}, config=config)
            return {
                "messages": [{"role": "assistant", "content": public_contact}],
                "current_stage": 3,
            }
        if cold_explicit:
            # Cold explicit: honour the request immediately with an email ask.
            # Do NOT route to the contact page — PB-15 requires honouring at once.
            cold_contact = (
                "Let me connect you with someone from the team — "
                "what email should I use for the introduction?"
            )
            for word in cold_contact.split(" "):
                if word:
                    await adispatch_custom_event("token", {"content": word + " "}, config=config)
            return {
                "messages": [{"role": "assistant", "content": cold_contact}],
                "current_stage": 3,
                "stage3_proposals_issued": state.get("stage3_proposals_issued", 0) + 1,
            }

        system = build_proposal_prompt(state, reason, in_hours)
        api_messages = _to_api_messages(state.get("messages", []))

        with generation_span(
            name="propose_handoff",
            model=getattr(llm_client, "_model", "unknown"),
            input_messages=api_messages,
            metadata={
                "session_id": state.get("session_id"),
                "turn_index": state.get("turn_counter", 0),
                "reason": reason,
            },
        ) as gen:
            try:
                response = await llm_client.complete(system=system, messages=api_messages)
                full_text = response.content
            except Exception as exc:
                log.error(tel_events.LLM_GENERATION_FAILURE, session_id=state.get("session_id"), turn_index=state.get("turn_counter", 0), error=sanitize_error(str(exc)))
                full_text = "Let me connect you with the team directly. What's the best email to reach you on?"
                response = None
            if gen is not None and response is not None:
                gen.update(
                    model=response.model,
                    output=full_text,
                    usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens}
                    if response.usage else {},
                )

        # Post-process BEFORE dispatching tokens so clients see the corrected text.
        full_text = _strip_apology_openers(full_text)
        # Enforce Critical Rule 7: Stage 3 proposals also need referral ack when referral_mentioned=True.
        # Pass last_user_msg so turn-0 referrals are caught before state persistence completes.
        full_text = _enforce_referral_acknowledgment(state, full_text, last_user_msg)
        # Small models often generate a qualifying question here instead of the call proposal.
        full_text = _enforce_single_question_email_priority(full_text)
        # Guarantee email ask is present for hot/explicit proposals; stall email is optional.
        # warm_lead uses resource-offer language ("send this") not sales-intro language.
        if reason != "stall" and not re.search(r"\bemail\b", full_text, re.IGNORECASE):
            non_q_sentences = [s for s in re.split(r"(?<=[.!?])\s+", full_text) if "?" not in s]
            base = " ".join(non_q_sentences).rstrip(" .") if non_q_sentences else ""
            if reason == "warm_lead":
                full_text = (base + " What email should I send this to?").lstrip()
            else:
                full_text = (base + " What email address should I send the introduction to?").lstrip()
        # Guarantee a proposal word is present — language depends on reason.
        # Stall has no guarantee: soft closes don't need a proposal element.
        # Hot-lead uses _HOT_LEAD_PROPOSAL_RE (stricter) to avoid "introduction" in the email
        # question ("What email should I send the introduction to?") suppressing the guarantee.
        if reason in ("hot_lead", "explicit_request") and not _HOT_LEAD_PROPOSAL_RE.search(full_text):
            full_text = "I'd like to set up a short call between you and one of our senior engineers. " + full_text
        elif reason == "warm_lead" and not _STAGE3_PROPOSAL_RE.search(full_text):
            full_text = "I can send you a relevant case study. " + full_text
        # Guarantee a follow-up time commitment for call-based proposals only (not warm resource offers).
        # warm_lead proposals offer a resource, not a call, so no team-response commitment is appropriate.
        if reason in ("hot_lead", "explicit_request") and not any(m in full_text.lower() for m in _COMMITMENT_MARKERS):
            commitment = (
                "One of our engineers will be in touch within 2 hours."
                if in_hours
                else "Our team will be in touch first thing tomorrow morning"
                     " — expect to hear from them by 10am CET/CEST."
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
        lead_level = derive_lead_level(qual, state.get("referral_mentioned", False))

        # CDD PB-10/PB-11/EC-05: never route negative persona visitors to sales CRM/Slack.
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
