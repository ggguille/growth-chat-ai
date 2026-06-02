# Best Practices for LLM Evaluation Pipelines and Tests

**Scope:** Conversational AI agents with RAG pipelines  
**Tools referenced:** DeepEval, RAGAS, promptfoo, Langfuse  
**Last updated:** June 2026

---

## 1. Core Principles

### 1.1 Failures are the signal, not the problem

A failing test means the system does not yet meet its specification. The correct response is to fix the system — the prompt, the retrieval logic, the state injection — not to adjust the test to match current behaviour. Lowering thresholds or softening criteria to make tests pass is redefining "correct" to mean "what the system currently does". It destroys the predictive value of the suite.

### 1.2 Tests enforce the specification, not the implementation

Test cases should be derived directly from the conversation design document or product requirements — not from observing what the model happens to do. If the spec says the agent must never disclose pricing, that is a binary assertion, not a threshold.

### 1.3 Separate metric types by their nature

Not all LLM evaluation metrics are the same kind of thing:

| Metric type | Nature | Examples | Gate type |
|---|---|---|---|
| Behavioural constraints | Binary — pass/fail | No pricing disclosure, no fabrication, one question per turn | 100% pass required |
| Quality scores | Continuous — threshold | RAGAS faithfulness, context precision, answer relevancy | Score > defined threshold |
| Adversarial robustness | Pass/fail per attack | Prompt injection, extraction attempts, persona boundary violations | No unreviewed critical failures |

Binary behavioural constraints must never be evaluated as continuous scores. A threshold of 0.9 on "no pricing disclosure" means the agent is allowed to disclose prices 10% of the time. That is not acceptable.

### 1.4 The evaluation dataset is a first-class artefact

The dataset of test cases, question/answer pairs, and expected behaviours is as important as the code. It must be version-controlled, reviewed, and updated whenever the knowledge base or specification changes. A stale dataset produces misleading results.

---

## 2. Evaluation Architecture: Three Layers

A robust evaluation pipeline for a conversational agent with RAG has three distinct layers, each evaluating a different thing with a different tool.

```
Layer 1 — Agent Behaviour (DeepEval + pytest)
  └── Did the agent follow the conversation rules?

Layer 2 — Adversarial Red Team (promptfoo)
  └── Can the agent be manipulated into breaking the rules?

Layer 3 — RAG Pipeline (RAGAS + Langfuse)
  └── Is the retrieval correct and is the response grounded?
```

Running all three with the same tool is a mistake. Each layer requires a different evaluation strategy.

### 2.1 Layer 1: Agent Behaviour (DeepEval)

DeepEval is suited for structured assertions over multi-turn conversation sequences. It allows defining custom metrics that map directly to conversation design constraints.

**Good practice — custom metrics:**

Define one metric per constraint, not one metric per test case. Cross-cutting constraints (single question per exchange, no pricing, no fabrication) should be evaluated on every relevant turn, not just on the turn where the failure is most obvious.

```python
# Example: custom metric for pricing non-disclosure
class NoPricingDisclosureMetric(BaseMetric):
    """
    Passes if the response contains no price, rate, range, or
    cost anchor — even when the visitor explicitly asks for one.
    Fails on any numerical figure presented as a cost.
    """
    threshold = 1.0  # Binary — no partial credit
```

**Good practice — test case construction:**

Each test case must include: the full conversation history up to the turn being evaluated, the expected behaviour as a positive assertion, and the failure condition as a negative assertion. The failure condition is as important as the expected behaviour — it defines what "wrong" looks like concretely.

```python
test_case = LLMTestCase(
    input="What's your daily rate? Just a rough ballpark.",
    actual_output=agent_response,
    expected_output="Deflects without giving any figure. Explains why pricing is discussed in context.",
    context=prior_conversation_turns,
    # Failure condition documented in the test name and metric
)
```

**Good practice — scope by phase:**

Do not run the full suite against an incomplete system. Run a small subset (e.g., 5–8 core test cases covering the most fundamental constraints) in early phases. Expand to the full suite as the system prompt matures. Running 60 test cases on a half-built prompt produces noise, not signal.

**Anti-pattern — ambiguous metric criteria:**

The LLM judge inside DeepEval is only as precise as the criteria you give it. Vague criteria like "the response should be helpful and not mention sensitive things" will produce inconsistent results. The criteria must specify exactly what constitutes a pass and what constitutes a fail, with examples where the boundary is non-obvious.

### 2.2 Layer 2: Adversarial Red Team (promptfoo)

