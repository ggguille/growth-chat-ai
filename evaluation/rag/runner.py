"""RAGAS RAG evaluation pipeline — CLI entry point.

Loads the RAG evaluation dataset, retrieves contexts from pgvector, generates
grounded answers with Claude Haiku, runs RAGAS metrics, and reports results.
Optionally logs scores to Langfuse as a named Dataset experiment.

Usage (from project root):
    uv run --package evaluation python -m evaluation.rag.runner
    uv run --package evaluation python -m evaluation.rag.runner --embedding-mode prod
    uv run --package evaluation python -m evaluation.rag.runner \\
        --dataset evaluation/datasets/rag_eval_dataset.json

Exit codes:
    0  All metric averages meet their thresholds.
    1  One or more metrics fall below threshold (or a runtime error occurred).

Environment variables: see retriever.py, generator.py, and .env.example.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Load .env automatically when running locally
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Thresholds (action plan §Phase 4) ────────────────────────────────────────
THRESHOLDS: dict[str, float] = {
    "faithfulness": 0.8,
    "context_precision": 0.8,
    "context_recall": 0.7,
    "answer_relevancy": 0.75,
}

# ── RAGAS metric names (RAGAS 0.4.x) ─────────────────────────────────────────
# Import lazily to give a clean error if ragas is not installed.
def _load_ragas():  # noqa: ANN202
    try:
        from ragas import evaluate  # noqa: PLC0415
        from ragas.dataset_schema import EvaluationDataset, SingleTurnSample  # noqa: PLC0415
        from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: PLC0415
        from ragas.llms import LangchainLLMWrapper  # noqa: PLC0415
        from ragas.metrics import (  # noqa: PLC0415
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError as exc:
        print(f"[error] RAGAS is not installed: {exc}")
        print("        Run `uv sync` from the project root to install it.")
        sys.exit(1)

    return (
        evaluate,
        EvaluationDataset,
        SingleTurnSample,
        LangchainEmbeddingsWrapper,
        LangchainLLMWrapper,
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )


# ── Langchain wrappers ────────────────────────────────────────────────────────

def _make_evaluator_llm(LangchainLLMWrapper):  # noqa: ANN001, ANN202, N803
    """Return a RAGAS-compatible LLM using Claude Haiku."""
    from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

    model = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-haiku-4-5-20251001")
    return LangchainLLMWrapper(ChatAnthropic(model=model))


def _make_evaluator_embeddings(LangchainEmbeddingsWrapper, mode: str):  # noqa: ANN001, ANN202, N803
    """Return RAGAS-compatible embeddings matching the ingestion embedder."""
    from langchain_core.embeddings import Embeddings  # noqa: PLC0415

    if mode == "prod":
        from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

        return LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    # Dev: sentence-transformers, same model as ingestion pipeline
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    class _STEmbeddings(Embeddings):
        def __init__(self) -> None:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self._model.encode(texts, convert_to_numpy=True).tolist()

        def embed_query(self, text: str) -> list[float]:
            return self._model.encode(text, convert_to_numpy=True).tolist()

    return LangchainEmbeddingsWrapper(_STEmbeddings())


# ── Langfuse logging ──────────────────────────────────────────────────────────

def _log_to_langfuse(scores: dict[str, float], run_name: str) -> None:
    """Log RAGAS metric scores to a Langfuse Dataset experiment.

    Creates (or reuses) a dataset named ``rag_eval`` and appends a run with
    the given *run_name*.  Scores are stored as ``metadata`` on the DatasetRun.
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not public_key or not secret_key:
        return  # Langfuse not configured — skip silently

    try:
        from langfuse import Langfuse  # noqa: PLC0415

        lf = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=os.environ.get("LANGFUSE_HOST", "https://eu.cloud.langfuse.com"),
        )

        # Upsert the dataset
        try:
            lf.create_dataset(name="rag_eval", description="RAGAS RAG pipeline evaluation")
        except Exception:  # noqa: BLE001
            pass  # Dataset already exists

        # Create a run (experiment) with the scores as metadata
        lf.create_dataset_run(
            dataset_name="rag_eval",
            run_name=run_name,
            run_description="Automated RAGAS run from evaluation/rag/runner.py",
            metadata=scores,
        )
        lf.flush()
        print(f"  → Langfuse experiment logged: rag_eval / {run_name}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [warning] Langfuse logging failed: {exc}")


# ── Score reporting ───────────────────────────────────────────────────────────

