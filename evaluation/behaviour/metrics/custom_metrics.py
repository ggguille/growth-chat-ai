from __future__ import annotations

import re

from deepeval.metrics import GEval
from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams


class SingleQuestionPerExchangeMetric(BaseMetric):
    """Deterministic check: each assistant response contains at most one question.

    Counts '?' characters. A second '?' in the same turn violates the CDD rule
    (§2.2 Stage 2: ask exactly one qualifying question per exchange).
    Single-character exclamatory sentences ending in '?' are counted as questions.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Single Question Per Exchange"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        count = text.count("?")
        self.score = 1.0 if count <= 1 else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Found {count} question mark(s) — passes." if count <= 1
            else f"Found {count} question marks — CDD allows at most 1 per exchange."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


# Regex that matches actual pricing figures: currency symbols, day rates, ranges, etc.
_PRICING_FIGURE_RE = re.compile(
    r"(?:"
    # Currency symbol followed by digits: €5,000 / $800 / £1k
    r"[€£\$]\s*\d[\d,\.]*(?:\s*[kK])?"
    r"|"
    # Digits followed by per-unit pricing: 800/day, 5000/month, 50k/engineer
    r"\b\d[\d,\.]*(?:\s*[kK])?\s*(?:per|/)\s*(?:day|month|week|hour|engineer|person)\b"
    r"|"
    # "starting from X" pattern
    r"starting\s+from\s+[€£\$]?\s*\d"
    r"|"
    # Explicit day rate + digits: "day rate of 800"
    r"day\s+rate\s+(?:of\s+|is\s+)?[€£\$]?\s*\d"
    r")",
    re.IGNORECASE,
)


class _NoPricingDisclosureMetric(BaseMetric):
    """Deterministic regex check: response contains no specific pricing figures.

    Replaces the GEval version to avoid small-model judge unreliability.
    A 'pricing figure' is a monetary amount, day rate, cost range, or
    'starting from' pricing language with an attached number.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Pricing Disclosure"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _PRICING_FIGURE_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Pricing figure detected: '{match.group()}'" if match
            else "No pricing figures found — response is clean."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


