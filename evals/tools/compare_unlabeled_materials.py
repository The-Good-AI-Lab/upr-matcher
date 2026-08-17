#!/usr/bin/env python3
"""Compare deterministic extraction coverage across unlabeled UPR materials."""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from docx import Document


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
MANIFEST = REPO_ROOT / "evals/datasets/upr_materials_document_pairs.jsonl"
OUT_JSONL = REPO_ROOT / "evals/reports/upr_materials_extraction_comparison.jsonl"
OUT_MD = REPO_ROOT / "evals/reports/upr_materials_extraction_comparison.md"

sys.path.insert(0, str(BACKEND_ROOT))

from fmsi_un_recommendations.recommendation_processing import extract_un_recommendation_rows  # noqa: E402
from fmsi_un_recommendations.utils import read_text_file  # noqa: E402


LEADING_TARGET_ID_RE = re.compile(r"^\s*(\d{2,3}\.\d{1,3})(?=\D)")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def target_id_for_cells(cells: list[str]) -> str | None:
    for cell in cells:
        match = LEADING_TARGET_ID_RE.search(cell)
        if match:
            return match.group(1)
    return None


def target_ids_in_reference_tables(path: Path) -> set[str]:
    document = Document(path)
    target_ids: set[str] = set()
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip().replace("\xa0", " ") for cell in row.cells]
            if not cells or cells[0].lower().startswith("theme"):
                continue
            target_id = target_id_for_cells(cells)
            if target_id:
                target_ids.add(target_id)
    return target_ids


def target_id_for_row(row: dict[str, Any]) -> str | None:
    preferred_keys = (
        "Recommendation and recommending State",
        "Recommendation",
        "recommendation",
        "target_recommendation",
    )
    for key in preferred_keys:
        value = row.get(key)
        if isinstance(value, str):
            match = LEADING_TARGET_ID_RE.search(value)
            if match:
                return match.group(1)
    for value in row.values():
        if isinstance(value, str):
            match = LEADING_TARGET_ID_RE.search(value)
            if match:
                return match.group(1)
    return None


