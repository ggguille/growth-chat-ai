"""Load and validate the RAG evaluation dataset.

The canonical dataset lives at ``evaluation/datasets/rag_eval_dataset.json``.
Each item has the fields documented in :class:`RagEvalItem`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RagEvalItem:
    """One row from ``rag_eval_dataset.json``."""

    id: str
    question: str
    ground_truth: str
    relevant_document: str | None
    relevant_category: str | None
    has_relevant_chunk: bool
    test_type: str  # known_relevant | paraphrase | no_relevant_chunk
    expected_behaviour: str | None  # "acknowledge_limit" for no_relevant_chunk items


def load_dataset(path: str | Path | None = None) -> list[RagEvalItem]:
    """Return all items from the RAG evaluation dataset.

    Args:
        path: Path to ``rag_eval_dataset.json``.  Defaults to
              ``evaluation/datasets/rag_eval_dataset.json`` relative to the
              project root (two directories above this file).
    """
    if path is None:
        # Resolve relative to project root (evaluation/rag/ → evaluation/ → root/)
        path = Path(__file__).parent.parent.parent / "evaluation" / "datasets" / "rag_eval_dataset.json"

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"RAG eval dataset not found: {path}")

    raw: list[dict] = json.loads(path.read_text(encoding="utf-8"))

    items: list[RagEvalItem] = []
    for row in raw:
        items.append(
            RagEvalItem(
                id=row["id"],
                question=row["question"],
                ground_truth=row["ground_truth"],
                relevant_document=row.get("relevant_document"),
                relevant_category=row.get("relevant_category"),
                has_relevant_chunk=row["has_relevant_chunk"],
                test_type=row["test_type"],
                expected_behaviour=row.get("expected_behaviour"),
            )
        )
    return items
