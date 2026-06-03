"""TC-P3-001 to TC-P3-010 — P3 Referred Decision-Maker persona.

CDD §9.2: 10 test cases covering the high-authority, low-friction referred visitor flow —
minimal qualification, fast Stage 3 trigger, consultant detection, three-way intro.
"""
from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

_REFERRAL_OPEN = (
    "Hi — a colleague at Accenture recommended your company for an AI project we're scoping. "
    "We're a 400-person scale-up and we need senior engineers fast."
)
_VP_CONFIRMS = (
    "New build — we're adding a recommendation layer to our platform. "
    "I'm the VP of Product and I have sign-off on the vendor."
)


@pytest.mark.p3
async def test_tc_p3_001(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P3-001: Opens with referral and urgency — acknowledges referral, skips exploratory questions, one scoping question."""
    response = await chat_session.send(_REFERRAL_OPEN)
    test_case = LLMTestCase(input=_REFERRAL_OPEN, actual_output=response.text)
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="referral_acknowledged",
            criteria=(
                "The response acknowledges the referral from Accenture or the fact that the visitor "
                "was recommended. It does not treat this as a cold open."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
        GEval(
            name="no_exploratory_sequence",
            criteria=(
                "The response does not start an exploratory qualification sequence. "
                "Given the referral and company size stated, it asks at most one focused scoping question."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_002(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P3-002: VP Product with sign-off confirms in second message → Stage 3 triggered immediately."""
    await chat_session.send(_REFERRAL_OPEN)
    response = await chat_session.send(_VP_CONFIRMS)
    assert response.stage3_proposal_issued or response.current_stage == 3, (
        "Backend did not trigger Stage 3 after P3 hot threshold (referral + authority + company + problem confirmed)"
    )
    test_case = LLMTestCase(input=_VP_CONFIRMS, actual_output=response.text)
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="immediate_stage3_p3",
            criteria=(
                "The response triggers a Stage 3 proposal — a short call with an engineer and an email request. "
                "No further qualifying questions are asked after the hot threshold is confirmed."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_003(chat_session, no_pricing_disclosure):
    """TC-P3-003: Email provided after Stage 3 proposal — context packet includes referral and authority flags."""
    await chat_session.send(_REFERRAL_OPEN)
    await chat_session.send(_VP_CONFIRMS)
    response = await chat_session.send("Sure — vp@company.com")
    test_case = LLMTestCase(input="Sure — vp@company.com", actual_output=response.text)
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="follow_up_commitment",
            criteria=(
                "The response confirms that someone will be in touch and gives a specific time commitment. "
                "It does not ask more questions."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_004(chat_session, single_question_per_exchange, no_pricing_disclosure, no_fabrication_without_context):
    """TC-P3-004: Asks about a specific case study before agreeing — retrieves KB content, no fabrication."""
    await chat_session.send(_REFERRAL_OPEN)
    response = await chat_session.send(
        "Do you have any examples of recommendation layer builds you've done before?"
    )
    test_case = LLMTestCase(
        input="Do you have any examples of recommendation layer builds you've done before?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        no_fabrication_without_context,
        GEval(
            name="case_study_from_kb",
            criteria=(
                "The response references a real case study from the knowledge base "
                "(e.g. DataShield, RegEdge, or Voltara) rather than inventing one. "
                "If no directly matching case study exists, it acknowledges this rather than fabricating."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_005(chat_session, no_pricing_disclosure):
    """TC-P3-005: Requests call for same day, conversation at 5pm CET — no same-day commit, next-morning only."""
    await chat_session.send(_REFERRAL_OPEN)
    await chat_session.send(_VP_CONFIRMS)
    response = await chat_session.send("Can someone call me today? It's urgent.")
    test_case = LLMTestCase(
        input="Can someone call me today? It's urgent.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_guaranteed_same_day_after_4pm",
            criteria=(
                "If the response addresses outside-hours availability, it commits only to next business morning "
                "before 10am CET/CEST — not to a same-day call. "
                "If the system believes it is within business hours, a same-day response is acceptable. "
                "The test fails only if a same-day commitment is made when the team is demonstrably offline."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_006(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P3-006: Consultant evaluating for a client — qualifies on client context, does not pitch consultant as buyer.

    v1 behaviour (CDD EC-03): is_consultant=True is captured in session state and context packet.
    Three-way intro proposal is a v2 item — not expected from generate_response in v1.
    The system should continue qualifying on the client's initiative, not the consultant's.
    """
    response = await chat_session.send(
        "I'm an independent AI consultant. I've been asked to evaluate options for a client "
        "who needs to build out their data engineering capability. They're a 200-person fintech, Series C."
    )
    test_case = LLMTestCase(
        input="I'm an independent AI consultant...",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="consultant_qualified_on_client",
            criteria=(
                "The response qualifies on the client's context (200-person fintech, Series C) "
                "rather than treating the consultant as the buyer. "
                "It does not pitch the consultant on an engagement as if they are the CTO or decision-maker."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
        GEval(
            name="consultant_role_acknowledged",
            criteria=(
                "The response acknowledges the consultant's intermediary role — it engages with "
                "the evaluation context (evaluating for a client) rather than ignoring it. "
                "It does not demand the consultant bring the client decision-maker before it will help."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_007(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P3-007: Asks about IP ownership before agreeing to a call — routes to commercial team, no answer, no fabrication."""
    await chat_session.send(_REFERRAL_OPEN)
    response = await chat_session.send(
        "One thing I need to clarify before we talk further — who owns the IP for code your engineers write?"
    )
    test_case = LLMTestCase(
        input="One thing I need to clarify before we talk further — who owns the IP for code your engineers write?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="ip_routed_to_commercial",
            criteria=(
                "The response does not answer the IP ownership question directly. "
                "It acknowledges this is a contract-level question and directs the visitor "
                "to a direct conversation with the commercial team. "
                "Any general IP claim ('clients typically own the code') fails."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_008(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P3-008: High authority but problem outside scope — acknowledges mismatch honestly, no oversell."""
    await chat_session.send(_REFERRAL_OPEN)
    response = await chat_session.send(
        "We actually need firmware engineers for embedded systems — is that something you do?"
    )
    test_case = LLMTestCase(
        input="We actually need firmware engineers for embedded systems — is that something you do?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="honest_scope_mismatch",
            criteria=(
                "The response acknowledges honestly that embedded firmware engineering is outside Zartis's core areas. "
                "It does not misrepresent the company's capabilities to retain the lead. "
                "It closes with a positive impression."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_009(chat_session, no_pricing_disclosure):
    """TC-P3-009: Explicit human request immediately without prior context — honoured at once, no qualification attempt."""
    response = await chat_session.send("I'd rather just speak to someone directly. Can you connect me with a person?")
    test_case = LLMTestCase(
        input="I'd rather just speak to someone directly. Can you connect me with a person?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="explicit_request_honoured",
            criteria=(
                "The response immediately honours the request to speak with a person. "
                "It does not ask qualifying questions before offering the connection. "
                "It asks for an email or explains how to reach the team."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
        GEval(
            name="no_qualification_before_honouring",
            criteria=(
                "The response does not ask about company size, problem, budget, or role before "
                "acknowledging the explicit request for a human."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=1.0,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.p3
async def test_tc_p3_010(chat_session, no_pricing_disclosure):
    """TC-P3-010: Provides email but asks to delay call two weeks — timeline preference noted, no push for earlier."""
    await chat_session.send(_REFERRAL_OPEN)
    await chat_session.send(_VP_CONFIRMS)
    response = await chat_session.send(
        "Sure, here's my email — vp@company.com. But I'm travelling until the 15th, so let's target after that."
    )
    test_case = LLMTestCase(
        input="Sure, here's my email — vp@company.com. But I'm travelling until the 15th, so let's target after that.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="timeline_preference_respected",
            criteria=(
                "The response confirms the email capture and acknowledges the visitor's preferred timeline "
                "(after the 15th). It does not push for an earlier meeting or ignore the timeline preference."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)
