"""Post-processing rules applied to LLM-generated text before it is dispatched to clients.

All symbols are private — consumed by the node modules (generate_response, propose_handoff).
No internal graph/ imports; this module is a dependency leaf.
"""
from __future__ import annotations

import re

# ── Rule constants ────────────────────────────────────────────────────────────

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


# ── Post-processing functions ─────────────────────────────────────────────────

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
