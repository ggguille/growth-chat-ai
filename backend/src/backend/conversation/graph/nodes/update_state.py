"""update_state node factory — extracts qualification signals from visitor messages."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from telemetry import get_logger
from telemetry import events as tel_events

from backend.analytics.events import generation_span
from backend.conversation.models import GraphState
from backend.llm.base import LLMUsage
from backend.qualification.models import (
    QualificationDelta,
    QualificationState,
    SignalEntry,
)

from ..messages import _to_api_messages
from ..routing import _has_explicit_authority

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient

log = get_logger("orchestrator")

# ── Extraction schema / system prompt ────────────────────────────────────────

_QUALIFICATION_DELTA_SCHEMA = QualificationDelta.model_json_schema()
_QUALIFICATION_DELTA_SCHEMA["title"] = "QualificationDelta"

_EXTRACTION_SYSTEM = """
You extract qualification signals from a visitor message in a B2B sales chat.

Given the current qualification state and the new visitor message, return a JSON object
with ONLY the fields that have new evidence. Omit fields with no new signal.

Qualification dimensions:
- problem_fit: visitor has a concrete AI engineering problem or initiative
  ("not_detected" → "partially_confirmed" → "confirmed")
- authority_fit: visitor has decision-making authority or budget sign-off
  - "confirmed": visitor uses "I am" or "I'm" with a decision-making title (CTO, CEO, VP,
    founder, head of engineering, head of AI, Chief) OR explicitly states budget authority
    ("I have sign-off", "I make the call", "I'm the decision-maker")
  - "partially_confirmed": visitor is involved but authority is not explicitly confirmed
  - "not_detected": no role or authority information provided
- company_fit: company size/stage/sector signals suggesting ICP fit
  ("not_detected" → "partially_confirmed" → "confirmed")
- timing_fit: specific timeline, deadline, or urgency signals
  ("not_detected" → "partially_confirmed" → "confirmed")

Also detect:
- is_negative_persona: true if visitor is a competitor (hypothetical pricing/ops probes,
  no real initiative), researcher, student, or journalist
- is_no_fit: true if visitor is clearly outside ICP (individual contractor scope,
  academic purpose, wrong geography/regulatory context)
- explicit_human_request: true if visitor explicitly asks to speak with a human / book a call
- visitor_email: extract if visible in the message
- visitor_name: extract if visible in the message
- visitor_company: extract company name if mentioned
- visitor_role: extract role/title if mentioned
- is_consultant: true if visitor identifies as a freelancer/consultant evaluating for a client
- referral_mentioned: true if visitor mentions being referred or knowing someone at the company
- signals_observed: list of {dimension, signal_type, evidence, turn_index} for new signals only

Confidence transitions are monotonic (never downgrade). Only include a dimension if you have
new evidence that moves it to the same level or higher than current.