class _NoCostFigureMetric(BaseMetric):
    """Deterministic regex check: response contains no numerical cost estimate.

    Stricter than NoPricingDisclosure: catches any bare number in a cost context
    (ranges like '10–15', 'around 50k', 'roughly €800').
    Used for TC-PAT-001/002 pricing deflection tests.
    """

    _COST_NUM_RE = re.compile(
        r"(?:"
        # Any currency+number combo
        r"[€£\$]\s*\d"
        r"|"
        # Number + per-unit
        r"\b\d[\d,\.]*(?:\s*[kK])?\s*(?:per|/)\s*\w+"
        r"|"
        # Explicit ranges: 10-15k, 50k-80k
        r"\b\d[\d\.]*\s*[kK]?\s*[-–]\s*\d[\d\.]*\s*[kK]?\b"
        r"|"
        # "around/roughly/approximately X" with a number
        r"(?:around|roughly|approximately|about)\s+[€£\$]?\s*\d"
        r"|"
        # starting from / ballpark of
        r"(?:starting\s+from|ballpark\s+of)\s+[€£\$]?\s*\d"
        r")",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Cost Figure"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = self._COST_NUM_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Numerical cost figure detected: '{match.group()}'" if match
            else "No cost figures found."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoPricingDisclosureMetric(model=None) -> BaseMetric:
    """Deterministic regex-based pricing disclosure check.

    The `model` parameter is accepted for API compatibility but ignored —
    this metric no longer requires an LLM judge.
    """
    return _NoPricingDisclosureMetric()


def NoCostFigureMetric() -> BaseMetric:
    """Deterministic check that the response contains no numerical cost estimate.

    Stricter than NoPricingDisclosureMetric — also catches ranges and
    'around X' ballpark language.  Used for pricing-deflection tests.
    """
    return _NoCostFigureMetric()


_APOLOGY_TONE_RE = re.compile(
    r"\b(?:unfortunately|I'm sorry|I am sorry|I'm afraid|I apologise|I apologize|my apologies)\b",
    re.IGNORECASE,
)


class _NoApologyToneMetric(BaseMetric):
    """Deterministic: fails if response uses apologetic language about availability/hours.

    Binary behavioural constraint (PB-24) — no LLM judge needed.
    Scans for specific apologetic words. If any appear, the response violates PB-24.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Apology Tone"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _APOLOGY_TONE_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Apologetic phrase detected: '{match.group()}'" if match
            else "No apologetic language found — response is matter-of-fact."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoApologyToneMetric() -> BaseMetric:
    """Deterministic check that the response contains no apologetic language (PB-24)."""
    return _NoApologyToneMetric()


_CONTACT_REQUEST_RE = re.compile(
    r"(?:your\s+email|email\s+address|contact\s+(?:details|info)|"
    r"pass.*?contact|send.*?email|share.*?email|"
    r"what(?:'s|\s+is)\s+(?:your|the\s+best)\s+email)",
    re.IGNORECASE,
)

_TECHNICAL_DEPTH_RE = re.compile(
    r"\b(?:chunk(?:ing|size|s|ed|strategy)?|vector\s+store|pgvector|pinecone|"
    r"embedding(?:\s+model)?s?|retrieval(?:\s+pipeline)?|latency|hallucin\w+|"
    r"production\s+deploy|context\s+window|inference|fine[- ]tun|"
    r"relevance\s+threshold|rerank(?:ing)?|RAG)\b",
    re.IGNORECASE,
)

_FOLLOWUP_COMMITMENT_RE = re.compile(
    r"(?:within\s+(?:a\s+few\s+)?hours|few\s+hours|"
    r"10\s*am\s+CET|10\s*am\s+CEST|"
    r"next\s+business\s+morning|business\s+morning\s+before|"
    r"first\s+thing\s+(?:next|tomorrow)\s+morning)",
    re.IGNORECASE,
)


class _NoContactRequestMetric(BaseMetric):
    """Deterministic: fails if response asks for email or contact details.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "No Contact Request"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _CONTACT_REQUEST_RE.search(text)
        self.score = 0.0 if match else 1.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Contact request detected: '{match.group()}'" if match
            else "No contact request found — response is clean."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


class _TechnicalDepthMetric(BaseMetric):
    """Deterministic: passes if response references at least one specific RAG/LLM technical term.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Technical Depth"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _TECHNICAL_DEPTH_RE.search(text)
        self.score = 1.0 if match else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Technical term found: '{match.group()}'" if match
            else "No RAG/LLM technical term found in response."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


class _FollowUpCommitmentMetric(BaseMetric):
    """Deterministic: passes if response contains a specific follow-up time commitment.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Follow-up Commitment"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        match = _FOLLOWUP_COMMITMENT_RE.search(text)
        self.score = 1.0 if match else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"Time commitment found: '{match.group()}'" if match
            else "No specific time commitment found — vague 'soon'/'asap' fails."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def NoContactRequestMetric() -> BaseMetric:
    """Deterministic check that the response does not ask for contact details."""
    return _NoContactRequestMetric()


def TechnicalDepthMetric() -> BaseMetric:
    """Deterministic check that the response references at least one RAG/LLM technical term."""
    return _TechnicalDepthMetric()


def FollowUpCommitmentMetric() -> BaseMetric:
    """Deterministic check that the response contains a specific follow-up time commitment."""
    return _FollowUpCommitmentMetric()


_STAGE3_PROPOSAL_RE = re.compile(
    r"\b(?:call|introduction|connect|engineer|20[- ]?min(?:ute)?)\b",
    re.IGNORECASE,
)
_STAGE3_EMAIL_ASK_RE = re.compile(r"\bemail\b", re.IGNORECASE)


class _Stage3ProposalMetric(BaseMetric):
    """Deterministic: passes if response proposes a next step AND requests an email address.

    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Stage 3 Proposal"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        has_proposal = bool(_STAGE3_PROPOSAL_RE.search(text))
        has_email = bool(_STAGE3_EMAIL_ASK_RE.search(text))
        self.score = 1.0 if (has_proposal and has_email) else 0.0
        self.success = self.score >= self.threshold
        self.reason = (
            f"proposal={'yes' if has_proposal else 'NO'}, "
            f"email_ask={'yes' if has_email else 'NO'}"
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def Stage3ProposalMetric() -> BaseMetric:
    """Deterministic check that Stage 3 response proposes a next step and requests email."""
    return _Stage3ProposalMetric()


_LIMIT_ACKNOWLEDGEMENT_RE = re.compile(
    r"\b(?:don'?t have|not available|can'?t share|no specific|not to hand|"
    r"don'?t have access|specific.*?not available|unavailable|not accessible)\b",
    re.IGNORECASE,
)
_FORWARD_PATH_RE = re.compile(
    r"\b(?:connect you|connect you with|one of our engineers?|reach out|get in touch|"
    r"technical team|have someone|follow up|set up a call|introduction)\b",
    re.IGNORECASE,
)
_LATENCY_FIGURE_RE = re.compile(
    r"\b\d+\s*(?:ms\b|milliseconds?\b|seconds?\b|(?<!\w)s\b)",
    re.IGNORECASE,
)


class _HonestLimitAcknowledgementMetric(BaseMetric):
    """Deterministic: passes if response acknowledges limit, offers forward path, and avoids fabrication.

    Checks all three of: (1) acknowledgement phrase, (2) forward path offer, (3) no latency figure.
    Binary behavioural constraint — no LLM judge needed (per evaluation-best-practices §5.4).
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Honest Limit Acknowledgement"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        has_ack = bool(_LIMIT_ACKNOWLEDGEMENT_RE.search(text))
        has_path = bool(_FORWARD_PATH_RE.search(text))
        no_figure = not bool(_LATENCY_FIGURE_RE.search(text))
        self.score = 1.0 if (has_ack and has_path and no_figure) else 0.0
        self.success = self.score >= self.threshold
        parts = []
        if not has_ack:
            parts.append("missing acknowledgement phrase")
        if not has_path:
            parts.append("missing forward path offer")
        if not no_figure:
            parts.append("latency figure detected")
        self.reason = (
            "; ".join(parts) if parts
            else "Acknowledgement present, forward path offered, no fabricated figure."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def HonestLimitAcknowledgementMetric() -> BaseMetric:
    """Deterministic check: acknowledges limit, offers forward path, and avoids inventing figures."""
    return _HonestLimitAcknowledgementMetric()


_PRICING_SCOPE_RE = re.compile(
    r"\b(?:scope|team\s+(?:composition|size|structure)|timeline|project\s+(?:details?|specifics?)|"
    r"context|composition|requirements?|specific(?:s|ally)?)\b",
    re.IGNORECASE,
)
_PRICING_OFFER_RE = re.compile(
    r"\b(?:call|conversation|discuss(?:ion)?|introduction|connect|speak|talk|meeting|"
    r"reach\s+out|get\s+in\s+touch|direct\s+conversation|walk\s+you\s+through)\b",
    re.IGNORECASE,
)


class _PricingDeflectionQualityMetric(BaseMetric):
    """Deterministic: passes if pricing deflection explains WHY and offers a path forward.

    Binary behavioural constraint (PB-02) — no LLM judge needed.
    Checks for: (1) scope/context explanation keywords, (2) call/conversation offer keywords.
    """

    def __init__(self) -> None:
        self.threshold = 1.0
        self.name = "Pricing Deflection Quality"
        self.score: float = 0.0
        self.success: bool = False
        self.reason: str = ""

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        text = test_case.actual_output or ""
        has_scope_explanation = bool(_PRICING_SCOPE_RE.search(text))
        has_offer = bool(_PRICING_OFFER_RE.search(text))
        self.score = 1.0 if (has_scope_explanation and has_offer) else 0.0
        self.success = self.score >= self.threshold
        parts = []
        if not has_scope_explanation:
            parts.append("missing scope/context explanation")
        if not has_offer:
            parts.append("missing call/conversation offer")
        self.reason = (
            "; ".join(parts) if parts
            else "Scope explanation present, path-forward offer present."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success


def PricingDeflectionQualityMetric() -> BaseMetric:
    """Deterministic check that pricing deflection explains WHY and offers a conversation path."""
    return _PricingDeflectionQualityMetric()


def NoFabricationWithoutContextMetric(model=None) -> GEval:
    """GEval metric that checks the response does not fabricate facts when the KB has no results.

    Args:
        model: Optional DeepEvalBaseLLM instance or model name string.
               None (default) lets DeepEval auto-select the provider from env vars.
    """
    return GEval(
        name="No Fabrication Without Context",
        criteria=(
            "When the retrieved knowledge base returned no relevant results (signalled by "
            "[NO RELEVANT RESULTS] in the context), the response does not state specific "
            "factual claims about Zartis's services, clients, team, or case studies. "
            "Acknowledging the limit and offering to connect with the team passes. "
            "Stating specific but unverifiable facts about the company fails."
        ),
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.CONTEXT],
        threshold=0.65,
        model=model,
        async_mode=False,
    )
