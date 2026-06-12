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

# ── Thresholds (action plan §Phase 4) ────────────────────────────────────────
THRESHOLDS: dict[str, float] = {
    "faithfulness": 0.8,
    "context_precision": 0.8,
    "context_recall": 0.7,
    "answer_relevancy": 0.75,
}

# ── RAGAS metric names (RAGAS 0.4.x) ─────────────────────────────────────────
# Import lazily to give a clean error if ragas is not installed.

def _patch_ragas_vertexai_compat() -> None:
    """RAGAS 0.4.3 imports ChatVertexAI at module load time but langchain-community
    0.4+ removed that submodule. Inject a stub so the import does not fail — we
    never use VertexAI, it only appears in RAGAS's MULTIPLE_COMPLETION_SUPPORTED list.
    """
    import sys  # noqa: PLC0415
    from types import ModuleType  # noqa: PLC0415

    if "langchain_community.chat_models.vertexai" in sys.modules:
        return
    try:
        import langchain_community.chat_models.vertexai  # noqa: PLC0415, F401
        return
    except ImportError:
        pass

    stub = ModuleType("langchain_community.chat_models.vertexai")

    class _ChatVertexAIStub:
        pass

    stub.ChatVertexAI = _ChatVertexAIStub  # type: ignore[attr-defined]
    sys.modules["langchain_community.chat_models.vertexai"] = stub
    try:
        import langchain_community.chat_models as _cm  # noqa: PLC0415
        _cm.vertexai = stub  # type: ignore[attr-defined]
    except ImportError:
        pass


def _load_ragas():  # noqa: ANN202
    _patch_ragas_vertexai_compat()
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
        from ragas.run_config import RunConfig  # noqa: PLC0415
    except ImportError as exc:
        print(f"[error] RAGAS is not installed: {exc}")
        print("        Run `uv sync --package evaluation --extra ragas` from the project root.")
        print("        Note: on Windows with Python 3.14, use Linux/WSL or CI instead.")
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
        RunConfig,
    )


# ── Langchain wrappers ────────────────────────────────────────────────────────

def _make_evaluator_llm(LangchainLLMWrapper):  # noqa: ANN001, ANN202, N803
    """Return a RAGAS-compatible LLM using Claude Haiku."""
    from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

    model = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-haiku-4-5-20251001")
    return LangchainLLMWrapper(ChatAnthropic(model=model, max_retries=6))


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


def _make_run_config(RunConfig: Any) -> Any:  # noqa: ANN001, N803
    """Build a RAGAS RunConfig that respects the Anthropic rate limit.

    Default max_workers=2 keeps concurrent judge calls well within the 50 req/min
    Haiku tier limit. Increase RAGAS_MAX_WORKERS carefully if you have a higher tier.
    """
    max_workers = int(os.environ.get("RAGAS_MAX_WORKERS", "2"))
    return RunConfig(
        max_workers=max_workers,
        max_retries=10,
        max_wait=60,
        timeout=300,
    )


# ── Langfuse integration ──────────────────────────────────────────────────────

_DATASET_NAME = "rag_eval"


