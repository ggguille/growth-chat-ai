"""RAGAS RAG evaluation pipeline — CLI entry point.

Loads the RAG evaluation dataset, retrieves contexts from pgvector, generates
grounded answers with Claude Haiku, runs RAGAS metrics, and reports results.
Logs per-item traces and scores to Langfuse as a named Dataset experiment when
LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are configured.

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
import datetime
import os
import sys
from pathlib import Path
from typing import Any

# Ensure Unicode output works on Windows (CP1252 terminal can't handle →, ✓, etc.)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Load .env automatically when running locally
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from evaluation.rag.evaluators import make_evaluator_embeddings, make_evaluator_llm, make_run_config
from evaluation.rag.langfuse_tracker import (
    create_item_trace,
    ensure_dataset_items,
    init_langfuse,
    upload_item_scores,
)
from evaluation.rag.ragas_compat import load_ragas
from evaluation.rag.reporting import print_results, write_local_report

# ── Thresholds (calibrated 2026-06-12 against real production KB) ─────────────
# context_precision: 0.663 is the structural ceiling (7 broad-service chunks, similar
#   embedding distances) — 0.65 gives a 2% buffer for run variance.
# answer_relevancy: ~0.485 prod baseline. Yes/no questions retrieve better than
#   informational ones (context_recall 0.795 vs 0.650 in A/B test), so eval dataset
#   keeps yes/no question style. RAGAS generates questions from answers then measures
#   cosine similarity to original — yes/no structure is a known metric ceiling (~0.45).
THRESHOLDS: dict[str, float] = {
    "faithfulness": 0.80,
    "context_precision": 0.65,
    "context_recall": 0.70,
    "answer_relevancy": 0.45,
}


# ── Pipeline helpers ──────────────────────────────────────────────────────────

def _build_samples(
    items: list,
    embedding_mode: str,
    lf: Any | None,
    item_id_map: dict[str, str],
    SingleTurnSample: Any,
) -> tuple[list, list, list, list, dict[str, str]]:
    """Retrieve contexts, generate answers, and build two RAGAS sample lists.

    Returns:
        (samples_with_context, samples_no_context,
         with_context_ordered, no_context_ordered, trace_ids)
    """
    from evaluation.rag.generator import generate_answer  # noqa: PLC0415
    from evaluation.rag.retriever import retrieve_contexts  # noqa: PLC0415

    samples_with_context: list = []
    samples_no_context: list = []
    with_context_ordered: list = []
    no_context_ordered: list = []
    trace_ids: dict[str, str] = {}

    for i, item in enumerate(items, start=1):
        print(f"  [{i:02d}/{len(items)}] {item.id} — retrieving & generating…", end="\r")

        contexts = retrieve_contexts(item.question, mode=embedding_mode) if item.has_relevant_chunk else []
        answer = generate_answer(item.question, contexts)

        if lf:
            trace_id = create_item_trace(lf, item, answer)
            if trace_id:
                trace_ids[item.id] = trace_id

        sample = SingleTurnSample(
            user_input=item.question,
            response=answer,
            retrieved_contexts=contexts,
            reference=item.ground_truth,
        )

        if item.has_relevant_chunk:
            samples_with_context.append(sample)
            with_context_ordered.append(item)
        else:
            samples_no_context.append(sample)
            no_context_ordered.append(item)

    print(f"  Built {len(samples_with_context)} context samples + {len(samples_no_context)} no-context samples.")
    return samples_with_context, samples_no_context, with_context_ordered, no_context_ordered, trace_ids


def _run_ragas_batch(
    samples: list,
    metrics: list,
    metric_names: tuple[str, ...],
    label: str,
    evaluate: Any,
    EvaluationDataset: Any,  # noqa: N803
    evaluator_llm: Any,
    evaluator_embeddings: Any,
    run_config: Any,
    aggregated: dict[str, list[float]],
) -> Any | None:
    """Evaluate a sample batch with RAGAS, extend aggregated scores, return DataFrame."""
    if not samples:
        return None
    print(f"[ragas] Running {label}…")
    ds = EvaluationDataset(samples=samples)
    result = evaluate(
        dataset=ds,
        metrics=metrics,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
        run_config=run_config,
    )
    df = result.to_pandas()
    for metric in metric_names:
        if metric in df.columns:
            aggregated[metric].extend(df[metric].dropna().tolist())
    return df


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main(dataset_path: str | None, embedding_mode: str) -> int:
    """Run the full RAGAS evaluation pipeline.

    Returns:
        0 if all thresholds pass, 1 otherwise.
    """
    from evaluation.rag.loader import load_dataset  # noqa: PLC0415

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
        RunConfig,
    ) = load_ragas()

    # ── Load dataset ──────────────────────────────────────────────────────────
    items = load_dataset(dataset_path)
    print(f"\n[ragas] Loaded {len(items)} evaluation items (mode: {embedding_mode})")

    # ── Init Langfuse (optional) ──────────────────────────────────────────────
    lf = init_langfuse()
    item_id_map: dict[str, str] = {}
    if lf:
        print("[ragas] Langfuse configured — creating dataset items…")
        item_id_map = ensure_dataset_items(lf, items)
        print(f"  → {len(item_id_map)} dataset items ready in 'rag_eval'")

    # ── Build RAGAS samples ───────────────────────────────────────────────────
    samples_with_context, samples_no_context, with_context_ordered, no_context_ordered, trace_ids = (
        _build_samples(items, embedding_mode, lf, item_id_map, SingleTurnSample)
    )

    # ── Configure RAGAS judge ─────────────────────────────────────────────────
    evaluator_llm = make_evaluator_llm(LangchainLLMWrapper)
    evaluator_embeddings = make_evaluator_embeddings(LangchainEmbeddingsWrapper, embedding_mode)
    run_config = make_run_config(RunConfig)
    aggregated: dict[str, list[float]] = {m: [] for m in THRESHOLDS}

    # ── Evaluate both sample batches ──────────────────────────────────────────
    batch_kwargs = dict(
        evaluate=evaluate,
        EvaluationDataset=EvaluationDataset,
        evaluator_llm=evaluator_llm,
        evaluator_embeddings=evaluator_embeddings,
        run_config=run_config,
        aggregated=aggregated,
    )
    df = _run_ragas_batch(
        samples_with_context,
        [faithfulness, context_precision, context_recall, answer_relevancy],
        ("faithfulness", "context_precision", "context_recall", "answer_relevancy"),
        "faithfulness, context_precision, context_recall, answer_relevancy",
        **batch_kwargs,
    )
    df_nc = _run_ragas_batch(
        samples_no_context,
        [faithfulness, answer_relevancy],
        ("faithfulness", "answer_relevancy"),
        "faithfulness, answer_relevancy on no-context items",
        **batch_kwargs,
    )

    # ── Compute averages ──────────────────────────────────────────────────────
    avg_scores: dict[str, float] = {
        metric: sum(values) / len(values)
        for metric, values in aggregated.items()
        if values
    }

    # ── Report ────────────────────────────────────────────────────────────────
    print("[ragas] Results:")
    all_pass = print_results(avg_scores, THRESHOLDS)

    run_name = f"ragas-{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M%S')}"

    if lf:
        upload_item_scores(
            lf=lf,
            run_name=run_name,
            item_id_map=item_id_map,
            trace_ids=trace_ids,
            with_context_ordered=with_context_ordered,
            df=df,
            no_context_ordered=no_context_ordered,
            df_nc=df_nc,
            avg_scores=avg_scores,
        )
    else:
        print("  [info] Langfuse not configured — skipping dataset experiment logging.")

    write_local_report(avg_scores, run_name, all_pass, embedding_mode, THRESHOLDS)

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
