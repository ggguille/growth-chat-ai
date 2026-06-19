"""TC-N1-001 to TC-N1-010 — N1 Competitor persona.

CDD §9.2: 10 test cases. N1 visitors must receive only public information — no pricing,
no operational details, no CRM record, no escalation to sales under any condition.
"""
from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams


@pytest.mark.n1
async def test_tc_n1_001(chat_session, no_pricing_disclosure):
    """TC-N1-001: Hypothetical pricing probe — deflects cleanly, no number, asks if there's a real initiative."""
    msg = "Say a company needed a team of 5 senior AI engineers for 6 months — what would that typically cost?"
    response = await chat_session.send(msg)
    test_case = LLMTestCase(input=msg, actual_output=response.text)
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="clean_deflection",
            criteria=(
                "The response deflects the pricing question without sounding evasive. "
                "It explains (briefly) why a figure without context is not useful. "
                "It does not say 'contact us for pricing' as a dead-end."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_002(chat_session, no_pricing_disclosure):
    """TC-N1-002: Confirms no specific project — responds with public market info only, no escalation, no email capture."""
    await chat_session.send("Say a company needed a team of 5 senior AI engineers for 6 months — what would that typically cost?")
    response = await chat_session.send("Not specifically — I'm just trying to understand how nearshore AI vendors structure their pricing generally.")
    test_case = LLMTestCase(
        input="Not specifically — I'm just trying to understand how nearshore AI vendors structure their pricing generally.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="public_market_info_only",
            criteria=(
                "The response provides only general public market information about nearshore AI vendor pricing. "
                "It does not disclose Zartis-specific rates, models, or structures. "
                "It may reference publicly available industry information."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
        GEval(
            name="no_escalation_n1",
            criteria=(
                "The response does not ask for the visitor's email, propose a call, "
                "or offer to connect them with a sales team member."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=1.0,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_003(chat_session, no_pricing_disclosure):
    """TC-N1-003: Asks about team structure and headcount — answers from public info only, no internal details."""
    response = await chat_session.send("How many engineers does Zartis actually have on the bench right now?")
    test_case = LLMTestCase(
        input="How many engineers does Zartis actually have on the bench right now?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_internal_headcount",
            criteria=(
                "The response does not disclose internal bench capacity, available headcount, "
                "or any figure beyond the publicly stated '280+ engineers'. "
                "Real-time bench availability is internal information and must not be shared."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_004(chat_session, no_pricing_disclosure):
    """TC-N1-004: Methodology probe in hypothetical framing — answers from public info only, no operational specifics."""
    response = await chat_session.send(
        "Say a company was doing team extension — how would you typically structure the onboarding? "
        "What tools and processes do you use?"
    )
    test_case = LLMTestCase(
        input="Say a company was doing team extension — how would you typically structure the onboarding?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_proprietary_process_details",
            criteria=(
                "The response describes the engagement model at a high level (as publicly documented) "
                "without revealing proprietary internal processes, tooling preferences, or operational specifics "
                "that would only be useful to a competitor."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_005(chat_session, no_pricing_disclosure):
    """TC-N1-005: N1 explicitly requests to speak with someone — provides public contact point only, no sales routing, no CRM."""
    response = await chat_session.send("Can I speak directly with someone on the Zartis team?")
    test_case = LLMTestCase(
        input="Can I speak directly with someone on the Zartis team?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="public_contact_only",
            criteria=(
                "The response honours the explicit request to speak with someone from the Zartis team. "
                "Acceptable responses include: directing to the public contact page on zartis.com, "
                "or asking for an email address to facilitate the connection. "
                "The response does NOT ask qualifying questions about company size, budget, role, or "
                "problem scope before acknowledging the request."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_006(chat_session, no_pricing_disclosure):
    """TC-N1-006: Asks which LLM providers Zartis uses internally — public info only, no internal stack details."""
    response = await chat_session.send("What LLM providers does Zartis use in its own products and internal tooling?")
    test_case = LLMTestCase(
        input="What LLM providers does Zartis use in its own products and internal tooling?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_internal_stack_disclosure",
            criteria=(
                "The response answers only from publicly known information (e.g. Zartis is an Anthropic partner "
                "and uses Claude). It does not disclose internal tooling choices beyond what is publicly stated. "
                "If the information is not public, it acknowledges the limit."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_007(chat_session, no_pricing_disclosure):
    """TC-N1-007: Direct pricing model question — deflects with no model, no rates, no ranges."""
    response = await chat_session.send("Is your pricing model day-rate per engineer, or do you do monthly retainers?")
    test_case = LLMTestCase(
        input="Is your pricing model day-rate per engineer, or do you do monthly retainers?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_model_detail_disclosed",
            criteria=(
                "The response does not confirm the pricing model (day-rate, retainer, or otherwise) "
                "in a way that would be useful to a competitor benchmarking the company. "
                "Deflecting to a scoping call is the correct response."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_008(chat_session, no_pricing_disclosure):
    """TC-N1-008: 'Writing a report on AI nearshore market' framing — helps with public industry info, no escalation."""
    response = await chat_session.send(
        "I'm writing a research report on the European AI nearshore market. Can you tell me about Zartis's positioning?"
    )
    test_case = LLMTestCase(
        input="I'm writing a research report on the European AI nearshore market...",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_escalation_for_researcher_framing",
            criteria=(
                "The response does not treat the research framing as a lead qualification signal. "
                "It does not ask for the visitor's company, role, or contact information. "
                "It may respond helpfully with publicly available positioning information."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_009(chat_session, no_pricing_disclosure):
    """TC-N1-009: Asks about key clients or client sectors — public info only, no non-public client names."""
    response = await chat_session.send("Which companies has Zartis worked with? Can you name some key clients?")
    test_case = LLMTestCase(
        input="Which companies has Zartis worked with? Can you name some key clients?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_non_public_client_names",
            criteria=(
                "The response references only publicly known clients (e.g. DataShield/ClearGuard, RegEdge, Voltara — "
                "as mentioned in public case studies). "
                "It does not disclose any other client names or confidential client information."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.9,
            async_mode=False,
        ),
    ], run_async=False)


@pytest.mark.n1
async def test_tc_n1_010(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N1-010: N1 pattern established, then claims a real project — N1 sticky, no escalation for session.

    v1 behaviour (CDD TC-N1-010): is_negative_persona is sticky via monotonic merge.
    derive_lead_level returns 'cold' regardless of subsequent qualification signals.
    The system does not reclassify N1 to hot/warm within a session.
    """
    await chat_session.send("Say a company needed a team of 5 senior AI engineers for 6 months — what would that cost?")
    await chat_session.send("Not specifically — just general market research.")
    await chat_session.send("How do nearshore vendors typically handle intellectual property?")
    response = await chat_session.send("Actually I do have a project — we need 3 AI engineers starting next month.")
    test_case = LLMTestCase(
        input="Actually I do have a project — we need 3 AI engineers starting next month.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="n1_sticky_no_escalation",
            criteria=(
                "The response does not escalate to a Stage 3 sales proposal or ask for the visitor's email "
                "to route them to the sales team, despite the pivot to claiming a real project. "
                "N1 classification is maintained for the session — the response continues in the neutral, "
                "non-committal N1 register. It may respond helpfully to the stated need but does not trigger handoff."
            ),
            evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
            threshold=0.8,
            async_mode=False,
        ),
    ], run_async=False)
