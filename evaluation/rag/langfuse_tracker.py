"""Langfuse observability integration for the RAGAS evaluation pipeline."""
from __future__ import annotations

import os
from typing import Any

_DATASET_NAME = "rag_eval"


def init_langfuse() -> Any | None:
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


def ensure_dataset_items(lf: Any, items: list) -> dict[str, str]:
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


def create_item_trace(lf: Any, item: Any, answer: str) -> str:
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


def _upload_scores_for_batch(
    lf: Any,
    items_ordered: list,
    trace_ids: dict[str, str],
    item_id_map: dict[str, str],
    df: Any,
    run_name: str,
    metric_names: tuple[str, ...],
) -> None:
    import pandas as pd  # noqa: PLC0415

    for idx, item in enumerate(items_ordered):
        trace_id = trace_ids.get(item.id, "")
        dataset_item_id = item_id_map.get(item.id, "")
        if not trace_id:
            continue
        try:
            row = df.iloc[idx]
            for metric in metric_names:
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


def upload_item_scores(
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
        import pandas  # noqa: PLC0415, F401
    except ImportError:
        return

    _CONTEXT_METRICS = ("faithfulness", "context_precision", "context_recall", "answer_relevancy")
    _NO_CONTEXT_METRICS = ("faithfulness", "answer_relevancy")

    if df is not None:
        _upload_scores_for_batch(lf, with_context_ordered, trace_ids, item_id_map, df, run_name, _CONTEXT_METRICS)

    if df_nc is not None:
        _upload_scores_for_batch(lf, no_context_ordered, trace_ids, item_id_map, df_nc, run_name, _NO_CONTEXT_METRICS)

    try:
        lf.flush()
        print(f"  → Langfuse experiment logged: {_DATASET_NAME} / {run_name}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [warning] Langfuse flush failed: {exc}")
