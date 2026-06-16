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
from ..postprocessing import _REFERRAL_RE
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
- explicit_human_request: true if visitor explicitly asks to speak with a human, a real person, someone on the team, or to book a call. Examples: "can I speak directly with someone", "I'd like to speak with a person", "can I talk to someone from your team", "book a call", "set up a meeting".
  IMPORTANT: Do NOT set explicit_human_request=true for identity questions. The following are identity questions, NOT human requests: "Are you a real person?", "Are you a bot?", "Are you an AI?", "Are you ChatGPT?", "Who am I talking to?", "Is this a human?", "Am I talking to a real person?" — these ask about AI identity, not requests to connect with a human. Leave explicit_human_request unset for these.
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
    r"(?:building|developing|implementing|creating|deploying|adding)\s+(?:a\s+)?"
    r"(?:RAG|LLM|AI|ML|recommendation\s+(?:system|engine|layer|pipeline)|"
    r"NLP\s+pipeline|data\s+(?:pipeline|platform)|machine\s+learning\s+(?:system|model|pipeline))",
    re.IGNORECASE,
)
_PROBLEM_PARTIAL_RE = re.compile(
    r"\b(?:RAG|LLM|embedding\s+model|language\s+model|AI\s+(?:system|feature|initiative)|"
    r"recommendation\s+(?:system|engine|layer)|NLP|vector\s+(?:search|store|database))\b",
    re.IGNORECASE,
)
_COMPANY_FIT_RE = re.compile(
    r"(?:\b\d{2,}[- ](?:person|people|employee|engineer|strong)\b"   # "400-person", "120-strong"
    r"|\b\d{2,}\s+(?:people|persons?|employees?|engineers?|team\s+members?)\b"
    r"|\bSeries\s+[A-D]\b)",
    re.IGNORECASE,
)
_TIMING_FIT_RE = re.compile(
    r"\b(?:Q[1-4]|by\s+Q[1-4]|end\s+of\s+(?:the\s+)?(?:year|quarter)"
    r"|this\s+(?:year|quarter))\b",
    re.IGNORECASE,
)
# Rule-based negative persona detection — common N1/N2 opening patterns the LLM extraction misses.
_N1_MARKET_RE = re.compile(
    r"\b(?:market\s+research|competitive\s+(?:analysis|intelligence|research)"
    r"|researching\s+(?:vendors?|companies|providers?|options?)"
    r"|writing\s+(?:a|an)\s+(?:\w+\s+)?report"
    r"|industry\s+(?:research|report|survey|benchmarking)"
    r"|benchmarking|comparing\s+(?:providers?|vendors?|companies)"
    r"|how\s+(?:\w+\s+)?(?:vendors?|companies|providers?)\s+(?:structure|handle|price|approach)"
    r"|general(?:ly)?\s+(?:understanding|curious|interest(?:ed)?)"
    r"|(?:no\s+)?(?:specific|real|actual)\s+(?:project|initiative|need|requirement)(?:\s+(?:yet|in\s+mind))?"
    r"|just\s+(?:trying\s+to\s+understand|curious|researching|exploring)"
    r"|say\s+(?:a\s+)?(?:company|team|startup|client)\s+needed"
    r"|hypothetically\s+(?:speaking|if)"
    r"|what\s+would\s+(?:it|that)\s+(?:typically\s+)?cost"
    r"|what\s+does\s+(?:it\s+)?typically\s+cost)\b",
    re.IGNORECASE,
)
_N2_CANDIDATE_RE = re.compile(
    r"(?:are\s+you\s+(?:hiring|recruiting)"
    r"|(?:job|career|employment)\s+openings?"
    r"|open\s+roles?\s+at"
    r"|interested\s+in\s+(?:applying|working\s+(?:at|for)\s+zartis)"
    r"|looking\s+for\s+(?:a?\s*(?:job|role|position|opportunity))"
    r"|career\s+(?:change|in\s+ai|in\s+tech|advice|path|transition)"
    r"|considering\s+a\s+career"
    r"|studying\s+(?:ai|machine\s+learning|computer\s+science)"
    r"|\b(?:journalist|freelance\s+writer|PhD\s+(?:student|candidate)|"
    r"university\s+(?:student|researcher)|academic\s+research))\b",
    re.IGNORECASE,
)
# _REFERRAL_RE is imported from postprocessing (shared with _enforce_referral_acknowledgment).

# Rule-based Stage 3 decline detection — visitor pushes back on a call/email proposal.
# Only meaningful when stage3_proposals_issued > 0.
_STAGE3_DECLINE_RE = re.compile(
    r"(?:not\s+ready\s+(?:to|for)\s+(?:a\s+)?(?:call|meeting|that)"
    r"|I\s+have\s+(?:a\s+few\s+)?more\s+questions"
    r"|(?:maybe\s+)?later\b|not\s+(?:now|yet)\b"
    r"|not\s+interested\s+in\s+a\s+call"
    r"|let'?s?\s+(?:come\s+back\s+to\s+that|skip\s+that)"
    r"|I'?d?\s+(?:like|prefer)\s+(?:to\s+)?(?:continue|keep\s+(?:going|chatting|talking)))",
    re.IGNORECASE,
)

# Rule-based explicit human request detection — supplements LLM extraction.
# LLM extraction sometimes misses "can someone call me" and similar phrasings.
_EXPLICIT_HUMAN_RE = re.compile(
    r"(?:speak\s+(?:directly\s+)?(?:with\s+)?(?:to\s+)?(?:someone|a\s+person|a\s+human|your\s+team)"
    r"|talk\s+to\s+(?:someone|a\s+person|a\s+human|someone\s+from)"
    r"|connect\s+me\s+with\s+(?:a\s+person|someone|a\s+human|the\s+team)"
    r"|I'?d?\s+(?:like|prefer|rather)\s+(?:just\s+)?(?:to\s+)?(?:speak|talk)\s+to\s+(?:someone|a\s+person)"
    r"|book\s+a\s+(?:call|meeting)"
    r"|set\s+up\s+a\s+(?:call|meeting)"
    r"|can\s+someone(?:\s+from\s+your\s+team)?\s+(?:call|contact|reach)\s+me"
    r"|have\s+someone\s+(?:call|contact|reach)\s+me)",
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

        # Rule-based negative persona detection — covers common N1/N2 patterns the LLM misses.
        if not qual.is_negative_persona and not delta.is_negative_persona:
            if _N1_MARKET_RE.search(last_user) or _N2_CANDIDATE_RE.search(last_user):
                delta.is_negative_persona = True

        # Rule-based referral detection — supplements LLM extraction for P3 referral signals.
        if not state.get("referral_mentioned") and not delta.referral_mentioned:
            if _REFERRAL_RE.search(last_user):
                delta.referral_mentioned = True

        # Rule-based Stage 3 decline detection — only meaningful after at least one proposal.
        stage3_declined_now = (
            not state.get("stage3_declined")
            and state.get("stage3_proposals_issued", 0) > 0
            and _STAGE3_DECLINE_RE.search(last_user)
        )

        # Rule-based explicit human request detection — supplements LLM extraction.
        if not state.get("explicit_human_request") and not delta.explicit_human_request:
            if _EXPLICIT_HUMAN_RE.search(last_user):
                delta.explicit_human_request = True

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

        if stage3_declined_now:
            update["stage3_declined"] = True
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