def _init_langfuse() -> Any | None:
    """Return a configured Langfuse client if env vars are present, else None."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not public_key or not secret_key:
        return None
    try:
        from langfuse import Langfuse  # noqa: PLC0415

        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=os.environ.get("LANGFUSE_HOST", "https://eu.cloud.langfuse.com"),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  [warning] Langfuse init failed: {exc}")
        return None


def _ensure_dataset_items(lf: Any, items: list) -> dict[str, str]:
    """Create (or reuse) the rag_eval dataset and upsert one item per eval question.

    Returns mapping of item.id → Langfuse dataset_item.id.
    """
    try:
        lf.create_dataset(
            name=_DATASET_NAME,
            description="RAGAS RAG pipeline evaluation — one item per eval question",
        )
    except Exception:  # noqa: BLE001
        pass  # dataset already exists

    item_id_map: dict[str, str] = {}
    for item in items:
        try:
            di = lf.create_dataset_item(
                dataset_name=_DATASET_NAME,
                input={"question": item.question},
                expected_output={"ground_truth": item.ground_truth},
                metadata={
                    "item_id": item.id,
                    "has_relevant_chunk": item.has_relevant_chunk,
                    "test_type": item.test_type,
                    "relevant_document": item.relevant_document,
                    "relevant_category": item.relevant_category,
                },
            )
            item_id_map[item.id] = di.id
        except Exception as exc:  # noqa: BLE001
            print(f"  [warning] Could not create dataset item {item.id}: {exc}")
    return item_id_map


def _create_item_trace(lf: Any, item: Any, answer: str) -> str:
    """Create a Langfuse trace for one eval item and return its trace_id."""
    try:
        obs = lf.start_observation(
            name="rag-eval-item",
            input={"question": item.question},
            output={"answer": answer},
            metadata={
                "item_id": item.id,
                "test_type": item.test_type,
                "has_relevant_chunk": item.has_relevant_chunk,
            },
        )
        trace_id = obs.trace_id
        obs.end()
        return trace_id
    except Exception as exc:  # noqa: BLE001
        print(f"  [warning] Langfuse trace creation failed for {item.id}: {exc}")
        return ""


def _upload_item_scores(
    lf: Any,
    run_name: str,
    item_id_map: dict[str, str],
    trace_ids: dict[str, str],
    with_context_ordered: list,
    df: Any,
    no_context_ordered: list,
    df_nc: Any,
    avg_scores: dict[str, float],
) -> None:
    """Upload per-item RAGAS scores to Langfuse traces and link them to the dataset.

    Creates one DatasetRunItem per eval question so the full experiment is visible
    in the Langfuse UI under Datasets → rag_eval → Experiments.
    """
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError:
        return

    # Per-item scores for context items (faithfulness, context_precision,
    # context_recall, answer_relevancy)
    if df is not None:
        for idx, item in enumerate(with_context_ordered):
            trace_id = trace_ids.get(item.id, "")
            dataset_item_id = item_id_map.get(item.id, "")
            if not trace_id:
                continue
            try:
                row = df.iloc[idx]
                for metric in ("faithfulness", "context_precision", "context_recall", "answer_relevancy"):
                    if metric in df.columns:
                        val = row[metric]
                        if val is not None and not (isinstance(val, float) and pd.isna(val)):
                            lf.create_score(trace_id=trace_id, name=metric, value=float(val))
                if dataset_item_id:
                    lf.api.dataset_run_items.create(
                        run_name=run_name,
                        dataset_item_id=dataset_item_id,
                        trace_id=trace_id,
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"  [warning] Langfuse upload failed for {item.id}: {exc}")

    # Per-item scores for no-context items (faithfulness + answer_relevancy only)
    if df_nc is not None:
        for idx, item in enumerate(no_context_ordered):
            trace_id = trace_ids.get(item.id, "")
            dataset_item_id = item_id_map.get(item.id, "")
            if not trace_id:
                continue
            try:
                row = df_nc.iloc[idx]
                for metric in ("faithfulness", "answer_relevancy"):
                    if metric in df_nc.columns:
                        val = row[metric]
                        if val is not None and not (isinstance(val, float) and pd.isna(val)):
                            lf.create_score(trace_id=trace_id, name=metric, value=float(val))
                if dataset_item_id:
                    lf.api.dataset_run_items.create(
                        run_name=run_name,
                        dataset_item_id=dataset_item_id,
                        trace_id=trace_id,
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"  [warning] Langfuse upload failed for {item.id}: {exc}")

    # Flush all buffered events and print the experiment link.
    # The dataset run is created implicitly by the first dataset_run_items.create() call.
    try:
        lf.flush()
        print(f"  → Langfuse experiment logged: {_DATASET_NAME} / {run_name}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [warning] Langfuse flush failed: {exc}")


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


def _write_local_report(
    scores: dict[str, float],
    run_name: str,
    all_pass: bool,
    embedding_mode: str,
) -> None:
    """Write a JSON report to evaluation/.evaluation-reports/<run_name>.json."""
    import datetime  # noqa: PLC0415
    import json      # noqa: PLC0415

    report_dir = Path(__file__).parent.parent / ".evaluation-reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "run_name": run_name,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "embedding_mode": embedding_mode,
        "all_pass": all_pass,
        "thresholds": THRESHOLDS,
        "scores": {
            metric: {
                "value": scores.get(metric),
                "threshold": THRESHOLDS[metric],
                "pass": (
                    scores[metric] >= THRESHOLDS[metric]
                    if metric in scores and scores[metric] is not None
                    else None
                ),
            }
            for metric in THRESHOLDS
        },
    }

    report_path = report_dir / f"{run_name}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"  → Local report written: {report_path}")


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
        RunConfig,
    ) = _load_ragas()

    # ── Load dataset ──────────────────────────────────────────────────────────
    items = load_dataset(dataset_path)
    print(f"\n[ragas] Loaded {len(items)} evaluation items (mode: {embedding_mode})")

    # ── Init Langfuse (optional) ──────────────────────────────────────────────
    lf = _init_langfuse()
    item_id_map: dict[str, str] = {}
    if lf:
        print("[ragas] Langfuse configured — creating dataset items…")
        item_id_map = _ensure_dataset_items(lf, items)
        print(f"  → {len(item_id_map)} dataset items ready in '{_DATASET_NAME}'")

    # ── Build RAGAS samples ───────────────────────────────────────────────────
    samples_with_context: list[SingleTurnSample] = []
    samples_no_context: list[SingleTurnSample] = []

    # Track (item, trace_id) pairs in the same order as the sample lists
    # so per-sample DataFrame rows can be mapped back after RAGAS evaluation.
    with_context_ordered: list = []
    no_context_ordered: list = []
    trace_ids: dict[str, str] = {}

    for i, item in enumerate(items, start=1):
        print(f"  [{i:02d}/{len(items)}] {item.id} — retrieving & generating…", end="\r")

        if item.has_relevant_chunk:
            contexts = retrieve_contexts(item.question, mode=embedding_mode)
        else:
            contexts = []

        answer = generate_answer(item.question, contexts)

        # Create per-item Langfuse trace (after answer is generated)
        if lf:
            trace_id = _create_item_trace(lf, item, answer)
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

    # ── Configure RAGAS judge ─────────────────────────────────────────────────
    evaluator_llm = _make_evaluator_llm(LangchainLLMWrapper)
    evaluator_embeddings = _make_evaluator_embeddings(LangchainEmbeddingsWrapper, embedding_mode)
    run_config = _make_run_config(RunConfig)

    aggregated: dict[str, list[float]] = {m: [] for m in THRESHOLDS}
    df = None
    df_nc = None

    # ── Evaluate context items (all 4 metrics) ────────────────────────────────
    if samples_with_context:
        print("[ragas] Running faithfulness, context_precision, context_recall, answer_relevancy…")
        ds = EvaluationDataset(samples=samples_with_context)
        result = evaluate(
            dataset=ds,
            metrics=[faithfulness, context_precision, context_recall, answer_relevancy],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
            run_config=run_config,
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
            run_config=run_config,
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

    # ── Log per-item scores + link to Langfuse dataset ────────────────────────
    import datetime  # noqa: PLC0415

    run_name = f"ragas-{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d-%H%M%S')}"
    if lf:
        _upload_item_scores(
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

    _write_local_report(avg_scores, run_name, all_pass, embedding_mode)

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
