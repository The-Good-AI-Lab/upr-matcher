#!/usr/bin/env python3
"""Compute final match-quality metrics from human-labeled candidate rows."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES = REPO_ROOT / "evals/labeling/costa_rica_candidate_pairs.jsonl"
DEFAULT_MISSING = REPO_ROOT / "evals/labeling/costa_rica_missing_gold_pairs.jsonl"
DEFAULT_REPORT = REPO_ROOT / "evals/reports/costa_rica_final_match_quality.md"
DEFAULT_JSON = REPO_ROOT / "evals/reports/costa_rica_final_match_quality.json"
RELEVANT_LABELS = {"similar", "very_similar"}
DECISIVE_LABELS = {"very_similar", "similar", "not_relevant"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return round(2 * precision * recall / (precision + recall), 4)


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def selected_by_policy(row: dict[str, Any], *, max_rank: int, min_semantic_score: float | None) -> bool:
    rank = row.get("rank")
    if not isinstance(rank, int) or rank > max_rank:
        return False
    if min_semantic_score is None:
        return True
    score = row.get("semantic_score")
    return isinstance(score, (int, float)) and float(score) >= min_semantic_score


def summarize_rows(
    candidates: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    *,
    max_rank: int,
    min_semantic_score: float | None,
) -> dict[str, Any]:
    selected = [row for row in candidates if selected_by_policy(row, max_rank=max_rank, min_semantic_score=min_semantic_score)]
    selected_decisive = [row for row in selected if row.get("human_relevance") in DECISIVE_LABELS]
    selected_relevant = [row for row in selected_decisive if row.get("human_relevance") in RELEVANT_LABELS]
    all_decisive = [row for row in candidates if row.get("human_relevance") in DECISIVE_LABELS]
    all_relevant = [row for row in all_decisive if row.get("human_relevance") in RELEVANT_LABELS]
    unlabeled_selected = len(selected) - len(selected_decisive)
    non_decisive_candidates = len(candidates) - len(all_decisive)
    recall_denominator_ready = non_decisive_candidates == 0
    recall_denominator = len(all_relevant) + len(missing)
    precision = pct(len(selected_relevant), len(selected_decisive))
    recall = pct(len(selected_relevant), recall_denominator) if recall_denominator_ready else None
    return {
        "candidate_rows": len(candidates),
        "selected_rows": len(selected),
        "selected_decisive_rows": len(selected_decisive),
        "selected_relevant_rows": len(selected_relevant),
        "selected_unlabeled_or_unclear_rows": unlabeled_selected,
        "all_decisive_candidate_rows": len(all_decisive),
        "all_relevant_candidate_rows": len(all_relevant),
        "unlabeled_or_unclear_candidate_rows": non_decisive_candidates,
        "missing_gold_rows": len(missing),
        "recall_denominator_ready": recall_denominator_ready,
        "recall_denominator": recall_denominator if recall_denominator_ready else None,
        "precision": precision,
        "recall": recall,
        "f1": f1(precision, recall),
    }


def summarize_by_language(
    candidates: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    *,
    max_rank: int,
    min_semantic_score: float | None,
) -> dict[str, dict[str, Any]]:
    languages = sorted({row.get("language_pair", "unknown") for row in candidates} | {row.get("language_pair", "unknown") for row in missing})
    summaries: dict[str, dict[str, Any]] = {}
    for language in languages:
        language_candidates = [row for row in candidates if row.get("language_pair") == language]
        language_missing = [row for row in missing if row.get("language_pair") == language]
        summaries[language] = summarize_rows(
            language_candidates,
            language_missing,
            max_rank=max_rank,
            min_semantic_score=min_semantic_score,
        )
    return summaries


def failure_categories_for_false_positives(
    candidates: list[dict[str, Any]],
    *,
    max_rank: int,
    min_semantic_score: float | None,
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in candidates:
        if not selected_by_policy(row, max_rank=max_rank, min_semantic_score=min_semantic_score):
            continue
        if row.get("human_relevance") == "not_relevant":
            counts[str(row.get("failure_category") or "uncategorized")] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def render_report(summary: dict[str, Any]) -> str:
    policy = summary["policy"]
    overall = summary["overall"]
    lines = [
        "# Costa Rica Final Match Quality",
        "",
        "This report evaluates a configurable final-output policy over human-labeled candidate rows.",
        "Metrics stay `n/a` until the candidate queue has decisive human labels.",
        "",
        "## Policy",
        "",
        f"- Max rank: {policy['max_rank']}",
        f"- Minimum semantic score: {fmt(policy['min_semantic_score'])}",
        "",
        "## Overall",
        "",
        f"- Candidate rows: {overall['candidate_rows']}",
        f"- Selected rows: {overall['selected_rows']}",
        f"- Selected decisive rows: {overall['selected_decisive_rows']}",
        f"- Selected relevant rows: {overall['selected_relevant_rows']}",
        f"- Selected unlabeled or unclear rows: {overall['selected_unlabeled_or_unclear_rows']}",
        f"- Missing-gold rows: {overall['missing_gold_rows']}",
        f"- Precision: {fmt(overall['precision'])}",
        f"- Recall: {fmt(overall['recall'])}",
        f"- F1: {fmt(overall['f1'])}",
        "",
        "## By Language",
        "",
        "| Pair | Selected | Decisive | Relevant | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for language, values in summary["by_language"].items():
        lines.append(
            f"| `{language}` | {values['selected_rows']} | {values['selected_decisive_rows']} | "
            f"{values['selected_relevant_rows']} | {fmt(values['precision'])} | {fmt(values['recall'])} | "
            f"{fmt(values['f1'])} |"
        )
    lines.extend(["", "## Selected False-Positive Categories", ""])
    if summary["selected_false_positive_categories"]:
        for category, count in summary["selected_false_positive_categories"].items():
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- None yet.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--missing", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--max-rank", type=int, default=10)
    parser.add_argument("--min-semantic-score", type=float, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_rank < 1:
        raise ValueError("--max-rank must be at least 1")
    candidates = read_jsonl(args.candidates)
    missing = read_jsonl(args.missing)
    summary = {
        "policy": {
            "max_rank": args.max_rank,
            "min_semantic_score": args.min_semantic_score,
        },
        "overall": summarize_rows(
            candidates,
            missing,
            max_rank=args.max_rank,
            min_semantic_score=args.min_semantic_score,
        ),
        "by_language": summarize_by_language(
            candidates,
            missing,
            max_rank=args.max_rank,
            min_semantic_score=args.min_semantic_score,
        ),
        "selected_false_positive_categories": failure_categories_for_false_positives(
            candidates,
            max_rank=args.max_rank,
            min_semantic_score=args.min_semantic_score,
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(summary), encoding="utf-8")
    args.json_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote report to {args.report}")
    print(f"wrote json to {args.json_output}")


if __name__ == "__main__":
    main()