Return JSON matching QualificationDelta schema. All fields are optional.
""".strip()

_VALID_SIGNAL_TYPES = frozenset(("explicit", "implicit"))
_VALID_DIMENSIONS = frozenset(("problem_fit", "authority_fit", "company_fit", "timing_fit"))

# Rule-based qualification signal patterns — supplement LLM extraction when
# structured_complete returns empty deltas (common with small models like Llama 3.1 8B).
_PROBLEM_CONFIRMED_RE = re.compile(
    r"(?:building|developing|implementing|creating|deploying)\s+(?:a\s+)?(?:RAG|LLM|AI|ML)",
    re.IGNORECASE,
)
_PROBLEM_PARTIAL_RE = re.compile(
    r"\b(?:RAG|LLM|embedding\s+model|language\s+model|AI\s+(?:system|feature|initiative))\b",
    re.IGNORECASE,
)
_COMPANY_FIT_RE = re.compile(
    r"(?:\b\d{2,}\s+(?:people|employees|engineers?|team\s+members?)\b"
    r"|\bSeries\s+[A-D]\b)",
    re.IGNORECASE,
)
_TIMING_FIT_RE = re.compile(
    r"\b(?:Q[1-4]|by\s+Q[1-4]|end\s+of\s+(?:the\s+)?(?:year|quarter)"
    r"|this\s+(?:year|quarter))\b",
    re.IGNORECASE,
)

# Rule-based email extraction — regex finds addresses the LLM extraction misses.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


# ── Node factory ─────────────────────────────────────────────────────────────

def _make_update_state(llm_client: "BaseLLMClient", context_window: int):
    async def _update_state(state: GraphState) -> dict:
        """Extract qualification signals from the latest visitor message (LLM call)."""
        messages = state.get("messages", [])
        if not messages:
            return {}

        # Find the last user message
        last_user = ""
        for msg in reversed(messages):
            content = msg.content if hasattr(msg, "content") else msg.get("content", "")
            role = msg.type if hasattr(msg, "type") else msg.get("role", "")
            if role in ("human", "user"):
                last_user = content
                break

        if not last_user:
            return {}

        qual = state.get("qualification", QualificationState())
        turn_index = len([m for m in messages if (
            (hasattr(m, "type") and m.type == "human") or
            (isinstance(m, dict) and m.get("role") == "user")
        )])

        # Include recent conversation history so the extraction LLM can resolve
        # ambiguous signals in context (e.g. "I'd be working with them" references
        # the conversation, not an isolated message).
        recent = _to_api_messages(messages, context_window=context_window)
        history_lines = [
            f"  [{m['role']}]: {m['content'][:300]}"
            for m in recent[:-1]  # all but the last (= new visitor message)
        ]
        history_text = "\n".join(history_lines) if history_lines else "  (first turn)"

        user_msg = (
            f"Current qualification state:\n"
            f"problem_fit={qual.problem_fit}, authority_fit={qual.authority_fit}, "
            f"company_fit={qual.company_fit}, timing_fit={qual.timing_fit}, "
            f"is_negative_persona={qual.is_negative_persona}, is_no_fit={qual.is_no_fit}\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            f"Turn index: {turn_index}\n\n"
            f"New visitor message:\n{last_user}"
        )

        extraction_input = [{"role": "user", "content": user_msg}]
        raw: dict = {}
        usage = LLMUsage()
        with generation_span(
            name="qualification_extraction",
            model=getattr(llm_client, "_model", "unknown"),
            input_messages=extraction_input,
            metadata={"session_id": state.get("session_id"), "turn_index": turn_index},
        ) as gen:
            try:
                raw, usage = await llm_client.structured_complete(
                    system=_EXTRACTION_SYSTEM,
                    messages=extraction_input,
                    schema=_QUALIFICATION_DELTA_SCHEMA,
                )
                delta = QualificationDelta.model_validate(raw)
            except Exception as exc:
                log.warn(tel_events.STATE_EXTRACTION_FAILURE, session_id=state.get("session_id"), turn_index=turn_index, error=str(exc))
                delta = QualificationDelta()
            if gen is not None:
                gen.update(
                    output=str(raw),
                    usage_details={"input": usage.input_tokens, "output": usage.output_tokens},
                )

        # Rule-based override: explicit authority phrases always yield "confirmed".
        # Small models sometimes return "partially_confirmed" for "I'm the CTO" — this
        # pattern match catches those cases before the monotonic merge runs.
        if _has_explicit_authority(last_user) and qual.authority_fit != "confirmed":
            delta.authority_fit = "confirmed"

        # Rule-based overrides for problem/company/timing — supplement LLM extraction
        # when structured_complete returns empty deltas (small models like Llama 3.1 8B).
        if qual.problem_fit == "not_detected" and not delta.problem_fit:
            if _PROBLEM_CONFIRMED_RE.search(last_user):
                delta.problem_fit = "confirmed"
            elif _PROBLEM_PARTIAL_RE.search(last_user):
                delta.problem_fit = "partially_confirmed"

        if qual.company_fit == "not_detected" and not delta.company_fit:
            if _COMPANY_FIT_RE.search(last_user):
                delta.company_fit = "confirmed"

        if qual.timing_fit == "not_detected" and not delta.timing_fit:
            if _TIMING_FIT_RE.search(last_user):
                delta.timing_fit = "confirmed"

        # Rule-based email extraction — regex finds addresses the LLM extraction misses
        if not delta.visitor_email and not state.get("visitor_email"):
            email_match = _EMAIL_RE.search(last_user)
            if email_match:
                delta.visitor_email = email_match.group()

        update: dict = {}

        # Build updated QualificationState from delta
        new_qual = QualificationState(
            problem_fit=delta.problem_fit or "not_detected",
            authority_fit=delta.authority_fit or "not_detected",
            company_fit=delta.company_fit or "not_detected",
            timing_fit=delta.timing_fit or "not_detected",
            is_negative_persona=bool(delta.is_negative_persona),
            is_no_fit=bool(delta.is_no_fit),
            signals_observed=[
                SignalEntry(
                    dimension=s.get("dimension") if s.get("dimension") in _VALID_DIMENSIONS else "problem_fit",
                    signal_type=s.get("signal_type") if s.get("signal_type") in _VALID_SIGNAL_TYPES else "implicit",
                    evidence=str(s.get("evidence") or ""),
                    turn_index=int(s.get("turn_index") or turn_index),
                )
                for s in (delta.signals_observed or [])
            ],
        )
        # merge_qualification is the reducer — we just return the partial update
        update["qualification"] = new_qual

        if delta.explicit_human_request:
            update["explicit_human_request"] = True
        if delta.visitor_email:
            update["visitor_email"] = delta.visitor_email
        if delta.visitor_name:
            update["visitor_name"] = delta.visitor_name
        if delta.visitor_company:
            update["visitor_company"] = delta.visitor_company
        if delta.visitor_role:
            update["visitor_role"] = delta.visitor_role
        if delta.is_consultant:
            update["is_consultant"] = True
        if delta.referral_mentioned:
            update["referral_mentioned"] = True

        if not state.get("created_at"):
            update["created_at"] = datetime.now(UTC)

        return update

    return _update_state