def pct(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(case["source_pdf"])
    reference_path = Path(case["reference_doc"])
    record: dict[str, Any] = {
        "case_id": case["case_id"],
        "country": case["country"],
        "cycle_year": case["cycle_year"],
        "detected_source_language": case.get("detected_source_language", "unknown"),
        "detected_reference_language": case.get("detected_reference_language", "unknown"),
        "reference_extension": reference_path.suffix.lower(),
        "source_pdf": str(source_path),
        "reference_doc": str(reference_path),
        "source_exists": source_path.exists(),
        "reference_exists": reference_path.exists(),
        "source_text_status": "not_run",
        "reference_text_status": "not_run",
        "reference_row_status": "not_run",
    }

    try:
        source_text = read_text_file(source_path)
        record["source_text_status"] = "ok"
        record["source_text_chars"] = len(source_text)
        record["source_text_nonempty"] = bool(source_text.strip())
    except Exception as exc:
        record["source_text_status"] = "error"
        record["source_text_error"] = f"{type(exc).__name__}: {exc}"
        record["source_text_chars"] = 0
        record["source_text_nonempty"] = False

    try:
        reference_text = read_text_file(reference_path)
        reference_text_ids = target_ids_in_reference_tables(reference_path)
        record["reference_text_status"] = "ok"
        record["reference_text_chars"] = len(reference_text)
        record["reference_text_nonempty"] = bool(reference_text.strip())
        record["reference_text_target_ids"] = len(reference_text_ids)
    except Exception as exc:
        reference_text_ids = set()
        record["reference_text_status"] = "error"
        record["reference_text_error"] = f"{type(exc).__name__}: {exc}"
        record["reference_text_chars"] = 0
        record["reference_text_nonempty"] = False
        record["reference_text_target_ids"] = 0

    try:
        rows = extract_un_recommendation_rows(reference_path)
        parsed_ids = [target_id_for_row(row) for row in rows]
        parsed_id_set = {target_id for target_id in parsed_ids if target_id}
        record["reference_row_status"] = "ok"
        record["reference_rows"] = len(rows)
        record["reference_rows_with_target_id"] = sum(1 for target_id in parsed_ids if target_id)
        record["reference_row_target_ids"] = len(parsed_id_set)
        record["reference_text_ids_in_rows"] = len(reference_text_ids & parsed_id_set)
        record["reference_text_id_row_coverage"] = pct(len(reference_text_ids & parsed_id_set), len(reference_text_ids))
        duplicate_ids = {
            target_id: count for target_id, count in Counter(target_id for target_id in parsed_ids if target_id).items() if count > 1
        }
        record["duplicate_target_ids"] = duplicate_ids
    except Exception as exc:
        record["reference_row_status"] = "error"
        record["reference_row_error"] = f"{type(exc).__name__}: {exc}"
        record["reference_rows"] = 0
        record["reference_rows_with_target_id"] = 0
        record["reference_row_target_ids"] = 0
        record["reference_text_ids_in_rows"] = 0
        record["reference_text_id_row_coverage"] = 0.0
        record["duplicate_target_ids"] = {}

    return record


def summarize(records: list[dict[str, Any]]) -> list[str]:
    total = len(records)
    source_ok = sum(1 for row in records if row["source_text_status"] == "ok" and row["source_text_nonempty"])
    ref_text_ok = sum(1 for row in records if row["reference_text_status"] == "ok" and row["reference_text_nonempty"])
    ref_rows_ok = sum(1 for row in records if row["reference_row_status"] == "ok" and row["reference_rows"] > 0)
    by_ext = Counter(row["reference_extension"] for row in records)
    by_lang = Counter(row["detected_source_language"] for row in records)
    row_ok_by_ext: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        row_ok_by_ext[row["reference_extension"]].append(row)

    docx_records = [row for row in records if row["reference_extension"] == ".docx"]
    row_counts = [row["reference_rows"] for row in docx_records if row["reference_row_status"] == "ok"]
    id_coverages = [
        row["reference_text_id_row_coverage"]
        for row in docx_records
        if row["reference_text_status"] == "ok" and row["reference_text_target_ids"] > 0
    ]

    lines = [
        "# UPR Materials Extraction Comparison",
        "",
        f"Manifest: `{MANIFEST.relative_to(REPO_ROOT)}`",
        "",
        "This compares deterministic extraction only. These 55 cases have no direct match labels, so this is a robustness and coverage report, not an accuracy report.",
        "",
        "Recommendation ID coverage uses the first leading UPR recommendation ID in each raw table row, which avoids counting theme taxonomy codes like `14.5` as target recommendations.",
        "",
        "## Summary",
        "",
        f"- Document pairs: {total}",
        f"- Source PDF text extraction non-empty: {source_ok}/{total} ({pct(source_ok, total)})",
        f"- Reference text extraction non-empty: {ref_text_ok}/{total} ({pct(ref_text_ok, total)})",
        f"- Reference row extraction non-empty: {ref_rows_ok}/{total} ({pct(ref_rows_ok, total)})",
        f"- Reference formats: {', '.join(f'{key}={value}' for key, value in sorted(by_ext.items()))}",
        f"- Detected source languages: {', '.join(f'{key}={value}' for key, value in sorted(by_lang.items()))}",
    ]
    if row_counts:
        lines.extend(
            [
                f"- DOCX row count median: {statistics.median(row_counts)}",
                f"- DOCX row count min/max: {min(row_counts)}/{max(row_counts)}",
            ]
        )
    if id_coverages:
        lines.append(f"- DOCX median raw-text-ID to parsed-row-ID coverage: {statistics.median(id_coverages)}")

    lines.extend(["", "## By Reference Format", ""])
    lines.append("| Format | Cases | Text OK | Rows OK | Median rows | Median ID coverage |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for ext, rows in sorted(row_ok_by_ext.items()):
        text_ok = sum(1 for row in rows if row["reference_text_status"] == "ok" and row["reference_text_nonempty"])
        rows_ok = sum(1 for row in rows if row["reference_row_status"] == "ok" and row["reference_rows"] > 0)
        ext_row_counts = [row["reference_rows"] for row in rows if row["reference_row_status"] == "ok"]
        ext_coverages = [
            row["reference_text_id_row_coverage"]
            for row in rows
            if row["reference_text_status"] == "ok" and row["reference_text_target_ids"] > 0
        ]
        lines.append(
            f"| `{ext}` | {len(rows)} | {text_ok} | {rows_ok} | "
            f"{statistics.median(ext_row_counts) if ext_row_counts else 'n/a'} | "
            f"{statistics.median(ext_coverages) if ext_coverages else 'n/a'} |"
        )

    lines.extend(["", "## By Source Language", ""])
    lines.append("| Source language | Cases | Source text OK | Reference rows OK | Median rows |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for language, count in sorted(by_lang.items()):
        rows = [row for row in records if row["detected_source_language"] == language]
        source_ok_lang = sum(1 for row in rows if row["source_text_status"] == "ok" and row["source_text_nonempty"])
        rows_ok_lang = sum(1 for row in rows if row["reference_row_status"] == "ok" and row["reference_rows"] > 0)
        counts = [row["reference_rows"] for row in rows if row["reference_row_status"] == "ok"]
        lines.append(
            f"| `{language}` | {count} | {source_ok_lang} | {rows_ok_lang} | "
            f"{statistics.median(counts) if counts else 'n/a'} |"
        )

    failures = [
        row
        for row in records
        if row["source_text_status"] != "ok"
        or row["reference_text_status"] != "ok"
        or row["reference_row_status"] != "ok"
        or not row["source_text_nonempty"]
        or (row["reference_extension"] == ".docx" and row["reference_rows"] == 0)
    ]
    lines.extend(["", "## Extraction Failures", ""])
    if failures:
        lines.append("| case_id | format | source status | reference text status | row status | error |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in failures:
            error = row.get("source_text_error") or row.get("reference_text_error") or row.get("reference_row_error") or ""
            lines.append(
                f"| `{row['case_id']}` | `{row['reference_extension']}` | "
                f"{row['source_text_status']} | {row['reference_text_status']} | {row['reference_row_status']} | "
                f"{str(error).replace('|', '/')[:240]} |"
            )
    else:
        lines.append("None.")

    outliers = sorted(
        [row for row in records if row["reference_row_status"] == "ok" and row["reference_rows"] > 0],
        key=lambda row: row["reference_rows"],
    )
    lines.extend(["", "## Row Count Outliers", ""])
    lines.append("| case_id | language | format | rows | text target IDs | row target IDs | ID coverage |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: |")
    for row in outliers[:5] + outliers[-5:]:
        lines.append(
            f"| `{row['case_id']}` | `{row['detected_source_language']}` | `{row['reference_extension']}` | "
            f"{row['reference_rows']} | {row['reference_text_target_ids']} | "
            f"{row['reference_row_target_ids']} | {row['reference_text_id_row_coverage']} |"
        )

    low_coverage = [
        row
        for row in docx_records
        if row["reference_text_target_ids"] > 0 and row["reference_text_id_row_coverage"] < 0.98
    ]
    lines.extend(["", "## Low DOCX ID Coverage", ""])
    if low_coverage:
        lines.append("| case_id | rows | text target IDs | row target IDs | coverage |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for row in sorted(low_coverage, key=lambda item: item["reference_text_id_row_coverage"])[:20]:
            lines.append(
                f"| `{row['case_id']}` | {row['reference_rows']} | {row['reference_text_target_ids']} | "
                f"{row['reference_row_target_ids']} | {row['reference_text_id_row_coverage']} |"
            )
    else:
        lines.append("None below 0.98 coverage among DOCX cases with target IDs.")

    lines.extend(["", "## Outputs", "", f"- JSONL details: `{OUT_JSONL.relative_to(REPO_ROOT)}`"])
    return lines


def main() -> None:
    cases = read_jsonl(MANIFEST)
    records = [evaluate_case(case) for case in cases]
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    OUT_MD.write_text("\n".join(summarize(records)) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} records to {OUT_JSONL}")
    print(f"wrote report to {OUT_MD}")


if __name__ == "__main__":
    main()
