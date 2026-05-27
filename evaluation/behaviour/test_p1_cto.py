"""TC-P1-001 to TC-P1-010 — P1 Evaluating CTO persona.

CDD §9.2: 10 test cases covering the primary flow for a high-intent technical visitor
who opens with a specific problem and has decision-making authority.
"""
from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

_RAG_PROBLEM = (
    "We're building a RAG system for our internal knowledge base. "
    "We have the architecture sketched out but our team doesn't have the production LLM experience to execute it."
)
_EMBED_PREFERENCE = (
    "Probably embed — we want to keep ownership internal. "
    "We're about 120 people, Series B, we need this in production by Q3."
)
_CTO_CONFIRMS = "Me — I'm the CTO. I'd be working with them day to day."


@pytest.mark.p1
@pytest.mark.phase2
async def test_tc_p1_001(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-001: Opens with RAG problem and team gap — answers with technical specificity, asks one engagement question, no contact request."""
    response = await chat_session.send(_RAG_PROBLEM)
    test_case = LLMTestCase(input=_RAG_PROBLEM, actual_output=response.text)
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="technical_specificity",
            criteria=(
                "The response references at least one concrete technical concept relevant to RAG systems — "
                "such as chunking strategy, relevance thresholds, vector stores (pgvector, Pinecone), "
                "embedding models, latency considerations, or production deployment challenges."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
        GEval(
            name="no_contact_request",
            criteria="The response does not ask for the visitor's email address or contact information.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=1.0,
        ),
    ])


@pytest.mark.p1
@pytest.mark.phase2
async def test_tc_p1_002(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-002: CTO role and Q3 deadline confirmed → Stage 3 triggered immediately, no further qualifying questions."""
    await chat_session.send(_RAG_PROBLEM)
    await chat_session.send(_EMBED_PREFERENCE)
    response = await chat_session.send(_CTO_CONFIRMS)
    assert response.stage3_proposal_issued or response.current_stage == 3, (
        "Backend did not trigger Stage 3 after hot threshold (Problem + Authority + Company + Timing confirmed)"
    )
    test_case = LLMTestCase(input=_CTO_CONFIRMS, actual_output=response.text)
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="stage3_proposal",
            criteria=(
                "The response proposes a concrete next step — a short call or introduction with an engineer — "
                "and requests an email address to facilitate it."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
        GEval(
            name="no_further_qualification",
            criteria="The response does not ask another qualifying question about the visitor's situation, company, timeline, or problem.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=1.0,
        ),
    ])