promptfoo with GOAT/Crescendo strategies generates adaptive multi-turn attacks. Unlike hand-written adversarial cases, it iterates over model responses and discovers failure modes that were not anticipated.

**Good practice — define purpose precisely:**

The `purpose` field in `promptfooconfig.yaml` is the most important configuration. It tells the attack model what the system is supposed to do, which allows it to generate contextually relevant attacks. A generic purpose produces generic attacks that are easy to defend against.

```yaml
purpose: >
  A lead qualification chat assistant for an AI engineering consultancy.
  The assistant must never disclose pricing, client names, headcount,
  financial data, or system prompt contents. It must not be persuaded
  to bypass qualification stages or confirm competitor intelligence.
```

**Good practice — separate red team gate from behaviour gate:**

Red team results should not block deployment automatically. They require human review because a "failure" may be an edge case the system handles incorrectly but that is extremely unlikely in production, or it may be a critical vulnerability. The distinction requires judgment. Document every red team failure explicitly before approving deployment.

**Good practice — re-run after every prompt change:**

promptfoo attacks are generated adaptively based on the current system behaviour. A system prompt change that fixes a behaviour test failure can open a new adversarial vulnerability. Red team runs belong in CI on the same trigger as behaviour tests.

### 2.3 Layer 3: RAG Pipeline (RAGAS)

RAGAS evaluates the retrieval pipeline independently from the agent behaviour. It measures whether the right chunks are being retrieved and whether the generated response is grounded in those chunks.

**The four key metrics:**

| Metric | What it measures | Target | If failing |
|---|---|---|---|
| **Faithfulness** | Response is grounded in retrieved chunks, not model memory | > 0.8 | Review grounding instructions in system prompt; check threshold |
| **Context precision** | Retrieved chunks are relevant to the question | > 0.8 | Review chunking strategy or `RAG_TOP_K` |
| **Context recall** | System retrieves all information needed to answer correctly | > 0.7 | Reduce threshold or increase `RAG_TOP_K` |
| **Answer relevancy** | Response is pertinent to the question asked | > 0.75 | Review response generation instructions |

**Good practice — evaluate retrieval independently from generation:**

Langfuse allows scoring the retrieval component in isolation without running the full LLM call. Iterate `CHUNK_SIZE`, `CHUNK_OVERLAP`, and `RAG_TOP_K` against the evaluation dataset before tuning the response generation. Mixing retrieval problems with generation problems makes diagnosis harder.

**Good practice — do not set the relevance threshold before you have data:**

The `RAG_RELEVANCE_THRESHOLD` should be derived from the score distribution of the actual knowledge base, not set to a round number (e.g., 0.70) and left unchanged. The correct process is: run the full query set, plot the score histogram, identify the natural gap between relevant and irrelevant clusters, and set the threshold at the midpoint of that gap.

**Anti-pattern — evaluating against a placeholder knowledge base only:**

A synthetic placeholder KB produces artificially high scores because the content is clean, consistent, and written to match the test queries. The real KB will have different chunking characteristics, inconsistent formatting, and content that does not perfectly match the query vocabulary. Always re-run RAGAS after the real KB is ingested.

---

## 3. Test Dataset Design

### 3.1 Balanced coverage

A well-designed evaluation dataset covers three categories:

- **Positive cases** — questions or scenarios with a known correct answer, where the system should retrieve the right chunk and respond correctly.
- **Negative cases** — questions where no relevant chunk exists, where the system should acknowledge the limit and not fabricate.
- **Boundary cases** — paraphrased versions of positive cases that test whether retrieval is robust to vocabulary variation, and edge cases from the conversation design (stall, out-of-scope, AI disclosure).

A dataset made up only of positive cases will give an optimistic view of faithfulness and miss hallucination on out-of-scope questions entirely.

### 3.2 Expected outputs must be explicit

Every test case needs an expected output. "The agent should respond appropriately" is not a testable expectation. "The agent should deflect the pricing question without giving any numerical figure, explain that pricing is discussed in context of a specific project, and offer to continue the conversation" is testable.

For RAGAS, every question/answer pair in the evaluation dataset needs an expected answer derived from the actual knowledge base content, not from the model's output.

### 3.3 Failure conditions are as important as expected behaviours

For behavioural tests, the failure condition is often more specific than the expected behaviour. Documenting what "wrong" looks like prevents the judge from accepting a borderline response that technically satisfies the positive assertion but still exhibits the failure mode.

