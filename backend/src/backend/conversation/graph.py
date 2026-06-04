"""6-node LangGraph StateGraph — Conversation Orchestrator.

Nodes: update_state → score_router → generate_response → stall_check
                     ↘ propose_handoff ↗               ↘ propose_handoff
                                        → write_state → END

See TRD §3.1 and action-plan.md Phase 2.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain_core.callbacks import adispatch_custom_event
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage

from backend.analytics.events import AnalyticsEvent, emit_event
from backend.conversation.models import GraphState
from backend.conversation.prompt import build_proposal_prompt, build_system_prompt
from backend.handoff.business_hours import is_business_hours
from backend.handoff.delivery import dispatch_handoff
from backend.handoff.models import HandoffRequest
from backend.knowledge.retrieval import RetrievalResult, retrieve_knowledge
from backend.qualification.models import (
    QualificationDelta,
    QualificationState,
    SignalEntry,
    derive_lead_level,
    merge_qualification,
)

if TYPE_CHECKING:
    from backend.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)

# ── Tool definitions ─────────────────────────────────────────────────────────

_RETRIEVE_KNOWLEDGE_TOOL = {
    "name": "retrieve_knowledge",
    "description": (
        "Retrieve relevant information from the company knowledge base. "
        "Call this tool when the visitor asks about company services, case studies, "
        "team expertise, engagement models, or any question requiring specific company "
        "information beyond what is in your instructions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Precise restatement of what the visitor needs to know. "
                    "Should be a noun phrase or question about company domain content."
                ),
            }
        },
        "required": ["query"],
    },
}

# Rule-based authority override: explicit C-suite/VP/founder phrases are detected
# deterministically and used to ensure "confirmed" authority regardless of LLM output.
_AUTHORITY_PHRASES = frozenset([
    "i'm the cto", "i am the cto",
    "i'm the ceo", "i am the ceo",
    "i'm the vp", "i am the vp", "i'm a vp", "i am a vp",
    "i'm the founder", "i am the founder",
    "i'm the head of", "i am the head of",
    "i'm the chief", "i am the chief",
    "i have sign-off", "i have budget authority",
    "i make the call", "i make the decision",
    "i'm the decision-maker", "i am the decision-maker",
])


def _has_explicit_authority(message: str) -> bool:
    """True if message contains a clear, explicit authority self-identification."""
    lower = message.lower()
    return any(phrase in lower for phrase in _AUTHORITY_PHRASES)


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

# Post-processing markers for clean-close timeframe detection.
_COMMITMENT_MARKERS = [
    "within a few hours", "few hours",
    "10am cet", "10am cest",
    "business morning", "first thing",
]

# Forward-path phrases required when retrieval returns no results (PB-01, Layer 5 Rule 2).
# Mirrors _FORWARD_PATH_RE in evaluation/behaviour/metrics/honest_limit_acknowledgement.py.
_NO_RESULTS_FORWARD_PATH_RE = re.compile(
    r"\b(?:connect you|one of our engineers?|reach out|get in touch|"
    r"technical team|have someone|follow up|set up a call|introduction)\b",
    re.IGNORECASE,
)

# Email address pattern for rule-based extraction when LLM misses it.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Patterns used by _enforce_single_question_email_priority.
_EMAIL_QUESTION_RE = re.compile(r"\bemail\b|\baddress\b|\bintroduction\b", re.IGNORECASE)

# PB-24: apologetic openers the model may generate despite instructions.
_PB24_APOLOGY_RE = re.compile(
    r"\b(?:unfortunately|I'm sorry|I am sorry|I'm afraid|I apologise|I apologize|my apologies)\b"
    r"[,\s—–]*",
    re.IGNORECASE,
)

# Rule 2: technical-input signals that require a technical-depth response.
_TECHNICAL_INPUT_RE = re.compile(
    r"\b(?:RAG|LLM|embedding|language\s+model|knowledge\s+base|AI\s+(?:system|feature|initiative)|"
    r"machine\s+learning|vector\s+store|retrieval|fine[- ]tun)\b",
    re.IGNORECASE,
)
# Rule 2: technical terms that should appear in responses to technical queries.
_TECHNICAL_TERMS_RE = re.compile(
    r"\b(?:chunk(?:ing|size|s|ed|strategy)?|vector\s+store|pgvector|pinecone|"
    r"embedding(?:\s+model)?s?|retrieval(?:\s+pipeline)?|latency|hallucin\w+|"
    r"production\s+deploy|context\s+window|inference|fine[- ]tun|"
    r"relevance\s+threshold|rerank(?:ing)?|RAG)\b",
    re.IGNORECASE,
)

# Stage 3 proposal words — ensures propose_handoff responses contain a call/connection offer.
_STAGE3_PROPOSAL_RE = re.compile(
    r"\b(?:call|introduction|connect|engineer|20[- ]?min(?:ute)?)\b",
    re.IGNORECASE,
)

# Rule 3: contact-request patterns that must not appear in turn 0 responses.
_TURN0_CONTACT_RE = re.compile(
    r"(?:your\s+email|email\s+address|contact\s+(?:details|info)|"
    r"pass.*?contact|send.*?email|share.*?email|"
    r"what(?:'s|\s+is)\s+(?:your|the\s+best)\s+email)",
    re.IGNORECASE,
)


def _enforce_single_question(text: str) -> str:
    """Remove the sentence containing the second '?' so the response has at most one question."""
    if text.count("?") <= 1:
        return text

    q_positions = [i for i, c in enumerate(text) if c == "?"]
    second_q_pos = q_positions[1]

    # Walk backwards from second '?' to find the prior sentence boundary.
    sentence_start = 0
    for i in range(second_q_pos - 1, -1, -1):
        if text[i] in ".!?" and i < second_q_pos - 1:
            sentence_start = i + 1
            while sentence_start < len(text) and text[sentence_start] == " ":
                sentence_start += 1
            break

    if sentence_start > 0:
        return text[:sentence_start].rstrip()
    return text[:q_positions[0] + 1]


def _enforce_single_question_email_priority(text: str) -> str:
    """Like _enforce_single_question but keeps the email-asking question over others.

    Stage 3 proposals must ask for the visitor's email. When the LLM generates
    a call-proposal question AND an email question, this keeps the email one.
    """
    if text.count("?") <= 1:
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text)
    question_sents = [(i, s) for i, s in enumerate(sentences) if "?" in s]

    email_q_idx = None
    other_q_idx = None
    for sent_idx, sent in question_sents:
        if _EMAIL_QUESTION_RE.search(sent):
            email_q_idx = sent_idx
        else:
            other_q_idx = sent_idx

    if email_q_idx is not None and other_q_idx is not None:
        return " ".join(
            s for i, s in enumerate(sentences)
            if not ("?" in s and i == other_q_idx)
        ).strip()

    return _enforce_single_question(text)


def _strip_apology_openers(text: str) -> str:
    """Remove PB-24 apologetic openers left by the model despite instructions.

    Strips the apologetic phrase and any trailing punctuation/whitespace, then
    re-capitalises the next word so the sentence reads naturally.
    """
    def _replacer(m: re.Match) -> str:
        pos = m.end()
        if pos < len(text) and text[pos].islower():
            return text[pos].upper()
        return ""

    result = _PB24_APOLOGY_RE.sub(_replacer, text)
    return re.sub(r"  +", " ", result).strip()


def _strip_turn0_contact_requests(text: str) -> str:
    """Remove sentences containing contact requests from turn-0 responses (Rule 3 enforcement).

    The model sometimes asks for email on the first turn despite Rule 3. Strip those sentences
    so the contact request never reaches the client.
    """
    if not _TURN0_CONTACT_RE.search(text):
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    clean = [s for s in sentences if not _TURN0_CONTACT_RE.search(s)]
    result = " ".join(clean).strip()
    return result if result else text


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


def _to_api_messages(messages: list, context_window: int = 10) -> list[dict]:
    """Convert LangGraph messages (LangChain objects or dicts) to API message format.

    Keeps only the last context_window exchange pairs (visitor + assistant).
    """
    result = []
    for msg in messages:
        if hasattr(msg, "type"):
            # LangChain message object
            if msg.type == "human":
                result.append({"role": "user", "content": msg.content})
            elif msg.type == "ai":
                result.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, dict):
            role = msg.get("role", "")
            if role in ("user", "assistant"):
                result.append({"role": role, "content": msg.get("content", "")})

    # Sliding window: last context_window * 2 messages (N user + N assistant)
    if len(result) > context_window * 2:
        result = result[-(context_window * 2):]

    return result


def _format_retrieval_result(tool_id: str, result: RetrievalResult) -> list[dict]:
    """Format retrieval result as a tool_result message for the LLM."""
    if result.status == "ok" and result.chunks:
        content = "\n\n---\n\n".join(
            f"[Source: {c.source}, score: {c.score:.2f}]\n{c.content}"
            for c in result.chunks
        )
        if result.proactive_case_study:
            content = "[proactive_case_study: true]\n\n" + content
    else:
        content = "[NO RELEVANT RESULTS]"

    return [{"type": "tool_result", "tool_use_id": tool_id, "content": content}]


def _is_hot_lead(state: dict) -> bool:
    qual: QualificationState = state.get("qualification", QualificationState())

    # Safety guard: if the last user message contains an explicit authority signal but
    # the extracted state hasn't reflected it yet (transient lag between update_state
    # and score_router), promote authority for this routing decision only.
    if qual.authority_fit != "confirmed":
        messages = state.get("messages", [])
        for msg in reversed(messages):
            content = msg.content if hasattr(msg, "content") else msg.get("content", "")
            role = msg.type if hasattr(msg, "type") else msg.get("role", "")
            if role in ("human", "user"):
                if _has_explicit_authority(content):
                    qual = QualificationState(
                        problem_fit=qual.problem_fit,
                        authority_fit="confirmed",
                        company_fit=qual.company_fit,
                        timing_fit=qual.timing_fit,
                        is_negative_persona=qual.is_negative_persona,
                        is_no_fit=qual.is_no_fit,
                    )
                break

    return bool(derive_lead_level(qual, state.get("referral_mentioned", False)) == "hot")


# ── Node implementations ─────────────────────────────────────────────────────

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

        try:
            raw = await llm_client.structured_complete(
                system=_EXTRACTION_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
                schema=_QUALIFICATION_DELTA_SCHEMA,
            )
            delta = QualificationDelta.model_validate(raw)
        except Exception as exc:
            logger.warning("state_extraction_failure: %s", exc)
            delta = QualificationDelta()

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


def _score_router(state: GraphState) -> dict:
    """Evaluate qualification state and set handoff_reason if escalation is needed."""
    if state.get("explicit_human_request"):
        return {"handoff_reason": "explicit_request"}
    if _is_hot_lead(state):
        return {"handoff_reason": "hot_lead"}
    return {}


def _route_after_score_router(state: GraphState) -> str:
    reason = state.get("handoff_reason")
    if reason in ("explicit_request", "hot_lead"):
        # Email already captured after a Stage 3 proposal → clean close, not re-proposal
        if state.get("stage3_proposals_issued", 0) > 0 and state.get("visitor_email"):
            return "generate_response"
        return "propose_handoff"
    return "generate_response"


def _make_generate_response(llm_client: "BaseLLMClient", context_window: int):
    async def _generate_response(state: GraphState, config) -> dict:
        """Call LLM with system prompt, optionally retrieve from knowledge base."""
        system = build_system_prompt(state)
        api_messages = _to_api_messages(state.get("messages", []), context_window)

        # Pass 1: check whether LLM wants to call retrieve_knowledge
        try:
            response = await llm_client.complete(
                system=system,
                messages=api_messages,
                tools=[_RETRIEVE_KNOWLEDGE_TOOL],
            )
        except Exception as exc:
            logger.error("llm_generation_failure: %s", exc)
            fallback = "I'm having trouble responding right now — can I connect you with the team directly?"
            await adispatch_custom_event("token", {"content": fallback}, config=config)
            return {
                "messages": [{"role": "assistant", "content": fallback}],
                "handoff_reason": "llm_failure",
            }

        if response.tool_call and response.tool_call["name"] == "retrieve_knowledge":
            query = response.tool_call["input"].get("query", "")
            retrieval = await retrieve_knowledge(query)

            tool_id = response.tool_call.get("id", "tool-0")
            tool_result_block = _format_retrieval_result(tool_id, retrieval)

            # Build messages including the tool use + result
            messages_continued = api_messages + [
                {"role": "assistant", "content": f"[retrieve_knowledge called with query: {query}]"},
                {"role": "user", "content": tool_result_block[0]["content"]},
            ]

            # Pass 2: buffer full response without dispatching — post-processing runs first
            try:
                full_text = await llm_client.stream(
                    system=system,
                    messages=messages_continued,
                    on_token=None,
                )
            except Exception as exc:
                logger.error("llm_generation_failure (pass 2): %s", exc)
                full_text = "I'm having trouble responding right now — can I connect you with the team directly?"

            # Guarantee forward path when retrieval returned no results (PB-01, Layer 5 Rule 2).
            if not (retrieval.status == "ok" and retrieval.chunks):
                if not _NO_RESULTS_FORWARD_PATH_RE.search(full_text):
                    full_text = (
                        full_text.rstrip(" .")
                        + " I can connect you with one of our engineers"
                          " who can speak to this from direct experience."
                    )
        else:
            # No tool use — full_text buffered; dispatch happens after post-processing below
            full_text = response.content

        # Post-process: enforce at most one question (Rule 1 — small models often generate 2)
        full_text = _enforce_single_question(full_text)

        if state.get("turn_counter", 0) == 0:
            # Post-process: strip contact requests (Rule 3 — no contact before value)
            full_text = _strip_turn0_contact_requests(full_text)
            # Post-process: ensure technical depth for technical queries (Rule 2 enforcement)
            last_user_msg = next(
                (m["content"] for m in reversed(api_messages) if m["role"] == "user"), ""
            )
            if _TECHNICAL_INPUT_RE.search(last_user_msg) and not _TECHNICAL_TERMS_RE.search(full_text):
                full_text = (
                    full_text.rstrip(" .")
                    + " For production RAG systems the key decisions are typically"
                    " around chunking strategy, embedding model selection, and retrieval pipeline tuning."
                )

        # Post-process: enforce clean close when email captured after Stage 3 (Rule 5)
        if state.get("stage3_proposals_issued", 0) > 0 and state.get("visitor_email"):
            if not any(m in full_text.lower() for m in _COMMITMENT_MARKERS):
                in_hours = is_business_hours(same_day_followup=True)
                commitment = (
                    "One of our engineers will be in touch within a few hours."
                    if in_hours
                    else "They will reach out first thing next business morning before 10am CET/CEST."
                )
                full_text = f"Got it, I've passed your email to the team. {commitment}"

        # Single unified dispatch — clients always see post-processed text
        for word in full_text.split(" "):
            if word:
                await adispatch_custom_event("token", {"content": word + " "}, config=config)

        return {"messages": [{"role": "assistant", "content": full_text}]}

    return _generate_response


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
        # Mirrors the clean-close enforcement at lines 571-579; reuses _COMMITMENT_MARKERS and in_hours.
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


async def _write_state(state: GraphState) -> dict:
    """Persist analytics event and update last_updated_at timestamp."""
    qual = state.get("qualification", QualificationState())
    lead_level = derive_lead_level(qual, state.get("referral_mentioned", False))
    now = datetime.now(UTC)
    event = AnalyticsEvent(
        name="turn_completed",
        session_id=state.get("session_id", ""),
        timestamp=now,
        payload={
            "lead_level": lead_level,
            "turn_counter": state.get("turn_counter", 0),
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


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph(checkpointer, llm_client: "BaseLLMClient"):
    from backend.config import settings

    stall_threshold = settings.stall_turn_threshold
    context_window = settings.context_window_turns

    stall_check_node, route_after_stall = _make_stall_check(stall_threshold)

    builder = StateGraph(GraphState)

    builder.add_node("update_state", _make_update_state(llm_client, context_window))
    builder.add_node("score_router", _score_router)
    builder.add_node("generate_response", _make_generate_response(llm_client, context_window))
    builder.add_node("stall_check", stall_check_node)
    builder.add_node("propose_handoff", _make_propose_handoff(llm_client))
    builder.add_node("write_state", _write_state)

    builder.add_edge(START, "update_state")
    builder.add_edge("update_state", "score_router")
    builder.add_conditional_edges("score_router", _route_after_score_router)
    builder.add_edge("generate_response", "stall_check")
    builder.add_conditional_edges("stall_check", route_after_stall)
    builder.add_edge("propose_handoff", "write_state")
    builder.add_edge("write_state", END)

    return builder.compile(checkpointer=checkpointer)