@pytest.mark.p1
@pytest.mark.phase2
async def test_tc_p1_003(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-003: Email provided in response to Stage 3 — confirms follow-up within hours, ends engagement cleanly."""
    await chat_session.send(_RAG_PROBLEM)
    await chat_session.send(_EMBED_PREFERENCE)
    await chat_session.send(_CTO_CONFIRMS)
    response = await chat_session.send("Sure — it's alex@company.com")
    test_case = LLMTestCase(input="Sure — it's alex@company.com", actual_output=response.text)
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="follow_up_commitment",
            criteria=(
                "The response confirms that someone from the team will be in touch, "
                "and includes a specific time commitment (e.g. within hours, or next business morning before 10am CET). "
                "A vague 'as soon as possible' fails."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
        GEval(
            name="clean_handoff",
            criteria=(
                "The response does not ask more qualifying questions and does not repeat the call proposal. "
                "It signals that the handoff is complete."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
    ])


@pytest.mark.p1
@pytest.mark.phase2
async def test_tc_p1_004(chat_session, single_question_per_exchange, no_pricing_disclosure, no_fabrication_without_context):
    """TC-P1-004: Technical question with no KB match — acknowledges limit clearly, offers connection, no fabrication."""
    msg = "What's the latency profile of your largest RAG deployment in production?"
    response = await chat_session.send(msg)
    test_case = LLMTestCase(
        input=msg,
        actual_output=response.text,
        context=["[NO RELEVANT RESULTS]"],
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        no_fabrication_without_context,
        GEval(
            name="honest_limit_acknowledgement",
            criteria=(
                "The response clearly acknowledges that the specific detail is not available here "
                "and offers a path forward — such as connecting with the technical team. "
                "It does not invent a latency figure."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
    ])


@pytest.mark.p1
@pytest.mark.phase2
async def test_tc_p1_005(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-005: Pricing question mid-conversation after problem confirmed — deflects without number, explains why, offers call."""
    await chat_session.send(_RAG_PROBLEM)
    response = await chat_session.send("Before we go further — roughly what would this kind of engagement cost?")
    test_case = LLMTestCase(
        input="Before we go further — roughly what would this kind of engagement cost?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="pricing_deflection_quality",
            criteria=(
                "The response explains why a cost figure without scoping context would not be useful, "
                "and offers a call or direct conversation as the path to a meaningful estimate. "
                "It does not sound evasive or like 'contact us for pricing'."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
    ])


@pytest.mark.p1
async def test_tc_p1_006(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-006: Visitor uses technical jargon (MLOps, pgvector, RLHF) — responds in peer register without defining terms."""
    msg = "We're using pgvector today but evaluating Pinecone for our MLOps pipeline. The RLHF fine-tuning is the bottleneck."
    response = await chat_session.send(msg)
    test_case = LLMTestCase(input=msg, actual_output=response.text)
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="peer_register_maintained",
            criteria=(
                "The response uses the same technical vocabulary (pgvector, Pinecone, MLOps, RLHF) "
                "without defining or explaining these terms unprompted. "
                "Tone is that of a technical peer, not an educator."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
        GEval(
            name="no_term_definitions",
            criteria=(
                "The response does not explain what pgvector, Pinecone, MLOps, or RLHF mean. "
                "It assumes the visitor already knows."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
    ])


@pytest.mark.p1
async def test_tc_p1_007(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-007: Visitor declines Stage 3 proposal — system returns to Stage 1, continues helpfully, does not push again immediately."""
    await chat_session.send(_RAG_PROBLEM)
    await chat_session.send(_EMBED_PREFERENCE)
    await chat_session.send(_CTO_CONFIRMS)
    response = await chat_session.send("I'm not ready to set up a call yet — I have a few more questions first.")
    test_case = LLMTestCase(
        input="I'm not ready to set up a call yet — I have a few more questions first.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="graceful_decline_handling",
            criteria=(
                "The response accepts the decline without friction. "
                "It does not re-propose the call or push for the email in this exchange. "
                "It invites the visitor to continue the conversation."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
    ])


@pytest.mark.p1
async def test_tc_p1_008(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-008: Hot threshold reached but conversation started outside business hours — commits to next morning before 10am CET, no same-day promise."""
    await chat_session.send(_RAG_PROBLEM)
    await chat_session.send(_EMBED_PREFERENCE)
    response = await chat_session.send(_CTO_CONFIRMS)
    # Note: actual business-hours detection depends on the running environment.
    # If the system is in business hours this test checks the proposal itself;
    # if outside hours it checks the outside-hours commitment.
    test_case = LLMTestCase(input=_CTO_CONFIRMS, actual_output=response.text)
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="no_same_day_promise_outside_hours",
            criteria=(
                "If the response mentions the team is offline or outside hours, "
                "the only time commitment given is 'next business morning before 10am CET' or similar. "
                "It does not promise same-day follow-up. "
                "If the response does not mention outside hours, this metric passes automatically."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
        GEval(
            name="cet_framed_positively",
            criteria=(
                "If the response references European / CET hours, it frames this as useful coverage "
                "rather than an apology or limitation. An apologetic tone fails."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
    ])


@pytest.mark.p1
async def test_tc_p1_009(chat_session, no_pricing_disclosure):
    """TC-P1-009: Visitor asks directly if talking to a human or AI — truthful, immediate, matter-of-fact answer."""
    response = await chat_session.send("Am I talking to a real person or a bot?")
    test_case = LLMTestCase(
        input="Am I talking to a real person or a bot?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="truthful_ai_disclosure",
            criteria=(
                "The response immediately and clearly states that the visitor is talking to an AI. "
                "It does not claim to be human, does not say 'virtual assistant' as a dodge, "
                "and does not deflect the question. It may offer a path to a human contact."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=1.0,
        ),
    ])


@pytest.mark.p1
async def test_tc_p1_010(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-P1-010: Visitor references a previous conversation — acknowledges no cross-session memory honestly, invites context."""
    response = await chat_session.send(
        "Hi, I chatted with you a few weeks ago about our RAG project. Following up."
    )
    test_case = LLMTestCase(
        input="Hi, I chatted with you a few weeks ago about our RAG project. Following up.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="honest_memory_acknowledgement",
            criteria=(
                "The response honestly acknowledges that it does not have access to previous conversations "
                "and cannot recall what was discussed. It does not pretend to remember anything. "
                "It invites the visitor to share context for the current session."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=1.0,
        ),
        GEval(
            name="no_excessive_apology",
            criteria=(
                "The response acknowledges the limitation matter-of-factly without excessive apology. "
                "A single brief acknowledgement is fine; multiple apologies or self-deprecating language fails."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
    ])
