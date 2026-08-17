#!/usr/bin/env python3
"""Validate a binary judge output against human labels."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPO_ROOT / "evals/reports/binary_judge_validation.md"
DEFAULT_JSON = REPO_ROOT / "evals/reports/binary_judge_validation.json"


def read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        rows = payload.get("rows")
        if isinstance(rows, list):
            return rows
        raise ValueError("JSON input must be a list or an object with a `rows` list.")
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    raise ValueError("Input must be .jsonl, .json, or .csv")


def normalize_label(value: Any, *, pass_label: str, fail_label: str) -> bool | None:
    cleaned = str(value or "").strip().lower()
    if cleaned == pass_label:
        return True
    if cleaned == fail_label:
        return False
    return None


def pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def validate_rows(
    rows: list[dict[str, Any]],
    *,
    human_field: str,
    judge_field: str,
    pass_label: str,
    fail_label: str,
) -> dict[str, Any]:
    tp = tn = fp = fn = skipped = 0
    invalid_examples: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        human = normalize_label(row.get(human_field), pass_label=pass_label, fail_label=fail_label)
        judge = normalize_label(row.get(judge_field), pass_label=pass_label, fail_label=fail_label)
        if human is None or judge is None:
            skipped += 1
            if len(invalid_examples) < 5:
                invalid_examples.append(
                    {
                        "row": index,
                        "human_label": row.get(human_field),
                        "judge_label": row.get(judge_field),
                    }
                )
            continue
        if human and judge:
            tp += 1
        elif not human and not judge:
            tn += 1
        elif not human and judge:
            fp += 1
        else:
            fn += 1
    positives = tp + fn
    negatives = tn + fp
    judged = tp + tn + fp + fn
    return {
        "rows": len(rows),
        "judged_rows": judged,
        "skipped_rows": skipped,
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "tpr": pct(tp, positives),
        "tnr": pct(tn, negatives),
        "precision": pct(tp, tp + fp),
        "accuracy": pct(tp + tn, judged),
        "false_positive_rate": pct(fp, negatives),
        "false_negative_rate": pct(fn, positives),
        "invalid_examples": invalid_examples,
    }


def render_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Binary Judge Validation",
            "",
            "This report validates a binary judge against human labels. TPR and TNR are the primary alignment metrics.",
            "",
            f"- Rows: {summary['rows']}",
            f"- Judged rows: {summary['judged_rows']}",
            f"- Skipped rows: {summary['skipped_rows']}",
            "",
            "## Confusion Matrix",
            "",
            "| | Judge pass | Judge fail |",
            "| --- | ---: | ---: |",
            f"| Human pass | {summary['true_positive']} | {summary['false_negative']} |",
            f"| Human fail | {summary['false_positive']} | {summary['true_negative']} |",
            "",
            "## Metrics",
            "",
            f"- TPR: {fmt(summary['tpr'])}",
            f"- TNR: {fmt(summary['tnr'])}",
            f"- Precision: {fmt(summary['precision'])}",
            f"- Accuracy: {fmt(summary['accuracy'])}",
            f"- False positive rate: {fmt(summary['false_positive_rate'])}",
            f"- False negative rate: {fmt(summary['false_negative_rate'])}",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--human-field", default="human_label")
    parser.add_argument("--judge-field", default="judge_label")
    parser.add_argument("--pass-label", default="pass")
    parser.add_argument("--fail-label", default="fail")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_rows(args.input)
    summary = validate_rows(
        rows,
        human_field=args.human_field,
        judge_field=args.judge_field,
        pass_label=args.pass_label.lower(),
        fail_label=args.fail_label.lower(),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(summary), encoding="utf-8")
    args.json_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote report to {args.report}")
    print(f"wrote json to {args.json_output}")


if __name__ == "__main__":
    main()
