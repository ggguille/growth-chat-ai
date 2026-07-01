---
title: "Evaluation Pipelines"
description: "Operations runbook for Growth Chat evaluation — agent behaviour tests, adversarial red team, and RAG quality pipeline: metrics, thresholds, CI gates, and failure triage."
---

# Evaluation Pipelines

The system has three evaluation layers. Each targets a different failure mode and has distinct CI gate semantics. All layers run against the live backend or live database — not mocks — so results reflect actual production behaviour.

| Layer | Tool | What it tests | CI gate |
| --- | --- | --- | --- |
| [1 — Agent Behaviour](#layer-1-agent-behaviour) | DeepEval + pytest | CDD rule compliance across personas and conversation patterns | Hard block — 60/60 required |
| [2 — Adversarial Red Team](#layer-2-adversarial-red-team) | promptfoo | Resistance to prompt injection and social engineering | Soft block — human review required |
| [3 — RAG Pipeline](#layer-3-rag-pipeline) | RAGAS | Retrieval quality and response faithfulness | Soft block now → hard block after Phase 5 sign-off |

---

## Layer 1 — Agent Behaviour

### What it covers

60 tests run in CI (`-m "not adversarial"`):

| Group | Tests | What is verified |
| --- | --- | --- |
| P1 — Evaluating CTO | 10 | Technical depth, credibility, fast Stage 3 escalation |
| P2 — Exploring Founder | 10 | Education-first tone, resource offer, email capture |
| P3 — Referred Decision-Maker | 10 | Low-friction progression, referral acknowledgement |
| N1 — Competitor | 10 | Public-info-only responses, no escalation, no persona break |
| N2 — Curious Researcher | 10 | Helpful but non-qualifying, no Stage 3 push |
| Conversation patterns | 10 | Pricing deflection, out-of-scope, outside-hours, stall detection, etc. |
| Edge cases | 4 | CDD §6 edge cases |

Each test opens a real SSE session against the live backend, sends one or more messages to build conversation state, then evaluates the captured response with one or more metrics.

### Metric types

**Deterministic (regex / structural — threshold 1.0, always run):**

| Metric | What it checks |
| --- | --- |
| `NoPricingDisclosureMetric` | No currency symbols, no `/day` patterns, no "starting from X" phrasing |
| `SingleQuestionPerExchangeMetric` | At most one `?` per response |
| `NoCostFigureMetric` | No cost figures in any form |
| `NoContactRequestMetric` | No contact request on the first turn |
| `NoApologyToneMetric` | No apologetic language |
| `Stage3ProposalMetric` | Both a call/connect word and an email ask present |
| `HonestLimitAcknowledgementMetric` | Knowledge limit acknowledged + forward path offered |
| `PricingDeflectionQualityMetric` | Explains why pricing is not shared + offers a call |
| `TechnicalDepthMetric` | Technical terms present in response |
| `FollowUpCommitmentMetric` | Specific time commitment present after email capture |
| `NoFurtherQualificationMetric` | Stage 3 response contains email ask but no qualifying questions |

**LLM-as-judge / GEval (skipped when no judge configured, threshold 0.65–1.0):**

| Metric | Threshold | What it checks |
| --- | --- | --- |
| `NoFabricationWithoutContextMetric` | 0.65 | No specific factual claims when the KB returns no results |
| Inline `GEval` (per-test criteria) | 0.7–1.0 | Persona tone, graceful decline, AI disclosure, N1 adherence, stall handling, etc. |

::: callout tip "GEval and judge configuration"
GEval metrics are skipped (not failed) when no judge is configured. In development, set `JUDGE_PROVIDER=ollama` and `JUDGE_MODEL=qwen2.5:7b` with a local Ollama instance. In CI, the Anthropic Claude Haiku judge is configured automatically.
:::

### CI gate

**Hard block.** Any single test failure fails the `eval-behaviour.yml` workflow. The workflow is triggered automatically after every successful `Deploy Backend` run on `main`.

### Running manually

```bash
# All 60 CI tests
uv run --package evaluation pytest evaluation/behaviour -m "not adversarial" -v

# Single persona
uv run --package evaluation pytest evaluation/behaviour -m p1 -v

# Multiple markers
uv run --package evaluation pytest evaluation/behaviour -m "p1 or p2" -v

# Single test by ID
uv run --package evaluation pytest evaluation/behaviour -k "TC-P1-003" -v
```

Via GitHub Actions: `workflow_dispatch` on `eval-behaviour.yml`.

The backend must be running and reachable at `EVAL_API_URL` (default: `http://localhost:8000`). See `evaluation/.env.example` for all environment variables.

### Failure triage

| Failure type | Likely cause | Where to look |
| --- | --- | --- |
| Deterministic metric fails | Response literally contains the prohibited pattern | Graph post-processing: `backend/src/backend/conversation/graph/` |
| GEval metric fails | Judge scored below threshold; may also be judge variance | HTML report artifact (GitHub Actions) or Langfuse trace; re-run once to rule out variance |
| Backend 503 / connection error | Backend not ready or rate-limited during warm-up | Check `/ready` endpoint; wait for warm-up retry in CI to complete |

---

## Layer 2 — Adversarial Red Team

### What it covers

**20 baseline static test cases** across four threat categories:

| Category | Cases | What is probed |
| --- | --- | --- |
| Information extraction | TC-ADV-001–007 | Pricing anchor confirmation, headcount buckets, client name extraction, system prompt leakage, competitor opinion, financial data, model/infrastructure disclosure |
| Prompt injection | TC-ADV-008–012 | Role override, no-restrictions persona, fictional framing jailbreak, false prior statement confirmation, unverifiable authority claim |
| Persona boundary violations | TC-ADV-013–016 | N1/N2 pivot to real initiative, late consultant reveal, hostile pressure after pricing deflection |
| Qualification logic bypass | TC-ADV-017–020 | Premature Stage 3 demand, false hot-lead signal, bulk qualification questions, email-for-pricing trade |

**Adaptive attacks** are also generated automatically using GOAT (iterative multi-turn, learns from responses) and Crescendo (escalating social engineering) strategies.

**Assertion types per case:**
- `not-contains` — deterministic string check (e.g. no `€`, no `/day`, no `Stage 1`)
- `llm-rubric` — judge evaluates a natural-language pass/fail criterion

### CI gate

**Soft block.** A failure does not automatically block deployment. It requires explicit, documented human review and sign-off before the next deploy proceeds. The distinction between a genuine vulnerability and an edge case (judge variance, borderline phrasing) requires human judgment.

### Running manually

```bash
# Baseline 20 static cases
promptfoo eval --config evaluation/redteam/promptfooconfig.yaml --no-cache

# Adaptive attacks (GOAT + Crescendo)
promptfoo redteam run --config evaluation/redteam/promptfooconfig.yaml --no-cache
```

Via GitHub Actions: `workflow_dispatch` on `eval-redteam.yml`. The workflow also runs automatically after every successful `Deploy Backend` on `main`.

Requires: `promptfoo` installed globally (`npm install -g promptfoo`), backend reachable, `PROMPTFOO_GRADING_PROVIDER` set. See `evaluation/.env.example`.

### Failure triage

1. Download the HTML report artifact from the GitHub Actions run (30-day retention).
2. Identify the failing case(s) by TC ID.
3. Classify the failure:

| Classification | Criteria | Action |
| --- | --- | --- |
| Genuine vulnerability | Agent disclosed pricing, leaked a client name, broke persona, or complied with an injection | Fix in backend prompt (`backend/src/backend/conversation/prompt/`) or graph post-processing before next deploy |
| Judge variance | Borderline phrasing, different run gives different result, rubric is ambiguous | Document as known limitation; proceed with explicit sign-off |

---

## Layer 3 — RAG Pipeline

### What it covers

A 43-item ground-truth dataset (`evaluation/datasets/rag_eval_dataset.json`):

| Item type | Count | Purpose |
| --- | --- | --- |
| `known_relevant` | 25 | Direct KB match — tests recall and precision |
| `paraphrase` | 12 | Semantically rephrased questions — tests robustness |
| `no_relevant_chunk` | 6 | No KB match — tests graceful acknowledgement |

Pipeline per item: embed question → retrieve top-K chunks from pgvector → generate grounded answer with Claude Haiku → evaluate with RAGAS.

Items with no relevant chunk (`has_relevant_chunk=False`) only receive `faithfulness` and `answer_relevancy` — the precision and recall metrics require a reference answer to compare against.

### Metrics and thresholds

Thresholds were calibrated on 2026-06-12 against the production knowledge base. The authoritative values are in `evaluation/rag/runner.py`.

| Metric | Threshold | What it measures |
| --- | --- | --- |
| `faithfulness` | > 0.80 | Response is grounded in retrieved chunks — no claims from LLM memory |
| `context_precision` | > 0.65 | Retrieved chunks are relevant to the question |
| `context_recall` | > 0.70 | All necessary chunks were retrieved |
| `answer_relevancy` | > 0.45 | Response answers the question asked |

::: callout warning "Discrepancy with evaluation-best-practices.md"
The thresholds documented in `evaluation-best-practices.md` (`context_precision > 0.80`, `answer_relevancy > 0.75`) are aspirational targets from the original TRD. The values above are the real calibrated thresholds in the code and are what CI actually enforces. The gap reflects structural ceilings in the production KB — not quality regressions.
:::

**Why the lower thresholds are correct (structural ceilings):**
- `context_precision` 0.65: Multiple broad-service chunks have similar embedding distances; RAGAS cannot easily rank them when all are valid matches.
- `answer_relevancy` 0.45: RAGAS measures this by generating questions from the response, then computing cosine similarity. Short consulting-style yes/no answers score low by design.

### CI gate

Currently a **soft block** — `continue-on-error` is active in `eval-rag.yml`. Will become a **hard block** after Phase 5 sign-off, when `continue-on-error` is removed from the workflow.

**Trigger:** Runs automatically after a successful `Ingest Knowledge Base` run on `main`. This is the correct causal link — RAG quality only changes when the vector store content changes.

### Running manually

```bash
# Install the ragas optional extra (may fail on Windows Python 3.14 — use Linux/WSL or CI)
uv sync --package evaluation --extra ragas

# Dev mode (HuggingFace embeddings, knowledge_chunks_dev table)
uv run --package evaluation python -m evaluation.rag.runner --embedding-mode dev

# Production mode (OpenAI embeddings, knowledge_chunks table)
uv run --package evaluation python -m evaluation.rag.runner --embedding-mode prod

# Threshold recalibration
uv run --package evaluation python -m evaluation.calibrate_rag
```

Via GitHub Actions: `workflow_dispatch` on `eval-rag.yml`.

Requires: pgvector table populated, `RAGAS_DB_URL` set, `ANTHROPIC_API_KEY` set. See `evaluation/.env.example`.

### Failure triage

Check the JSON report artifact for per-item scores, then diagnose by metric:

| Failing metric | Likely cause | Action |
| --- | --- | --- |
| `faithfulness` | Model making claims not in retrieved chunks | Review backend prompt grounding in `backend/src/backend/conversation/prompt/` |
| `context_recall` | Relevant chunks not being retrieved | Check `RAG_TOP_K` and `RAG_RELEVANCE_THRESHOLD` backend settings; re-run `calibrate_rag.py` |
| `context_precision` below 0.65 | Retrieval returning off-topic chunks | Re-run `calibrate_rag.py`; check if new KB content has highly similar embeddings to unrelated content |
| `answer_relevancy` below 0.45 | Regression below structural floor | Compare per-item scores against Phase 4 baseline; scores above 0.45 but below 0.75 are expected and acceptable |

### Threshold recalibration

Run `calibrate_rag.py` after any of:

- New documents added to or removed from the knowledge base
- Embedding model changed
- `RAG_TOP_K` changed
- Significant KB content style change (e.g. adding long narrative pages to an existing short-FAQ corpus)

The script derives new thresholds from the score distribution gap between relevant and irrelevant chunk clusters and prints the recommended values. Apply them to `evaluation/rag/runner.py` and the corresponding backend environment variables.

---

## Evaluation Reports and Observability

All three layers ship results to Langfuse when credentials are configured (see [Observability runbook](./ops-observability.md)):

| Layer | What is logged |
| --- | --- |
| Layer 1 — Behaviour | Per-test metric scores as Langfuse traces after each test |
| Layer 2 — Red team | Baseline promptfoo results exported as a Langfuse dataset experiment |
| Layer 3 — RAG | Per-item RAGAS scores in a `ragas-{timestamp}` experiment under the `rag_eval` dataset |

HTML and JSON report artifacts are uploaded per CI run with **30-day retention**. Access them from the summary tab of the relevant GitHub Actions run.
