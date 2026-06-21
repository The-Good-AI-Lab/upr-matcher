#!/usr/bin/env python3
"""Run repeated live FMSI extraction evals and summarize stability."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "evals/tools"
DEFAULT_TRACE_ROOT = REPO_ROOT / "evals/traces/live"
DEFAULT_REPORT_ROOT = REPO_ROOT / "evals/reports/live"

sys.path.insert(0, str(TOOLS_ROOT))

from run_ai_pipeline_eval import (  # noqa: E402
    DEFAULT_CHUNK_CHAR_LIMIT,
    DEFAULT_GOLD_LINKS,
    DEFAULT_GOLD_SOURCES,
    DEFAULT_PROMPT_PATH,
    BudgetTracker,
    Settings,
    evaluate_llm_extraction,
    extract_fmsi_with_openrouter,
    load_costa_rica_case,
    normalize_text,
    sha256_file,
)


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def min_mean_max(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "mean": 0.0, "max": 0.0}
    return {
        "min": round(min(values), 4),
        "mean": mean(values),
        "max": round(max(values), 4),
    }


def recommendation_set(recommendations: list[dict[str, Any]]) -> set[str]:
    return {normalize_text(str(item.get("recommendation") or "")) for item in recommendations if item.get("recommendation")}


def pairwise_jaccard(sets: list[set[str]]) -> dict[str, float]:
    scores: list[float] = []
    for left_index, left in enumerate(sets):
        for right in sets[left_index + 1 :]:
            if not left and not right:
                scores.append(1.0)
            elif not left or not right:
                scores.append(0.0)
            else:
                scores.append(len(left & right) / len(left | right))
    return min_mean_max(scores)


def aggregate_repeats(repeats: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in repeats if not item.get("error")]
    observed_counts = [float(item["metrics"].get("observed_count", 0)) for item in repeats]
    coverages = [float(item["metrics"].get("gold_coverage_at_threshold", 0.0)) for item in repeats]
    average_similarities = [float(item["metrics"].get("average_best_similarity", 0.0)) for item in repeats]
    duplicate_counts = [float(item["metrics"].get("duplicate_recommendation_count", 0)) for item in repeats]
    recommendation_sets = [recommendation_set(item["recommendations"]) for item in repeats]
    return {
        "repeats_completed": len(repeats),
        "successful_repeats": len(successful),
        "failed_repeats": len(repeats) - len(successful),
        "observed_count": min_mean_max(observed_counts),
        "gold_coverage_at_threshold": min_mean_max(coverages),
        "average_best_similarity": min_mean_max(average_similarities),
        "duplicate_recommendation_count": min_mean_max(duplicate_counts),
        "pairwise_recommendation_jaccard": pairwise_jaccard(recommendation_sets),
    }


def render_report(trace: dict[str, Any], trace_path: Path) -> str:
    aggregate = trace["aggregate"]
    lines = [
        f"# Extraction Stability Eval: {trace['case']['case_id']}",
        "",
        f"- Run ID: `{trace['run_id']}`",
        f"- Trace JSON: `{trace_path}`",
        f"- Source language: `{trace['settings']['source_language']}`",
        f"- OpenRouter calls: {trace['openrouter_usage']['calls']} "
        f"(~${trace['openrouter_usage']['estimated_cost_usd']:.6f} estimated)",
        f"- Repeats completed: {aggregate['repeats_completed']}",
        f"- Successful repeats: {aggregate['successful_repeats']}",
        f"- Failed repeats: {aggregate['failed_repeats']}",
        "",
        "## Aggregate",
        "",
        "| Metric | Min | Mean | Max |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key, title in (
        ("observed_count", "Extracted recommendations"),
        ("gold_coverage_at_threshold", "Gold coverage"),
        ("average_best_similarity", "Average best similarity"),
        ("duplicate_recommendation_count", "Duplicate count"),
        ("pairwise_recommendation_jaccard", "Pairwise recommendation Jaccard"),
    ):
        values = aggregate[key]
        lines.append(f"| {title} | {values['min']} | {values['mean']} | {values['max']} |")

    lines.extend(
        [
            "",
            "## Repeats",
            "",
            "| Repeat | Extracted | Gold coverage | Average best similarity | Duplicates | Chunks |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in trace["repeats"]:
        metrics = item["metrics"]
        lines.append(
            f"| {item['repeat_index']} | {metrics.get('observed_count', 0)} | "
            f"{metrics.get('gold_coverage_at_threshold', 0.0)} | "
            f"{metrics.get('average_best_similarity', 0.0)} | "
            f"{metrics.get('duplicate_recommendation_count', 0)} | {len(item['chunks'])} |"
        )
    failures = [item for item in trace["repeats"] if item.get("error")]
    if failures:
        lines.extend(["", "## Failed Repeats", "", "| Repeat | Error |", "| ---: | --- |"])
        for item in failures:
            lines.append(f"| {item['repeat_index']} | {item['error']} |")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", default="costa_rica_2024", choices=["costa_rica_2024"])
    parser.add_argument("--gold-sources", default=str(DEFAULT_GOLD_SOURCES))
    parser.add_argument("--gold-links", default=str(DEFAULT_GOLD_LINKS))
    parser.add_argument("--source-language", choices=["es", "en"], default="es")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--allow-openrouter", action="store_true")
    parser.add_argument("--openrouter-model", default=None)
    parser.add_argument("--max-cost-usd", type=float, default=10.0)
    parser.add_argument("--prompt-usd-per-1m", type=float, default=1.0)
    parser.add_argument("--completion-usd-per-1m", type=float, default=1.0)
    parser.add_argument("--max-llm-chunks", type=int, default=1)
    parser.add_argument("--max-chunk-chars", type=int, default=DEFAULT_CHUNK_CHAR_LIMIT)
    parser.add_argument("--max-completion-tokens", type=int, default=4096)
    parser.add_argument("--extraction-similarity-threshold", type=float, default=0.35)
    parser.add_argument("--prompt-path", default=str(DEFAULT_PROMPT_PATH))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repeats < 1:
        raise ValueError("--repeats must be at least 1")
    if not args.allow_openrouter:
        raise RuntimeError("Refusing live OpenRouter extraction without --allow-openrouter")

    run_id = args.run_id or f"extraction_stability_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    case = load_costa_rica_case(args)
    budget = BudgetTracker(
        max_cost_usd=args.max_cost_usd,
        prompt_usd_per_1m=args.prompt_usd_per_1m,
        completion_usd_per_1m=args.completion_usd_per_1m,
    )
    model = args.openrouter_model or Settings().model
    repeats: list[dict[str, Any]] = []
    for repeat_index in range(1, args.repeats + 1):
        try:
            result = extract_fmsi_with_openrouter(case, args, budget)
            recommendations = [
                {
                    "recommendation": rec.recommendation,
                    "domain": rec.domain,
                    "beneficiaries": rec.beneficiaries,
                    "theme": rec.theme,
                }
                for rec in result["recommendations"]
            ]
            repeats.append(
                {
                    "repeat_index": repeat_index,
                    "metrics": evaluate_llm_extraction(
                        result["recommendations"],
                        case.gold_sources,
                        language=args.source_language,
                        similarity_threshold=args.extraction_similarity_threshold,
                    ),
                    "chunks": [
                        {
                            "chunk_index": chunk["chunk_index"],
                            "chunk_chars": chunk["chunk_chars"],
                            "recommendations_count": chunk["recommendations_count"],
                            "prompt_tokens": chunk["prompt_tokens"],
                            "completion_tokens": chunk["completion_tokens"],
                        }
                        for chunk in result["chunks"]
                    ],
                    "recommendations": recommendations,
                }
            )
        except Exception as exc:
            repeats.append(
                {
                    "repeat_index": repeat_index,
                    "error": f"{type(exc).__name__}: {exc}",
                    "metrics": {
                        "expected_gold_count": len(case.gold_sources),
                        "observed_count": 0,
                        "gold_coverage_at_threshold": 0.0,
                        "similarity_threshold": args.extraction_similarity_threshold,
                        "average_best_similarity": 0.0,
                        "duplicate_recommendation_count": 0,
                        "best_by_gold": [],
                    },
                    "chunks": [],
                    "recommendations": [],
                }
            )

    trace = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "case": {
            "case_id": case.case_id,
            "source_pdf": str(case.source_pdf),
            "reference_doc": str(case.reference_doc),
            "source_file_sha256": sha256_file(case.source_pdf),
            "reference_file_sha256": sha256_file(case.reference_doc),
        },
        "settings": {
            "source_language": args.source_language,
            "openrouter_model": model,
            "max_llm_chunks": args.max_llm_chunks,
            "max_chunk_chars": args.max_chunk_chars,
            "max_completion_tokens": args.max_completion_tokens,
            "extraction_similarity_threshold": args.extraction_similarity_threshold,
        },
        "repeats": repeats,
        "aggregate": aggregate_repeats(repeats),
        "openrouter_usage": budget.as_dict(),
    }
    args.trace_root.mkdir(parents=True, exist_ok=True)
    args.report_root.mkdir(parents=True, exist_ok=True)
    trace_path = args.trace_root / f"{run_id}.json"
    report_path = args.report_root / f"{run_id}.md"
    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_report(trace, trace_path), encoding="utf-8")
    print(f"wrote trace: {trace_path}")
    print(f"wrote report: {report_path}")
    print(
        "extraction "
        f"coverage_min={trace['aggregate']['gold_coverage_at_threshold']['min']} "
        f"coverage_mean={trace['aggregate']['gold_coverage_at_threshold']['mean']} "
        f"count_mean={trace['aggregate']['observed_count']['mean']}"
    )
    print(f"openrouter estimated_cost=${trace['openrouter_usage']['estimated_cost_usd']:.6f}")


if __name__ == "__main__":
    main()
