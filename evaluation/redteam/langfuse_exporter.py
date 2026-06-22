"""Export promptfoo red team results to Langfuse as a Dataset experiment.

Usage (CLI or CI step):
    python evaluation/redteam/langfuse_exporter.py \
        --results evaluation/redteam/results-baseline.json \
        --run-name ci-<run_id>-baseline

Mirrors the pattern used by evaluation/rag/langfuse_tracker.py.
Dataset: redteam_eval   Experiments visible at: Datasets → redteam_eval → Experiments
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_DATASET_NAME = "redteam_eval"

_TC_CATEGORIES: list[tuple[range, str]] = [
    (range(1, 8), "information_extraction"),
    (range(8, 13), "prompt_injection"),
    (range(13, 17), "persona_boundary"),
    (range(17, 21), "qualification_bypass"),
]


def _threat_category(description: str) -> str:
    m = re.search(r"TC-ADV-(\d+)", description)
    if not m:
        return "unknown"
    n = int(m.group(1))
    for r, cat in _TC_CATEGORIES:
        if n in r:
            return cat
    return "unknown"


def _user_prompt(result: dict) -> str:
    """Return the most readable prompt for a result (single-turn or multi-turn)."""
    prompt_val = result.get("vars", {}).get("prompt")
    if prompt_val:
        return str(prompt_val)
    prompt_obj = result.get("prompt", {})
    return prompt_obj.get("display") or prompt_obj.get("raw") or result.get("description", "")


def _init_langfuse():
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
        print(f"[warning] Langfuse init failed: {exc}")
        return None


def _ensure_dataset(lf) -> None:
    try:
        lf.create_dataset(
            name=_DATASET_NAME,
            description="promptfoo red team adversarial evaluation — TC-ADV-001..020",
        )
    except Exception:  # noqa: BLE001
        pass  # dataset already exists


def _upsert_dataset_items(lf, results: list[dict]) -> dict[str, str]:
    """Create (or reuse) one dataset item per test case. Returns description → item.id."""
    item_id_map: dict[str, str] = {}
    for res in results:
        desc = res.get("description", "")
        rubric_parts = []
        for cr in (res.get("gradingResult") or {}).get("componentResults", []):
            rubric_parts.append(cr.get("reason", ""))
        try:
            di = lf.create_dataset_item(
                dataset_name=_DATASET_NAME,
                input={"prompt": _user_prompt(res), "description": desc},
                expected_output={"rubric": " | ".join(filter(None, rubric_parts))},
                metadata={
                    "session_id": res.get("vars", {}).get("sessionId", ""),
                    "threat_category": _threat_category(desc),
                },
            )
            item_id_map[desc] = di.id
        except Exception as exc:  # noqa: BLE001
            print(f"  [warning] Could not upsert dataset item '{desc}': {exc}")
    return item_id_map


def _export_results(lf, results: list[dict], run_name: str, item_id_map: dict[str, str]) -> None:
    for res in results:
        desc = res.get("description", "")
        dataset_item_id = item_id_map.get(desc, "")
        response_text = (res.get("response") or {}).get("output", "")
        try:
            obs = lf.start_observation(
                name=desc or "redteam-case",
                input={"prompt": _user_prompt(res), "description": desc},
                output={"response": response_text},
                metadata={
                    "threat_category": _threat_category(desc),
                    "success": res.get("success"),
                    "score": res.get("score"),
                    "run_name": run_name,
                },
                tags=["redteam", run_name],
            )
            trace_id = obs.trace_id
            obs.end()
        except Exception as exc:  # noqa: BLE001
            print(f"  [warning] Trace creation failed for '{desc}': {exc}")
            continue

        # Overall pass score
        try:
            lf.create_score(
                trace_id=trace_id,
                name="pass",
                value=1.0 if res.get("success") else 0.0,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [warning] Score 'pass' failed for '{desc}': {exc}")

        # Per-assertion scores
        for idx, cr in enumerate((res.get("gradingResult") or {}).get("componentResults", [])):
            assertion_type = (cr.get("assertion") or {}).get("type", f"assertion_{idx}")
            score_name = f"{assertion_type}_{idx}"
            try:
                lf.create_score(
                    trace_id=trace_id,
                    name=score_name,
                    value=float(cr.get("score", 1.0 if cr.get("pass") else 0.0)),
                    comment=cr.get("reason", ""),
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [warning] Score '{score_name}' failed for '{desc}': {exc}")

        # Link to dataset experiment
        if dataset_item_id and trace_id:
            try:
                lf.api.dataset_run_items.create(
                    run_name=run_name,
                    dataset_item_id=dataset_item_id,
                    trace_id=trace_id,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [warning] Dataset run item link failed for '{desc}': {exc}")


def _print_summary(results: list[dict], stats: dict, run_name: str) -> None:
    categories: dict[str, dict[str, int]] = {}
    for res in results:
        cat = _threat_category(res.get("description", ""))
        if cat not in categories:
            categories[cat] = {"pass": 0, "fail": 0}
        if res.get("success"):
            categories[cat]["pass"] += 1
        else:
            categories[cat]["fail"] += 1

    total_pass = stats.get("successes", 0)
    total_fail = stats.get("failures", 0)
    total = total_pass + total_fail

    print(f"\nRed team results — {run_name}")
    print(f"  {'Category':<28} {'Pass':>4}  {'Fail':>4}")
    print("  " + "-" * 42)
    for cat, counts in categories.items():
        print(f"  {cat:<28} {counts['pass']:>4}  {counts['fail']:>4}")
    print("  " + "-" * 42)
    status = "✓ all passed" if total_fail == 0 else f"✗ {total_fail} failed"
    print(f"  {'TOTAL':<28} {total_pass:>4}  {total_fail:>4}   ({total} tests) {status}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export promptfoo red team results to Langfuse")
    parser.add_argument("--results", required=True, help="Path to promptfoo JSON results file")
    parser.add_argument("--run-name", required=True, help="Experiment run name (e.g. ci-12345-baseline)")
    args = parser.parse_args(argv)

    results_path = Path(args.results)
    if not results_path.exists():
        print(f"[error] Results file not found: {results_path}", file=sys.stderr)
        return 1

    data = json.loads(results_path.read_text())
    raw = data.get("results", [])
    if isinstance(raw, dict):
        # promptfoo ≥ v0.100 wraps results in a dict with version/stats/table sub-keys
        results: list[dict] = raw.get("results", [])
        stats: dict = raw.get("stats", data.get("stats", {}))
    else:
        results = raw
        stats = data.get("stats", {})

    _print_summary(results, stats, args.run_name)

    lf = _init_langfuse()
    if lf is None:
        print("Langfuse not configured — skipping upload (set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY)")
        return 0

    print(f"Exporting {len(results)} results to Langfuse dataset '{_DATASET_NAME}'…")
    _ensure_dataset(lf)
    item_id_map = _upsert_dataset_items(lf, results)
    _export_results(lf, results, args.run_name, item_id_map)

    try:
        lf.flush()
        print(f"  → Langfuse experiment logged: {_DATASET_NAME} / {args.run_name}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [warning] Langfuse flush failed: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
