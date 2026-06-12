"""Result reporting for the RAGAS evaluation pipeline — console table and JSON file."""
from __future__ import annotations

import datetime
import json
from pathlib import Path


def print_results(scores: dict[str, float], thresholds: dict[str, float]) -> bool:
    """Print a results table. Returns True if all thresholds pass."""
    print()
    print(f"  {'Metric':<24} {'Score':>6}  {'Threshold':>9}  {'Pass':>4}")
    print("  " + "-" * 50)
    all_pass = True
    for metric, threshold in thresholds.items():
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


def write_local_report(
    scores: dict[str, float],
    run_name: str,
    all_pass: bool,
    embedding_mode: str,
    thresholds: dict[str, float],
) -> None:
    """Write a JSON report to evaluation/.evaluation-reports/<run_name>.json."""
    report_dir = Path(__file__).parent.parent / ".evaluation-reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "run_name": run_name,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "embedding_mode": embedding_mode,
        "all_pass": all_pass,
        "thresholds": thresholds,
        "scores": {
            metric: {
                "value": scores.get(metric),
                "threshold": thresholds[metric],
                "pass": (
                    scores[metric] >= thresholds[metric]
                    if metric in scores and scores[metric] is not None
                    else None
                ),
            }
            for metric in thresholds
        },
    }

    report_path = report_dir / f"{run_name}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"  → Local report written: {report_path}")
