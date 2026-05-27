# Evaluation Suite

End-to-end quality assurance for the Growth Chat AI assistant. Three complementary layers cover behaviour correctness, adversarial robustness, and RAG retrieval quality.

```text
evaluation/
├── behaviour/              # DeepEval + pytest — persona and pattern tests
│   ├── metrics/            # Custom deterministic and LLM-as-judge metrics
│   ├── test_p1_cto.py      # P1 Evaluating CTO persona (TC-P1-001..010)
│   ├── test_p2_founder.py  # P2 Exploring Founder persona (TC-P2-001..010)
│   ├── test_p3_referred.py # P3 Referred Decision-Maker persona (TC-P3-001..010)
│   ├── test_n1_competitor.py # N1 Competitor persona (TC-N1-001..010)
│   ├── test_n2_researcher.py # N2 Curious Researcher persona (TC-N2-001..010)
│   └── test_patterns.py    # Recurring conversation patterns (TC-PAT-001..010)
├── redteam/
│   └── promptfooconfig.yaml # promptfoo adversarial test suite (TC-ADV-001..020)
├── datasets/
│   └── rag_eval_dataset.json # 43-item RAG ground-truth dataset
├── conftest.py             # Shared fixtures: ChatSession, chat_session
└── .env.example            # Required environment variables
```

---

## How it works

### Layer 1 — Behaviour tests (`behaviour/`)

