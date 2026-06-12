"""RAG threshold calibration script — Phase 4 TRD method.

Runs a representative set of queries against the knowledge base and prints
score distributions so you can identify the natural gap between relevant and
irrelevant retrievals. Use this to set RAG_RELEVANCE_THRESHOLD empirically.

Method (TRD §3.3, Phase 4 Step 1):
1. Run queries with known relevant chunks — scores should cluster high.
2. Run queries with no relevant chunk — scores should cluster low.
3. Identify the natural gap between the two clusters.
4. Set RAG_RELEVANCE_THRESHOLD at the midpoint of the gap.
5. Document the chosen value in the TRD and in backend/.env.

Usage (from project root):
    uv run --package evaluation python -m evaluation.calibrate_rag
    uv run --package evaluation python -m evaluation.calibrate_rag --mode prod
    uv run --package evaluation python -m evaluation.calibrate_rag --top-k 5

Environment variables:
    CHECKPOINT_DB_URL (or RAGAS_DB_URL)  psycopg3 connection string
    RAGAS_EMBEDDING_MODE                 dev | prod (default: dev)
    OPENAI_API_KEY                       required only when mode=prod
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Windows CP1252 terminals can't encode box-drawing / arrow / tick characters.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ── Query sets ────────────────────────────────────────────────────────────────

# Relevant queries — each maps to a known KB document category.
# Scores for these should cluster above the threshold.
RELEVANT_QUERIES: list[tuple[str, str]] = [
    ("services",   "Do you build RAG pipelines and LLM applications?"),
    ("services",   "What AI agent frameworks and orchestration tools do you use?"),
    ("team",       "How many engineers does Zartis have and where are they based?"),
    ("team",       "What European timezone coverage does your team provide?"),
    ("case-study", "Do you have experience building AI systems for compliance software?"),
    ("case-study", "Have you worked on AI security or data classification projects?"),
    ("case-study", "Do you have energy sector or EV charging case studies?"),
    ("engagement", "How does the team extension engagement model work?"),
    ("engagement", "Can you own a full end-to-end software delivery?"),
    ("faq",        "How quickly can engineers start on a new engagement?"),
    ("faq",        "What does a typical AI feature project cost and how long does it take?"),
    ("faq",        "Do you do academic machine learning research?"),
    # Paraphrases — robustness check
    ("services",   "We need help building an agentic system with LangGraph."),
    ("team",       "Are your engineers in CET timezone for daily standups?"),
    ("case-study", "Can you give an example of a large team scale-up you delivered?"),
]

# Irrelevant queries — no relevant chunk should exist in the KB.
# Scores for these should cluster below the threshold.
IRRELEVANT_QUERIES: list[tuple[str, str]] = [
    ("off-topic",  "What is the capital of France?"),
    ("off-topic",  "How do I implement a binary search tree in Python?"),
    ("off-topic",  "What is the current inflation rate in the Eurozone?"),
    ("off-topic",  "Can you write me a SQL query to find duplicate rows?"),
    ("off-topic",  "What are the best JavaScript frameworks for mobile development?"),
    ("off-topic",  "How does TCP/IP handshake work?"),
    ("internal",   "What is Zartis's annual revenue for 2024?"),
    ("internal",   "How many employees left the company last year?"),
    ("internal",   "What internal project management tools does your team use?"),
    ("internal",   "What does your standard NDA look like?"),
]


# ── Retrieval ─────────────────────────────────────────────────────────────────

def _get_top_scores(question: str, mode: str, top_k: int) -> list[float]:
    """Return the top-K similarity scores for *question* against the KB."""
    db_url = os.environ.get("RAGAS_DB_URL") or os.environ.get("CHECKPOINT_DB_URL")
    if not db_url:
        print("[error] CHECKPOINT_DB_URL (or RAGAS_DB_URL) must be set.")
        sys.exit(1)

    import psycopg  # noqa: PLC0415

    from evaluation.rag.retriever import embed_question  # noqa: PLC0415

    embedding = embed_question(question, mode)
    vector_literal = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
    table = "knowledge_chunks" if mode == "prod" else "knowledge_chunks_dev"
    conn_str = db_url.replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT (1 - (embedding <=> %s::vector))::float AS score
                FROM {table}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_literal, vector_literal, top_k),
            )
            rows = cur.fetchall()

    return [float(row[0]) for row in rows]


# ── Reporting ─────────────────────────────────────────────────────────────────

def _bar(value: float, width: int = 30) -> str:
    filled = int(round(value * width))
    return "█" * filled + "░" * (width - filled)


def _print_query_row(label: str, category: str, question: str, scores: list[float], threshold: float) -> None:
    top = scores[0] if scores else 0.0
    indicator = "✓" if top >= threshold else "✗"
    short_q = question[:55] + "…" if len(question) > 56 else question
    print(f"  {indicator} [{category:<10}] {short_q:<57} top={top:.3f}  {_bar(top)}")


def _suggest_threshold(
    relevant_scores: list[float],
    irrelevant_scores: list[float],
) -> float | None:
    """Return the midpoint of the natural gap between the two score distributions."""
    if not relevant_scores or not irrelevant_scores:
        return None
    min_relevant = min(relevant_scores)
    max_irrelevant = max(irrelevant_scores)
    if min_relevant <= max_irrelevant:
        # Distributions overlap — cannot auto-suggest; manual inspection needed
        return None
    return round((min_relevant + max_irrelevant) / 2, 3)


# ── Main ──────────────────────────────────────────────────────────────────────

def main(mode: str, top_k: int, current_threshold: float) -> None:
    print(f"\n[calibrate] Mode: {mode}  |  top_k: {top_k}  |  current threshold: {current_threshold}")
    table = "knowledge_chunks" if mode == "prod" else "knowledge_chunks_dev"
    print(f"[calibrate] Table: {table}\n")

    relevant_top1: list[float] = []
    irrelevant_top1: list[float] = []

    # ── Relevant queries ──────────────────────────────────────────────────────
    print(f"  {'Status'} {'Category':<12} {'Question':<58} {'Top score':<10}  {'Bar (0→1)'}")
    print("  " + "─" * 100)
    print("  RELEVANT queries (expect scores ABOVE threshold):")
    for category, question in RELEVANT_QUERIES:
        scores = _get_top_scores(question, mode, top_k)
        _print_query_row("", category, question, scores, current_threshold)
        if scores:
            relevant_top1.append(scores[0])

    # ── Irrelevant queries ────────────────────────────────────────────────────
    print()
    print("  IRRELEVANT queries (expect scores BELOW threshold):")
    for category, question in IRRELEVANT_QUERIES:
        scores = _get_top_scores(question, mode, top_k)
        _print_query_row("", category, question, scores, current_threshold)
        if scores:
            irrelevant_top1.append(scores[0])

    # ── Distribution summary ──────────────────────────────────────────────────
    print()
    print("  Distribution summary (top-1 similarity scores):")
    print(f"    Relevant  queries:   min={min(relevant_top1):.3f}  max={max(relevant_top1):.3f}"
          f"  mean={sum(relevant_top1)/len(relevant_top1):.3f}")
    print(f"    Irrelevant queries:  min={min(irrelevant_top1):.3f}  max={max(irrelevant_top1):.3f}"
          f"  mean={sum(irrelevant_top1)/len(irrelevant_top1):.3f}")

    # ── Threshold suggestion ──────────────────────────────────────────────────
    suggested = _suggest_threshold(relevant_top1, irrelevant_top1)
    print()
    if suggested is not None:
        print(f"  Suggested RAG_RELEVANCE_THRESHOLD: {suggested}")
        print(f"  (midpoint between min relevant {min(relevant_top1):.3f} and max irrelevant {max(irrelevant_top1):.3f})")
        print()
        print("  Next steps:")
        print(f"    1. Set RAG_RELEVANCE_THRESHOLD={suggested} in backend/.env")
        print(f"    2. Set RAG_PROACTIVE_THRESHOLD={round(suggested + 0.10, 3)} (or leave unset for the +0.10 default)")
        print("    3. Document the value in documentation/docs/technical-requirements/trd-component-specifications.md")
        print("    4. Run the RAGAS evaluation: uv run --package evaluation python -m evaluation.rag.runner")
    else:
        print("  ⚠ Score distributions overlap — cannot auto-suggest a threshold.")
        print("  Inspect the table above manually and choose a value that minimises")
        print("  false positives (irrelevant chunks retrieved) while retaining recall.")

    print()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate RAG_RELEVANCE_THRESHOLD by inspecting score distributions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run --package evaluation python evaluation/calibrate_rag.py
  uv run --package evaluation python evaluation/calibrate_rag.py --mode prod
  uv run --package evaluation python evaluation/calibrate_rag.py --top-k 5 --threshold 0.65
""",
    )
    parser.add_argument(
        "--mode",
        choices=["dev", "prod"],
        default=os.environ.get("RAGAS_EMBEDDING_MODE", "dev"),
        help="Embedding mode: dev (sentence-transformers 384-dim) or prod (OpenAI 1536-dim).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=int(os.environ.get("RAGAS_TOP_K", "3")),
        help="Number of chunks to retrieve per query (default: 3).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.environ.get("RAG_RELEVANCE_THRESHOLD", "0.0")),
        help="Current threshold to show on the pass/fail indicator (default: RAG_RELEVANCE_THRESHOLD env var or 0.0).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(args.mode, args.top_k, args.threshold)
