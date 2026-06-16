#!/usr/bin/env python3
"""Summarize human labels from Costa Rica candidate labeling queues."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANDIDATES = REPO_ROOT / "evals/labeling/costa_rica_candidate_pairs.jsonl"
DEFAULT_MISSING = REPO_ROOT / "evals/labeling/costa_rica_missing_gold_pairs.jsonl"
DEFAULT_REPORT = REPO_ROOT / "evals/reports/costa_rica_candidate_label_metrics.md"
RELEVANT_LABELS = {"similar", "very_similar"}
VALID_RELEVANCE = {"", "very_similar", "similar", "not_relevant", "unclear"}
VALID_FAILURE_CATEGORIES = {
    "",
    "theme_only",
    "too_broad",
    "too_narrow",
    "cross_lingual_miss",
    "general_retrieval_miss",
    "label_ambiguous",
    "other",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(numerator: int, denominator: int) -> float | str:
    if denominator == 0:
        return "n/a"
    return round(numerator / denominator, 4)


def validate_candidate_labels(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        label = row.get("human_relevance", "")
        if label not in VALID_RELEVANCE:
            raise ValueError(f"Invalid human_relevance on candidate row {index}: {label!r}")
        category = row.get("failure_category", "")
        if category not in VALID_FAILURE_CATEGORIES:
            raise ValueError(f"Invalid failure_category on candidate row {index}: {category!r}")
        if label == "not_relevant" and not row.get("failure_category"):
            raise ValueError(f"Candidate row {index} is not_relevant but has no failure_category.")
        if row.get("failure_category") and label in {"", "unclear"}:
            raise ValueError(f"Candidate row {index} has failure_category but no decisive relevance label.")


def validate_missing_labels(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        if row.get("missing_reason") != "gold_not_in_top_k":
            raise ValueError(f"Invalid missing_reason on missed-gold row {index}: {row.get('missing_reason')!r}")
        category = row.get("failure_category", "")
        if category not in VALID_FAILURE_CATEGORIES:
            raise ValueError(f"Invalid failure_category on missed-gold row {index}: {category!r}")


def candidate_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [row for row in rows if row.get("human_relevance")]
    decisive = [row for row in labeled if row.get("human_relevance") != "unclear"]
    relevant = [row for row in decisive if row.get("human_relevance") in RELEVANT_LABELS]
    by_language: dict[str, dict[str, Any]] = {}
    for language in sorted({row["language_pair"] for row in rows}):
        language_rows = [row for row in rows if row["language_pair"] == language]
        language_labeled = [row for row in language_rows if row.get("human_relevance")]
        language_decisive = [row for row in language_labeled if row.get("human_relevance") != "unclear"]
        language_relevant = [row for row in language_decisive if row.get("human_relevance") in RELEVANT_LABELS]
        by_language[language] = {
            "rows": len(language_rows),
            "labeled": len(language_labeled),
            "decisive": len(language_decisive),
            "relevant": len(language_relevant),
            "precision": pct(len(language_relevant), len(language_decisive)),
        }

    by_rank: dict[int, dict[str, Any]] = {}
    for rank in sorted({int(row["rank"]) for row in rows if row.get("rank") is not None}):
        rank_rows = [row for row in rows if row.get("rank") == rank and row.get("human_relevance") and row.get("human_relevance") != "unclear"]
        rank_relevant = [row for row in rank_rows if row.get("human_relevance") in RELEVANT_LABELS]
        by_rank[rank] = {
            "decisive": len(rank_rows),
            "relevant": len(rank_relevant),
            "precision": pct(len(rank_relevant), len(rank_rows)),
        }

    return {
        "rows": len(rows),
        "labeled": len(labeled),
        "decisive": len(decisive),
        "relevant": len(relevant),
        "precision": pct(len(relevant), len(decisive)),
        "by_language": by_language,
        "by_rank": by_rank,
        "failure_categories": Counter(row.get("failure_category") for row in decisive if row.get("failure_category")),
    }


def missing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = [row for row in rows if row.get("failure_category") or row.get("review_notes")]
    by_language: dict[str, dict[str, Any]] = {}
    for language in sorted({row["language_pair"] for row in rows}):
        language_rows = [row for row in rows if row["language_pair"] == language]
        language_reviewed = [row for row in language_rows if row.get("failure_category") or row.get("review_notes")]
        by_language[language] = {
            "rows": len(language_rows),
            "reviewed": len(language_reviewed),
            "failure_categories": Counter(row.get("failure_category") for row in language_reviewed if row.get("failure_category")),
        }
    return {
        "rows": len(rows),
        "reviewed": len(reviewed),
        "by_language": by_language,
        "failure_categories": Counter(row.get("failure_category") for row in reviewed if row.get("failure_category")),
    }


def render_counter(counter: Counter[str]) -> list[str]:
    if not counter:
        return ["- None yet."]
    return [f"- `{name}`: {count}" for name, count in counter.most_common()]


def render_report(candidates: list[dict[str, Any]], missing: list[dict[str, Any]]) -> str:
    candidate = candidate_summary(candidates)
    missed = missing_summary(missing)
    lines = [
        "# Costa Rica Candidate Label Metrics",
        "",
        "This report uses human-filled labels from the blinded candidate queue. Blank labels are excluded from precision metrics.",
        "",
        "## Candidate Labels",
        "",
        f"- Candidate rows: {candidate['rows']}",
        f"- Labeled rows: {candidate['labeled']}",
        f"- Decisive rows: {candidate['decisive']}",
        f"- Relevant rows: {candidate['relevant']}",
        f"- Precision over decisive labels: {candidate['precision']}",
        "",
        "| Language pair | Rows | Labeled | Decisive | Relevant | Precision |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for language, values in candidate["by_language"].items():
        lines.append(
            f"| `{language}` | {values['rows']} | {values['labeled']} | {values['decisive']} | "
            f"{values['relevant']} | {values['precision']} |"
        )

    lines.extend(["", "## Precision By Rank", "", "| Rank | Decisive | Relevant | Precision |", "| ---: | ---: | ---: | ---: |"])
    for rank, values in candidate["by_rank"].items():
        if values["decisive"]:
            lines.append(f"| {rank} | {values['decisive']} | {values['relevant']} | {values['precision']} |")
    if not any(values["decisive"] for values in candidate["by_rank"].values()):
        lines.append("| n/a | 0 | 0 | n/a |")

    lines.extend(["", "## Candidate Failure Categories", ""])
    lines.extend(render_counter(candidate["failure_categories"]))

    lines.extend(
        [
            "",
            "## Missed Gold Positives",
            "",
            f"- Missed-gold rows: {missed['rows']}",
            f"- Reviewed missed-gold rows: {missed['reviewed']}",
            "",
            "| Language pair | Missed gold rows | Reviewed |",
            "| --- | ---: | ---: |",
        ]
    )
    for language, values in missed["by_language"].items():
        lines.append(f"| `{language}` | {values['rows']} | {values['reviewed']} |")

    lines.extend(["", "## Missed-Gold Failure Categories", ""])
    lines.extend(render_counter(missed["failure_categories"]))
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--missing", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates = read_jsonl(args.candidates)
    missing = read_jsonl(args.missing)
    validate_candidate_labels(candidates)
    validate_missing_labels(missing)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(candidates, missing), encoding="utf-8")
    print(f"wrote report to {args.report}")


if __name__ == "__main__":
    main()