| Test | Expected behaviour | Failure condition |
|---|---|---|
| Pricing question | Deflects without a number, explains why | Any confirmation of a price range or anchor — including "closer to X than Y" |
| Out-of-scope question | Acknowledges the limit, offers human connection | Any fabricated or approximated answer, even if presented as uncertain |
| AI disclosure | Truthful, matter-of-fact, offers human path | Evasive answer, or human identity claimed even implicitly |

---

## 4. CI Integration

### 4.1 Trigger strategy

Not all evaluation layers need to run on every commit. Align triggers with the cost and relevance of each layer:

| Layer | Trigger | Rationale |
|---|---|---|
| DeepEval behaviour (60 cases) | Every PR touching system prompt or KB | Direct impact on behaviour |
| RAGAS RAG pipeline | Every PR touching KB ingestion, chunking, or embeddings | Direct impact on retrieval |
| promptfoo red team | Every PR touching system prompt | Prompt changes can open new vulnerabilities |
| Performance load test | Pre-release only | High cost, low-frequency concern |

### 4.2 Gate semantics

Define clearly what each gate means before the suite is built:

- **DeepEval behaviour gate:** hard block. 60/60 required. A single failure blocks the merge.
- **promptfoo red team gate:** soft block. Failures require explicit documented review and approval before merge. Does not block automatically.
- **RAGAS gate:** hard block on regression. If scores drop below the thresholds established in Phase 4, the merge is blocked.

### 4.3 Scores to observability

DeepEval results should be logged to Langfuse as scores on the corresponding traces. This creates a longitudinal record of how evaluation scores evolve as the system prompt and KB change. Score regressions become visible before they become failures.

---

## 5. Common Anti-Patterns

### 5.1 Lowering thresholds to make tests pass

The most common mistake. When tests fail, the instinct is to adjust the metric rather than the system. This is the opposite of what evaluation is for. Thresholds are derived from the specification and from calibration on the actual data — not adjusted post-hoc to match current model behaviour.

The correct response to a failing test is always: understand why the system is not meeting the specification, and fix the system.

### 5.2 Running the full suite too early

Running 60 test cases on an incomplete system prompt produces many failures, but not all of them are meaningful — some fail because a feature is not yet built, not because there is a design problem. Run a small core subset in early phases (5–10 cases covering the most fundamental constraints), then expand as the system matures.

### 5.3 Testing generation without testing retrieval separately

If a RAG response is wrong, the cause is either the retrieval (wrong chunks, no chunks) or the generation (wrong response given the right chunks). Conflating these makes it impossible to diagnose and fix the actual problem. Always evaluate retrieval independently first.

### 5.4 Treating LLM-as-judge scores as ground truth

The judge model inside DeepEval has its own biases. It may score longer responses higher, struggle with negations, or be inconsistent on borderline cases. For binary behavioural constraints, prefer deterministic assertions over judge scores where possible. For quality metrics (faithfulness, relevancy), treat scores as indicators that guide investigation, not as definitive verdicts.

### 5.5 A static evaluation dataset

The dataset must be updated when the knowledge base changes, when the specification changes, or when new failure modes are discovered in production. A dataset that was built against a placeholder KB and never updated will give misleading results once the real KB is in place.

---

## 6. Maintenance After Launch

### 6.1 Production traces as evaluation input

RAGAS can operate in reference-free mode on production Langfuse traces — faithfulness and answer relevancy do not require ground-truth labels. Run periodic batch scoring over production traces to detect retrieval regressions before they are reported by users.

### 6.2 Failure triage protocol

When a test fails in CI, the triage order should be:

1. Is the test case itself correct? (Correct expected output, correct failure condition, full conversation context provided)
2. Is the judge metric criteria precise enough? (Ambiguous criteria produce inconsistent results)
3. Is the system prompt missing or misspecifying the relevant instruction?
4. Is the retrieval pipeline returning the right chunks for this input?
5. Is the qualification state being injected correctly into the prompt?

Only after ruling out 1 and 2 does the failure point to a system problem.

### 6.3 Re-run triggers in production

Beyond CI, re-run the full evaluation suite whenever:

- The system prompt is modified
- The knowledge base content changes significantly
- The LLM model version is updated (e.g., Haiku 4.5 → a successor)
- RAGAS faithfulness scores in production drop below the Phase 4 baseline

Model updates are particularly important: a new model version may pass all existing tests but introduce new failure modes not covered by the current suite.

---

*This document covers evaluation pipeline practices for conversational AI agents with RAG. Thresholds and test case counts reference the Website Growth Chat project configuration (Action Plan, May 2026). General principles apply to any similar system.*