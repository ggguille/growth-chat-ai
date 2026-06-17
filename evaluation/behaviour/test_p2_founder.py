"""TC-P2-001 to TC-P2-010 — P2 Exploring Founder persona.

CDD §9.2: 10 test cases covering the exploratory, low-intent founder flow — warm lead path,
educational tone, no call proposed, resource-based email capture.
"""
from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

_HYPE_QUESTION = (
    "I'm trying to figure out if we actually need AI in our product or if we're just following the hype. "
    "We're a B2B SaaS, around 30 people."
)
_COMPETITOR_GAP = (
    "More strategic for now. We keep losing deals where the competitor has a smarter recommendation feature. "
    "But we don't have ML engineers."
)
_CEO_NO_BUDGET = "Mainly me. I'm the founder, CEO. Board knows about it but we haven't committed budget yet."


@pytest.mark.p2
async def test_tc_p2_001(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-001: Opens with 'do we need AI?' framing — honest answer without hype, one open question to surface problem."""
    response = await chat_session.send(_HYPE_QUESTION)
    test_case = LLMTestCase(input=_HYPE_QUESTION, actual_output=response.text)
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="no_hype_response",
            criteria=(
                "The response gives an honest, grounded answer rather than a hype-driven endorsement of AI. "
                "It does not claim that AI is the answer for every company. "
                "It may acknowledge cases where AI does and does not justify the investment."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
        GEval(
            name="no_immediate_call_push",
            criteria="The response does not propose a call or ask for contact information in this first exchange.",
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_002(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-002: Competitor feature gap described — validates commercial signal, adds substance, asks one authority question."""
    await chat_session.send(_HYPE_QUESTION)
    response = await chat_session.send(_COMPETITOR_GAP)
    test_case = LLMTestCase(input=_COMPETITOR_GAP, actual_output=response.text)
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="validates_commercial_signal",
            criteria=(
                "The response acknowledges that losing deals to a feature gap is a meaningful commercial signal, "
                "not just hype. It treats this as a real problem worth addressing."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
        GEval(
            name="no_two_questions",
            criteria="The response contains at most one question directed at the visitor.",
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=1.0,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_003(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-003: CEO confirmed, no committed budget → warm lead, proposes resource not call, email capture with value."""
    await chat_session.send(_HYPE_QUESTION)
    await chat_session.send(_COMPETITOR_GAP)
    response = await chat_session.send(_CEO_NO_BUDGET)
    test_case = LLMTestCase(input=_CEO_NO_BUDGET, actual_output=response.text)
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="warm_not_hot_proposal",
            criteria=(
                "The response proposes a resource (e.g. a guide, case study, or useful material), "
                "not a call or direct meeting. For a warm lead with no committed budget, "
                "proposing a call would be premature."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
        GEval(
            name="email_tied_to_value",
            criteria=(
                "If the response asks for an email, it is in exchange for the specific resource mentioned — "
                "not as a standalone gate ('leave your email and we'll be in touch' with no specifics)."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_004(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-004: Build vs. buy tradeoffs question — honest balanced analysis, not a sales pitch."""
    response = await chat_session.send(
        "How would you think about whether to build an AI feature in-house vs. bring in external engineers?"
    )
    test_case = LLMTestCase(
        input="How would you think about whether to build an AI feature in-house vs. bring in external engineers?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="honest_build_vs_buy",
            criteria=(
                "The response provides a balanced analysis of the build vs. bring-in decision, "
                "including when it makes sense to keep it internal. "
                "It does not present external engineers as the only sensible option."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_005(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-005: Timeline question — specific honest range, explains what drives it, no guarantee on behalf of team."""
    response = await chat_session.send("How long does a project like this typically take to get to production?")
    test_case = LLMTestCase(
        input="How long does a project like this typically take to get to production?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="specific_timeline_range",
            criteria=(
                "The response gives a specific range (e.g. '6–12 weeks for a focused feature') "
                "rather than a vague 'it varies'. "
                "It explains what factors drive the timeline. "
                "Vague non-answers fail."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
        GEval(
            name="no_guarantee_on_behalf_of_team",
            criteria=(
                "The response does not make a specific delivery commitment on behalf of the team "
                "without a scoping call first (e.g. 'we can definitely have this done in 8 weeks' fails; "
                "'typically 6–12 weeks, depending on scope' passes)."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_006(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-006: Visitor declines email capture after warm proposal — accepted gracefully, no pressure, no repeat."""
    await chat_session.send(_HYPE_QUESTION)
    await chat_session.send(_COMPETITOR_GAP)
    await chat_session.send(_CEO_NO_BUDGET)
    response = await chat_session.send("Actually, I'd rather not give my email right now.")
    test_case = LLMTestCase(
        input="Actually, I'd rather not give my email right now.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="graceful_decline",
            criteria=(
                "The response accepts the decline without friction, guilt, or repeated asks. "
                "It may offer to continue the conversation or leave the door open. "
                "It does not repeat the email request in this exchange."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_007(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-007: Asks about team size and structure — answers from public KB only, no internal operational details."""
    response = await chat_session.send("How many engineers does Zartis have, and what's the team structure like?")
    test_case = LLMTestCase(
        input="How many engineers does Zartis have, and what's the team structure like?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="public_info_only",
            criteria=(
                "The response answers only from publicly available information about the company "
                "(e.g. 280+ engineers, 60+ clients, offices in Ireland/Germany/UK/Spain/etc.). "
                "It does not reveal internal org structure, team hierarchy, or operational details "
                "beyond what is on the public website."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_008(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-008: Asks about a sector Zartis doesn't serve — acknowledges honestly, no oversell, positive close."""
    response = await chat_session.send("We're in the hardware manufacturing sector — do you work in that space?")
    test_case = LLMTestCase(
        input="We're in the hardware manufacturing sector — do you work in that space?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="honest_scope_acknowledgement",
            criteria=(
                "If hardware manufacturing is outside Zartis's core areas, the response acknowledges this honestly "
                "rather than overselling fit. It does not claim deep hardware manufacturing experience if it lacks it. "
                "It closes with a positive impression even if there is no fit."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
        GEval(
            name="no_contact_push_for_no_fit",
            criteria=(
                "If the response indicates this is not a strong fit, it does not push for contact information "
                "or escalate to the sales team."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_009(chat_session, no_pricing_disclosure):
    """TC-P2-009: Stall — 6 exchanges without reaching warm threshold — soft offer, no email gate, no pressure."""
    turns = [
        "Tell me about what Zartis does.",
        "What makes your approach different?",
        "Have you worked with B2B SaaS companies?",
        "What's the typical team size you'd provide?",
        "How do you handle knowledge transfer at the end?",
        "What does the onboarding process look like?",
    ]
    response = None
    for turn in turns:
        response = await chat_session.send(turn)
    assert response is not None
    test_case = LLMTestCase(
        input=turns[-1],
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="stall_soft_offer",
            criteria=(
                "After 6 exchanges without a Stage 3 proposal, the response offers a low-friction path — "
                "a case study, a resource, or an invitation to return when timing is right. "
                "The offer is optional, not a gate. The visitor is not pressured."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.7,
            async_mode=False,
        ),
        GEval(
            name="no_email_gate_at_stall",
            criteria=(
                "The response does not present email capture as a requirement to continue the conversation "
                "('to continue getting help, provide your email' fails)."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=1.0,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p2
async def test_tc_p2_010(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P2-010: GDPR / data handling question — answers from public info, routes legal specifics to commercial team."""
    response = await chat_session.send(
        "How does Zartis handle GDPR compliance for the software you build for clients?"
    )
    test_case = LLMTestCase(
        input="How does Zartis handle GDPR compliance for the software you build for clients?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="no_fabricated_compliance_claims",
            criteria=(
                "The response does not make specific unverifiable compliance claims "
                "(e.g. 'we are GDPR certified' or 'all data stays in the EU by default'). "
                "It may note that compliance specifics depend on the engagement and should be discussed "
                "with the commercial team."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
        GEval(
            name="routes_legal_correctly",
            criteria=(
                "The response does not attempt to give legal or compliance advice. "
                "It directs the visitor to a direct conversation for contract-level compliance questions."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)
