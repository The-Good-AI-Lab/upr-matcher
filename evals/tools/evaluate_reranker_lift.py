#!/usr/bin/env python3
"""Summarize reranker lift from AI pipeline eval traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACE_ROOT = REPO_ROOT / "evals/traces/live"
DEFAULT_REPORT = REPO_ROOT / "evals/reports/reranker_lift.md"
DEFAULT_JSON = REPO_ROOT / "evals/reports/reranker_lift.json"
METRIC_KEYS = ("hit@10", "recall@10", "precision@10", "mrr", "ndcg@10")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def metric_value(metrics: dict[str, Any] | None, key: str) -> float | None:
    if not metrics:
        return None
    value = (metrics.get("macro") or {}).get(key)
    return float(value) if value is not None else None


def fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def trace_has_reranker_metrics(trace: dict[str, Any]) -> bool:
    reranking = trace.get("reranking") or {}
    return bool(reranking.get("metrics"))


def discover_traces(trace_root: Path) -> list[Path]:
    if not trace_root.exists():
        return []
    paths: list[Path] = []
    for path in sorted(trace_root.glob("*.json")):
        try:
            trace = read_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        if trace_has_reranker_metrics(trace):
            paths.append(path)
    return paths


def row_for_trace(path: Path) -> dict[str, Any] | None:
    trace = read_json(path)
    if not trace_has_reranker_metrics(trace):
        return None
    settings = trace.get("settings") or {}
    semantic_metrics = (trace.get("semantic_candidate_matching") or {}).get("metrics")
    reranker_metrics = (trace.get("reranking") or {}).get("metrics")
    row: dict[str, Any] = {
        "run_id": trace.get("run_id") or path.stem,
        "trace_path": str(path),
        "case_id": (trace.get("case") or {}).get("case_id"),
        "language_pair": f"{settings.get('source_language', 'unknown')}-en",
        "source_mode": settings.get("source_mode"),
        "candidate_top_k": settings.get("candidate_top_k"),
        "reranker_top_k": settings.get("reranker_top_k"),
        "evaluated_sources": (semantic_metrics or {}).get("evaluated_sources", 0),
    }
    for key in METRIC_KEYS:
        semantic = metric_value(semantic_metrics, key)
        reranked = metric_value(reranker_metrics, key)
        row[f"semantic_{key}"] = semantic
        row[f"reranked_{key}"] = reranked
        row[f"delta_{key}"] = None if semantic is None or reranked is None else round(reranked - semantic, 4)
    return row


def build_rows(trace_paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in trace_paths:
        row = row_for_trace(path)
        if row:
            rows.append(row)
    return rows


def render_report(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Reranker Lift",
        "",
        "This report compares semantic-candidate ranking against reranked candidates inside the same trace.",
        "",
    ]
    if not rows:
        lines.extend(
            [
                "No traces with reranker metrics were found.",
                "",
                "Run `evals/tools/run_ai_pipeline_eval.py` without `--skip-reranker`, then rerun this report.",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Run | Pair | Sources | candidate_top_k | reranker_top_k | recall@10 sem | recall@10 rerank | delta | MRR sem | MRR rerank | delta |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['run_id']}` | `{row['language_pair']}` | {row['evaluated_sources']} | "
            f"{row.get('candidate_top_k') or 'n/a'} | {row.get('reranker_top_k') or 'n/a'} | "
            f"{fmt(row['semantic_recall@10'])} | {fmt(row['reranked_recall@10'])} | {fmt(row['delta_recall@10'])} | "
            f"{fmt(row['semantic_mrr'])} | {fmt(row['reranked_mrr'])} | {fmt(row['delta_mrr'])} |"
        )

    lines.extend(
        [
            "",
            "## Full Metric Deltas",
            "",
            "| Run | Metric | Semantic | Reranked | Delta |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        for key in METRIC_KEYS:
            lines.append(
                f"| `{row['run_id']}` | `{key}` | {fmt(row[f'semantic_{key}'])} | "
                f"{fmt(row[f'reranked_{key}'])} | {fmt(row[f'delta_{key}'])} |"
            )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, action="append", dest="traces")
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trace_paths = args.traces or discover_traces(args.trace_root)
    rows = build_rows(trace_paths)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(rows), encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote report to {args.report}")
    print(f"wrote json to {args.json_output}")


if __name__ == "__main__":
    main()
