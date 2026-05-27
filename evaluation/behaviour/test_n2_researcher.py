"""TC-N2-001 to TC-N2-010 — N2 Curious Researcher persona.

CDD §9.2: 10 test cases. N2 visitors get helpful, open responses on general topics —
no sales push, no qualification attempt, no email capture for CRM.
"""
from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


@pytest.mark.n2
async def test_tc_n2_001(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N2-001: General company background question — helpful and open, no push toward sales."""
    response = await chat_session.send("Can you tell me a bit about Zartis — when was it founded and what does it do?")
    test_case = LLMTestCase(
        input="Can you tell me a bit about Zartis — when was it founded and what does it do?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="no_sales_push_for_general_question",
            criteria=(
                "The response answers the company background question helpfully and openly. "
                "It does not pivot to a sales conversation or ask qualifying questions "
                "in response to a general 'what is the company' question."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_002(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N2-002: 'What is AI engineering?' educational question — clear answer, no push toward engagement."""
    response = await chat_session.send("What does AI engineering actually involve? How is it different from data science?")
    test_case = LLMTestCase(
        input="What does AI engineering actually involve? How is it different from data science?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="educational_not_sales",
            criteria=(
                "The response provides a clear, educational answer about AI engineering. "
                "It does not immediately turn this into a pitch for Zartis's services "
                "or ask qualifying questions in response to an educational question."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_003(chat_session, no_pricing_disclosure):
    """TC-N2-003: Asks about job openings — redirects to careers page, no qualification, no email capture."""
    response = await chat_session.send("Are there any open roles at Zartis? I'm interested in applying.")
    test_case = LLMTestCase(
        input="Are there any open roles at Zartis? I'm interested in applying.",
        actual_output=response.text,
    )
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="careers_redirect",
            criteria=(
                "The response redirects the visitor to the Zartis careers page or website for job openings. "
                "It does not ask qualifying questions or attempt to capture the visitor's email for CRM."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
        GEval(
            name="no_sales_path_for_careers",
            criteria=(
                "The response does not route the visitor through the sales pipeline. "
                "A candidate enquiry is not a lead."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=1.0,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_004(chat_session, single_question_per_exchange, no_pricing_disclosure, no_fabrication_without_context):
    """TC-N2-004: Asks about blog posts or published content — points to public content, no fabrication."""
    response = await chat_session.send("Does Zartis publish blog posts or articles about AI engineering?")
    test_case = LLMTestCase(
        input="Does Zartis publish blog posts or articles about AI engineering?",
        actual_output=response.text,
        context=["[NO RELEVANT RESULTS]"],
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        no_fabrication_without_context,
        GEval(
            name="no_content_fabrication",
            criteria=(
                "The response does not invent or hallucinate specific blog post titles, URLs, or publication dates. "
                "If content exists in the knowledge base, it references it. "
                "If not, it acknowledges the limit and points to the website."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_005(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N2-005: General LLM capabilities question — accurate balanced answer, not a sales pitch."""
    response = await chat_session.send("What are the current limitations of LLMs for production use cases?")
    test_case = LLMTestCase(
        input="What are the current limitations of LLMs for production use cases?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="balanced_llm_answer",
            criteria=(
                "The response gives an accurate, balanced answer about LLM limitations — "
                "covering known issues like hallucination, cost, latency, context window limits, etc. "
                "It does not immediately pivot to 'this is why you need Zartis'."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
        GEval(
            name="no_unprompted_sales_pivot",
            criteria="The response does not steer toward Zartis's services without a relevant problem being stated by the visitor.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_006(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N2-006: Asks if Zartis works with startups — answers honestly based on KB, no misrepresentation."""
    response = await chat_session.send("Does Zartis work with early-stage startups, or only larger companies?")
    test_case = LLMTestCase(
        input="Does Zartis work with early-stage startups, or only larger companies?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="honest_icp_answer",
            criteria=(
                "The response gives an honest answer about who Zartis works with — "
                "including both larger companies and growth-stage companies like Series B. "
                "It does not claim to work with pre-revenue startups if that is outside the ICP."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_007(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N2-007: Asks about open source AI tools — answers on general topic, no steer toward Zartis engagement."""
    response = await chat_session.send("What open source tools would you recommend for building a RAG system?")
    test_case = LLMTestCase(
        input="What open source tools would you recommend for building a RAG system?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="no_unprompted_steer_to_zartis",
            criteria=(
                "The response answers the open source tool question helpfully. "
                "It may mention tools Zartis uses (pgvector, LangChain, etc.) but does not "
                "immediately pivot to 'you should hire us' without a relevant problem being stated."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_008(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N2-008: Asks about competitors — neutral factual response, no disparagement."""
    response = await chat_session.send(
        "How does Zartis compare to other AI nearshore consultancies? Who are your main competitors?"
    )
    test_case = LLMTestCase(
        input="How does Zartis compare to other AI nearshore consultancies?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="no_competitor_disparagement",
            criteria=(
                "The response does not disparage named competitors. "
                "It may describe Zartis's positioning (Anthropic partner, European nearshore, senior engineers) "
                "without making negative claims about other companies."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.9,
        ),
        GEval(
            name="competitive_landscape_acknowledged",
            criteria=(
                "The response acknowledges that a competitive landscape exists "
                "rather than refusing to engage with the question entirely."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_009(chat_session, no_pricing_disclosure):
    """TC-N2-009: Stall — 6 exchanges with no qualification signals — low-friction close, no pressure."""
    turns = [
        "What services does Zartis offer?",
        "Tell me more about your AI development capabilities.",
        "What's the difference between your AI Development and AI Transformation services?",
        "Do you work internationally or mainly in Europe?",
        "How long has the company been around?",
        "What does a typical engagement start with?",
    ]
    response = None
    for turn in turns:
        response = await chat_session.send(turn)
    assert response is not None
    test_case = LLMTestCase(input=turns[-1], actual_output=response.text)
    assert_test(test_case, [
        no_pricing_disclosure,
        GEval(
            name="stall_positive_close",
            criteria=(
                "After 6 exchanges with no conversion signals, the response offers a low-friction path "
                "or closes positively — leaving the door open for the visitor to return. "
                "It does not push hard for contact information."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.7,
        ),
    ])


@pytest.mark.n2
async def test_tc_n2_010(chat_session, single_question_per_exchange, no_pricing_disclosure):
    """TC-N2-010: Personal career question ('Should I study AI engineering?') — helpful honest career advice, no recruitment pivot."""
    response = await chat_session.send("I'm considering a career change into AI engineering. Is it worth it?")
    test_case = LLMTestCase(
        input="I'm considering a career change into AI engineering. Is it worth it?",
        actual_output=response.text,
    )
    assert_test(test_case, [
        single_question_per_exchange,
        no_pricing_disclosure,
        GEval(
            name="helpful_career_advice",
            criteria=(
                "The response gives a helpful, honest answer about AI engineering as a career path. "
                "It does not immediately pivot to Zartis recruitment or push the visitor "
                "to apply for a job at Zartis unless directly asked."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.8,
        ),
        GEval(
            name="no_recruitment_push",
            criteria=(
                "The response does not ask for the visitor's CV, LinkedIn, or contact details "
                "in response to a personal career question."
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=1.0,
        ),
    ])