Live end-to-end tests that drive the real backend API over SSE. Each test creates a fresh `ChatSession` (unique `session_id`) and sends one or more messages, then evaluates the final response with [DeepEval](https://docs.confident-ai.com/) metrics.

**Personas tested:**

| Marker | File | Description |
| --- | --- | --- |
| `p1` | `test_p1_cto.py` | High-intent CTO with a concrete RAG problem — fast Stage 3, technical peer register |
| `p2` | `test_p2_founder.py` | Exploratory founder, no committed budget — warm-lead path, resource-based email capture |
| `p3` | `test_p3_referred.py` | Referred decision-maker — minimal qualification, fast Stage 3, consultant detection |
| `n1` | `test_n1_competitor.py` | Competitor probing for pricing and operational details — public info only, no CRM |
| `n2` | `test_n2_researcher.py` | Curious researcher or student — helpful open answers, no qualification attempt |
| `pattern` | `test_patterns.py` | High-risk recurring situations: pricing under pressure, AI disclosure, stall handling |

**Metrics used:**

| Metric | Type | When required |
| --- | --- | --- |
| `SingleQuestionPerExchangeMetric` | Deterministic (counts `?`) | Most tests — validates CDD §2.2 |
| `NoPricingDisclosureMetric` | LLM-as-judge (GEval, OpenAI) | All tests — zero tolerance for rates |
| `NoFabricationWithoutContextMetric` | LLM-as-judge (GEval, OpenAI) | Tests with `[NO RELEVANT RESULTS]` context |
| Inline `GEval` metrics | LLM-as-judge (GEval, OpenAI) | Per-test criteria specific to each case |

LLM-as-judge metrics **require `OPENAI_API_KEY`** — tests skip automatically if the key is missing.

### Layer 2 — Red team (`redteam/`)

Static adversarial cases plus GOAT and Crescendo adaptive attack strategies, run via [promptfoo](https://promptfoo.dev/). Covers 20 baseline cases (TC-ADV-001..020) across four threat categories:

- **Information extraction** — pricing anchors, headcount probes, client name extraction, system prompt leakage
- **Prompt injection** — role overrides, persona jailbreaks, fictional framing, false prior statements
- **Persona boundary violations** — N1/N2 pivot attacks, late consultant reveal, hostile pressure
- **Qualification logic bypass** — premature Stage 3 demands, false hot-lead signals, email-for-pricing trades

### Layer 3 — RAG dataset (`datasets/`)

43-item ground-truth dataset for evaluating retrieval quality. Used with RAGAS or a custom evaluation harness (not automated in this repo — the dataset is the authoritative reference). Items cover:

| Type | Count | Purpose |
| --- | --- | --- |
| `known_relevant` | 25 | Question has a matching KB chunk — tests recall |
| `paraphrase` | 12 | Same question rephrased — tests semantic robustness |
| `no_relevant_chunk` | 6 | No KB match exists — expected behaviour: acknowledge limit |

---

## Setup

### Prerequisites

- Python 3.14+ managed via `uv` (see `.python-version` at the project root)
- A running backend instance (local or remote)
- `OPENAI_API_KEY` to run LLM-as-judge metrics (optional — tests skip without it)
- `promptfoo` CLI for the red team layer

### 1. Install dependencies

From the **project root**:

```bash
uv sync
```

This installs the full workspace, including the `evaluation` package and its dependencies (`deepeval`, `pytest`, `pytest-asyncio`, `langfuse`, `httpx`, `python-dotenv`).

### 2. Configure environment

Copy the example file:

```bash
cp evaluation/.env.example evaluation/.env
```

The `.env.example` ships with the **Ollama (dev) block active** by default. Uncomment
the Anthropic block for CI runs. Only one provider should be active at a time —
`OPENAI_API_KEY` takes precedence if set alongside the others.

#### 2a — Dev: local Ollama (no API key required)

Ollama is the default judge for local development, as per ADR-001.

1. Install and start Ollama: <https://ollama.com>
2. Pull a capable model: `ollama pull llama4:8b`
3. Keep the Ollama block active in `evaluation/.env` (it is the default).

`LOCAL_MODEL_API_KEY`, `LOCAL_MODEL_NAME`, and `OLLAMA_BASE_URL` are the only
required vars. All DeepEval `GEval` metrics — custom and inline — auto-route to
Ollama through DeepEval's env-var detection. No test file changes needed.

> **Note:** Smaller local models may score differently from Claude on subjective
> criteria. Tests with `threshold=1.0` require a model with strong instruction
> following (≥ 8B parameters recommended).

#### 2b — CI/production: Claude Sonnet 4.6 via Anthropic API

DeepEval ≥ 4.0.4 ships a native `AnthropicModel` class whose default model is
`claude-sonnet-4-6`. No custom wrappers or extra packages beyond `anthropic` are
needed.

In `evaluation/.env` (or as CI environment secrets):

1. Comment out the `LOCAL_MODEL_API_KEY` / `LOCAL_MODEL_NAME` / `OLLAMA_BASE_URL` lines.
2. Uncomment and set:

   ```text
   USE_ANTHROPIC_MODEL=true
   ANTHROPIC_API_KEY=<your-key>
   # ANTHROPIC_MODEL_NAME=claude-sonnet-4-6   # optional; this is already the default
   ```

All `GEval` instances (custom and inline) auto-route to Claude Sonnet when
`USE_ANTHROPIC_MODEL=true` and no `OPENAI_API_KEY` is present.

#### Environment variable reference

| Variable | Mode | Required | Default | Purpose |
| --- | --- | --- | --- | --- |
| `EVAL_API_URL` | both | No | `http://localhost:8000` | Backend URL the tests call |
| `ZGC_API_KEY` | both | No | `dev-key` | API key sent in `ZGC-API-KEY` header |
| `LOCAL_MODEL_API_KEY` | dev | Yes (dev) | — | Set to `ollama` to use Ollama |
| `LOCAL_MODEL_NAME` | dev | Yes (dev) | — | Ollama model tag, e.g. `llama4:8b` |
| `OLLAMA_BASE_URL` | dev | No | `http://localhost:11434` | Ollama endpoint |
| `USE_ANTHROPIC_MODEL` | CI | Yes (CI) | — | Set to `true` to use Claude |
| `ANTHROPIC_API_KEY` | CI | Yes (CI) | — | Anthropic API key |
| `ANTHROPIC_MODEL_NAME` | CI | No | `claude-sonnet-4-6` | Override the Claude model |
| `OPENAI_API_KEY` | — | No | — | Legacy fallback; takes priority if set |
| `LANGFUSE_PUBLIC_KEY` | both | No | — | Enables eval score logging to Langfuse |
| `LANGFUSE_SECRET_KEY` | both | No | — | Langfuse secret (pair with public key) |
| `LANGFUSE_HOST` | both | No | `https://eu.cloud.langfuse.com` | Langfuse instance URL |

### 3. Start the backend

The behaviour tests need the backend running and reachable at `EVAL_API_URL`. See the [backend README](../backend/README.md) or run:

```bash
uv run --package backend uvicorn backend.main:app --reload --port 8000
```

If the backend is not reachable, all tests are **skipped** (not failed).

### 4. (Red team only) Install promptfoo

```bash
npm install -g promptfoo
```

Set `EVAL_API_URL` and `ZGC_API_KEY` in your shell environment or in `evaluation/.env` before running.

---

## Running the tests

All `uv run` commands are executed from the **project root**.

### Run all behaviour tests

```bash
uv run --package evaluation pytest evaluation/behaviour
```

### Run a specific persona

```bash
uv run --package evaluation pytest evaluation/behaviour -m p1
uv run --package evaluation pytest evaluation/behaviour -m p2
uv run --package evaluation pytest evaluation/behaviour -m p3
uv run --package evaluation pytest evaluation/behaviour -m n1
uv run --package evaluation pytest evaluation/behaviour -m n2
uv run --package evaluation pytest evaluation/behaviour -m pattern
```

### Run Phase 2 scope only

```bash
uv run --package evaluation pytest evaluation/behaviour -m phase2
```

### Run with verbose output

```bash
uv run --package evaluation pytest evaluation/behaviour -v
```

### Run without an LLM-as-judge provider

Tests that require a judge provider (`no_pricing_disclosure`, `no_fabrication_without_context`)
skip automatically when no provider is configured. Deterministic tests
(`single_question_per_exchange`) always run regardless.

### Run the red team suite

```bash
cd evaluation/redteam
promptfoo eval
```

Results open in the promptfoo browser UI by default. To output JSON:

```bash
promptfoo eval --output results.json
```

---

## Pytest markers

| Marker | Scope |
| --- | --- |
| `p1` | CTO persona tests |
| `p2` | Founder persona tests |
| `p3` | Referred decision-maker tests |
| `n1` | Competitor persona tests |
| `n2` | Curious researcher tests |
| `pattern` | Conversation pattern tests |
| `phase2` | Phase 2 first evaluation cycle (subset of the above) |

---

## Langfuse integration

When `LANGFUSE_PUBLIC_KEY` is set, DeepEval automatically ships eval scores as traces to Langfuse. No code changes are needed — `behaviour/conftest.py` sets the required environment variables at startup.

This lets you correlate eval scores with production traces in the same Langfuse project.