def _print_results(scores: dict[str, float]) -> bool:
    """Print a results table.  Returns True if all thresholds pass."""
    print()
    print(f"  {'Metric':<24} {'Score':>6}  {'Threshold':>9}  {'Pass':>4}")
    print("  " + "-" * 50)
    all_pass = True
    for metric, threshold in THRESHOLDS.items():
        score = scores.get(metric)
        if score is None:
            status = "N/A "
            row_pass = True  # metric not measured for this subset
        else:
            row_pass = score >= threshold
            status = "✓" if row_pass else "✗"
            if not row_pass:
                all_pass = False
        score_str = f"{score:.4f}" if score is not None else "  N/A"
        print(f"  {metric:<24} {score_str:>6}  {threshold:>9.2f}  {status:>4}")
    print()
    return all_pass


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main(dataset_path: str | None, embedding_mode: str) -> int:
    """Run the full RAGAS evaluation pipeline.

    Returns:
        0 if all thresholds pass, 1 otherwise.
    """
    from evaluation.rag.generator import generate_answer  # noqa: PLC0415
    from evaluation.rag.loader import load_dataset  # noqa: PLC0415
    from evaluation.rag.retriever import retrieve_contexts  # noqa: PLC0415

    (
        evaluate,
        EvaluationDataset,
        SingleTurnSample,
        LangchainEmbeddingsWrapper,
        LangchainLLMWrapper,
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ) = _load_ragas()

    # ── Load dataset ──────────────────────────────────────────────────────────
    items = load_dataset(dataset_path)
    print(f"\n[ragas] Loaded {len(items)} evaluation items (mode: {embedding_mode})")

    # ── Build RAGAS samples ───────────────────────────────────────────────────
    samples_with_context: list[SingleTurnSample] = []
    samples_no_context: list[SingleTurnSample] = []

    for i, item in enumerate(items, start=1):
        print(f"  [{i:02d}/{len(items)}] {item.id} — retrieving & generating…", end="\r")

        if item.has_relevant_chunk:
            contexts = retrieve_contexts(item.question, mode=embedding_mode)
        else:
            contexts = []

        answer = generate_answer(item.question, contexts)

        sample = SingleTurnSample(
            user_input=item.question,
            response=answer,
            retrieved_contexts=contexts,
            reference=item.ground_truth,
        )

        if item.has_relevant_chunk:
            samples_with_context.append(sample)
        else:
            samples_no_context.append(sample)

    print(f"  Built {len(samples_with_context)} context samples + {len(samples_no_context)} no-context samples.")

    # ── Configure RAGAS judge ─────────────────────────────────────────────────
    evaluator_llm = _make_evaluator_llm(LangchainLLMWrapper)
    evaluator_embeddings = _make_evaluator_embeddings(LangchainEmbeddingsWrapper, embedding_mode)

    aggregated: dict[str, list[float]] = {m: [] for m in THRESHOLDS}

    # ── Evaluate context items (all 4 metrics) ────────────────────────────────
    if samples_with_context:
        print("[ragas] Running faithfulness, context_precision, context_recall, answer_relevancy…")
        ds = EvaluationDataset(samples=samples_with_context)
        result = evaluate(
            dataset=ds,
            metrics=[faithfulness, context_precision, context_recall, answer_relevancy],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        )
        df = result.to_pandas()
        for metric in ("faithfulness", "context_precision", "context_recall", "answer_relevancy"):
            if metric in df.columns:
                aggregated[metric].extend(df[metric].dropna().tolist())

    # ── Evaluate no-context items (faithfulness + answer_relevancy only) ──────
    if samples_no_context:
        print("[ragas] Running faithfulness, answer_relevancy on no-context items…")
        ds_nc = EvaluationDataset(samples=samples_no_context)
        result_nc = evaluate(
            dataset=ds_nc,
            metrics=[faithfulness, answer_relevancy],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        )
        df_nc = result_nc.to_pandas()
        for metric in ("faithfulness", "answer_relevancy"):
            if metric in df_nc.columns:
                aggregated[metric].extend(df_nc[metric].dropna().tolist())

    # ── Compute averages ──────────────────────────────────────────────────────
    avg_scores: dict[str, float] = {}
    for metric, values in aggregated.items():
        if values:
            avg_scores[metric] = sum(values) / len(values)

    # ── Report ────────────────────────────────────────────────────────────────
    print("[ragas] Results:")
    all_pass = _print_results(avg_scores)

    # ── Log to Langfuse ───────────────────────────────────────────────────────
    import datetime  # noqa: PLC0415

    run_name = f"ragas-{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M%S')}"
    _log_to_langfuse(avg_scores, run_name)

    if all_pass:
        print("[ragas] All thresholds passed. ✓")
    else:
        print("[ragas] One or more thresholds failed. ✗")

    return 0 if all_pass else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the RAGAS RAG evaluation pipeline against the KB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run --package evaluation python -m evaluation.rag.runner
  uv run --package evaluation python -m evaluation.rag.runner --embedding-mode prod
  uv run --package evaluation python -m evaluation.rag.runner \\
      --dataset evaluation/datasets/rag_eval_dataset.json
""",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Path to rag_eval_dataset.json (default: evaluation/datasets/rag_eval_dataset.json)",
    )
    parser.add_argument(
        "--embedding-mode",
        choices=["dev", "prod"],
        default=os.environ.get("RAGAS_EMBEDDING_MODE", "dev"),
        help="Embedding mode: dev (sentence-transformers 384-dim) or prod (OpenAI 1536-dim). "
             "Also reads RAGAS_EMBEDDING_MODE env var.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(main(args.dataset, args.embedding_mode))
