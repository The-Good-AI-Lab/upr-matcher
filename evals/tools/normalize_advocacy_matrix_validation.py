from __future__ import annotations

import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VALIDATION_ROOT = (
    REPO_ROOT.parent / "un-recommendations" / "data" / "fmsi-poc-data" / "validation"
)
VALIDATION_ROOT = Path(os.environ.get("UPR_VALIDATION_ROOT", DEFAULT_VALIDATION_ROOT)).resolve()

XLS_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


@dataclass(frozen=True)
class MatrixConfig:
    case_id: str
    country: str
    cycle_year: int
    workbook: str
    source_pdf: str
    stakeholder_pdf: str
    reference_doc: str
    current_cycle_column: int
    impact_column: int
    current_cycle_label: str
    source_language: str = "en"
    reference_language: str = "en"
    label_language: str = "en"


CONFIGS = [
    MatrixConfig(
        case_id="bangladesh_2023",
        country="Bangladesh",
        cycle_year=2023,
        workbook="UPR Advocacy Evaluation Bangladesh.xlsx",
        source_pdf="2023_UPR Bangladesh.pdf",
        stakeholder_pdf="Summary of the stakeholders_Bangladesh_2023.pdf",
        reference_doc="Matrix of recommendations_Bangladesh_2023.doc",
        current_cycle_column=12,  # M
        impact_column=13,  # N
        current_cycle_label="4th cycle",
    ),
    MatrixConfig(
        case_id="papua_new_guinea_2021",
        country="Papua New Guinea",
        cycle_year=2021,
        workbook="1. Advocacy Plan _ Evaluation table UPR PNG.xlsx",
        source_pdf="2021_UPR PapuaNewGuinea.pdf",
        stakeholder_pdf="Summary of the stakeholders_PapuaNewGuinea_2021.pdf",
        reference_doc="Matrix of recommendations_PapuaNewGuinea_2021.docx",
        current_cycle_column=11,  # L
        impact_column=12,  # M
        current_cycle_label="3rd cycle",
    ),
]


def main() -> None:
    output_root = REPO_ROOT / "evals"
    gold_dir = output_root / "gold"
    datasets_dir = output_root / "datasets"
    reports_dir = output_root / "reports"
    for directory in (gold_dir, datasets_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    all_sources: dict[str, list[dict[str, object]]] = {}
    all_links: dict[str, list[dict[str, object]]] = {}
    for config in CONFIGS:
        sources, links = normalize_case(config)
        all_sources[config.case_id] = sources
        all_links[config.case_id] = links
        write_jsonl(gold_dir / f"{config.case_id}_source_blocks.jsonl", sources)
        write_jsonl(gold_dir / f"{config.case_id}_impact_links.jsonl", links)
        print(
            f"{config.case_id}: wrote {len(sources)} source blocks and "
            f"{len(links)} current-cycle impact links."
        )

    upsert_document_pairs(datasets_dir / "document_pairs.yaml", CONFIGS)
    update_inventory(reports_dir / "validation_inventory.md", all_sources, all_links)


def normalize_case(config: MatrixConfig) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    workbook_path = VALIDATION_ROOT / config.workbook
    sheets = [sheet for sheet in read_xlsx(workbook_path) if not sheet["name"].lower().startswith("relevant")]

    source_blocks: list[dict[str, object]] = []
    impact_links_by_key: dict[tuple[str, str, str], dict[str, object]] = {}

    for sheet in sheets:
        theme = str(sheet["name"])
        theme_slug = slugify(theme)
        source_block = extract_source_block(sheet["rows"])
        source_block_id = f"{config.case_id}:{theme_slug}:source_block"
        source_blocks.append(
            {
                "case_id": config.case_id,
                "source_block_id": source_block_id,
                "theme": theme,
                "theme_slug": theme_slug,
                "source_recommendation_block": source_block,
                "proposed_recommendations": split_proposed_recommendations(source_block),
                "source_file": config.source_pdf,
                "stakeholder_file": config.stakeholder_pdf,
                "validation_workbook": workbook_path.name,
                "source_language": config.source_language,
                "label_granularity": "theme_block",
            }
        )

        for row_index, row in enumerate(sheet["rows"], start=1):
            impact = parse_impact(row[config.impact_column] if len(row) > config.impact_column else "")
            target_cell = row[config.current_cycle_column] if len(row) > config.current_cycle_column else ""
            if impact is None or not is_current_cycle_target(target_cell):
                continue

            state = row[2] if len(row) > 2 else ""
            for target_id, target_text in split_target_recommendations(target_cell):
                target_key = target_id or stable_hash(target_text)
                key = (source_block_id, str(impact), target_key)
                impact_links_by_key[key] = {
                    "case_id": config.case_id,
                    "impact_label_id": f"{source_block_id}:impact_{impact:g}:{target_key}",
                    "source_block_id": source_block_id,
                    "theme": theme,
                    "theme_slug": theme_slug,
                    "state": state,
                    "impact_score": impact,
                    "impact_label": impact_label(impact),
                    "target_recommendation_id": target_id,
                    "target_recommendation": target_text,
                    "target_cell": target_cell,
                    "target_cycle": config.current_cycle_label,
                    "target_column": column_name(config.current_cycle_column),
                    "impact_column": column_name(config.impact_column),
                    "workbook_row": row_index,
                    "source_file": config.source_pdf,
                    "stakeholder_file": config.stakeholder_pdf,
                    "reference_file": config.reference_doc,
                    "validation_workbook": workbook_path.name,
                    "source_language": config.source_language,
                    "reference_language": config.reference_language,
                    "label_language": config.label_language,
                    "language_pair": f"{config.source_language}-{config.reference_language}",
                    "label_kind": "lobbying_impact",
                    "label_granularity": "theme_block_to_current_cycle_recommendation",
                    "eval_use": "weak_positive" if impact > 0 else "weak_negative",
                }

    return source_blocks, [impact_links_by_key[key] for key in sorted(impact_links_by_key)]


def extract_source_block(rows: list[list[str]]) -> str:
    for row in rows:
        if len(row) > 1 and row[1].startswith("-"):
            return row[1]
    return ""


def split_proposed_recommendations(block: str) -> list[str]:
    if not block:
        return []
    parts = re.split(r"\s+-\s*", block)
    cleaned: list[str] = []
    for index, part in enumerate(parts):
        part = part.strip()
        if index == 0:
            part = part.removeprefix("-").strip()
        if part:
            cleaned.append(part)
    return cleaned


def parse_impact(value: str) -> float | None:
    cleaned = normalize_text(value)
    if cleaned in {"0", "0.5", "1"}:
        return float(cleaned)
    return None


def is_current_cycle_target(value: str) -> bool:
    cleaned = normalize_text(value)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in {"did not participate", "recommendations 3rd cycle", "recommendations 4th cycle"}:
        return False
    if lowered.startswith("total:"):
        return False
    return True


def parse_target_recommendation_id(value: str) -> str | None:
    match = re.match(r"^\s*(\d{2,3}\.\d+)\b", value)
    return match.group(1) if match else None


def split_target_recommendations(value: str) -> list[tuple[str | None, str]]:
    cleaned = normalize_text(value)
    matches = list(re.finditer(r"\b(\d{2,3}\.\d+)\.?\b", cleaned))
    if not matches:
        return [(None, cleaned)]

    targets: list[tuple[str | None, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        target_text = cleaned[start:end].strip(" ;")
        if target_text:
            targets.append((match.group(1), target_text))
    return targets


def impact_label(value: float) -> str:
    if value == 1:
        return "direct_lobbying_impact"
    if value == 0.5:
        return "partial_lobbying_impact"
    return "no_lobbying_impact"


def read_xlsx(path: Path) -> list[dict[str, object]]:
    with ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationships.findall("rel:Relationship", REL_NS)
        }

        sheets: list[dict[str, object]] = []
        for sheet in workbook.findall("m:sheets/m:sheet", XLS_NS):
            name = html.unescape(sheet.attrib["name"]).strip()
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rel_id]
            sheet_path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
            root = ET.fromstring(archive.read(sheet_path))
            sheets.append(
                {
                    "name": name,
                    "rows": [read_row(row, shared_strings) for row in root.findall("m:sheetData/m:row", XLS_NS)],
                }
            )
        return sheets


def read_shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        normalize_text("".join(text.text or "" for text in item.findall(".//m:t", XLS_NS)))
        for item in root.findall("m:si", XLS_NS)
    ]


def read_row(row: ET.Element, shared_strings: list[str]) -> list[str]:
    values: list[str] = []
    last_column = 0
    for cell in row.findall("m:c", XLS_NS):
        column = column_number(cell.attrib.get("r", ""))
        while last_column + 1 < column:
            values.append("")
            last_column += 1
        values.append(cell_value(cell, shared_strings))
        last_column = column
    while values and values[-1] == "":
        values.pop()
    return values


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value_type = cell.attrib.get("t")
    value_node = cell.find("m:v", XLS_NS)
    if value_node is None:
        inline = cell.find("m:is", XLS_NS)
        if inline is None:
            return ""
        return normalize_text("".join(text.text or "" for text in inline.findall(".//m:t", XLS_NS)))

    raw = value_node.text or ""
    if value_type == "s" and raw.isdigit():
        index = int(raw)
        if 0 <= index < len(shared_strings):
            return shared_strings[index]
    return normalize_text(raw)


def column_number(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    number = 0
    for char in letters:
        number = number * 26 + (ord(char.upper()) - 64)
    return number


def column_name(index: int) -> str:
    index += 1
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def slugify(value: str) -> str:
    value = html.unescape(value).lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def upsert_document_pairs(path: Path, configs: list[MatrixConfig]) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else "cases:\n"
    lines = [existing.rstrip()]
    for config in configs:
        marker = f"  - case_id: {config.case_id}"
        if marker in existing:
            continue
        lines.extend(
            [
                marker,
                f"    country: {config.country}",
                f"    cycle_year: {config.cycle_year}",
                f"    source_pdf: {config.source_pdf}",
                f"    stakeholder_pdf: {config.stakeholder_pdf}",
                f"    reference_doc: {config.reference_doc}",
                f"    validation_workbook: {config.workbook}",
                f"    source_languages: [{config.source_language}]",
                f"    reference_languages: [{config.reference_language}]",
                f"    label_languages: [{config.label_language}]",
                f"    primary_pipeline_language_pair: {config.source_language}-{config.reference_language}",
                "    label_kind: lobbying_impact",
                "    notes: Extracted from advocacy evaluation matrix; labels are weaker than direct match labels.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_inventory(
    path: Path,
    all_sources: dict[str, list[dict[str, object]]],
    all_links: dict[str, list[dict[str, object]]],
) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Validation Inventory\n"
    sections: list[str] = []
    for config in CONFIGS:
        sources = all_sources[config.case_id]
        links = all_links[config.case_id]
        positive = sum(1 for link in links if float(link["impact_score"]) > 0)
        partial = sum(1 for link in links if link["impact_score"] == 0.5)
        direct = sum(1 for link in links if link["impact_score"] == 1)
        zero = sum(1 for link in links if link["impact_score"] == 0)
        per_theme: dict[str, dict[str, int]] = {}
        for source in sources:
            per_theme.setdefault(str(source["theme"]), {"source_blocks": 0, "links": 0, "positive": 0})
            per_theme[str(source["theme"])]["source_blocks"] += 1
        for link in links:
            counts = per_theme.setdefault(str(link["theme"]), {"source_blocks": 0, "links": 0, "positive": 0})
            counts["links"] += 1
            if float(link["impact_score"]) > 0:
                counts["positive"] += 1

        lines = [
            f"## {config.country} {config.cycle_year}",
            "",
            "- Label kind: `lobbying_impact`",
            "- Label granularity: theme source block -> current-cycle UPR recommendation",
            f"- Source blocks: {len(sources)}",
            f"- Current-cycle impact links: {len(links)}",
            f"- Weak positive links (`impact_score > 0`): {positive}",
            f"- Partial impact links (`0.5`): {partial}",
            f"- Direct impact links (`1`): {direct}",
            f"- Weak negative/no-impact links (`0`): {zero}",
            "",
            "| Theme | Source blocks | Current-cycle links | Weak positive links |",
            "| --- | ---: | ---: | ---: |",
        ]
        for theme, counts in per_theme.items():
            lines.append(f"| {theme} | {counts['source_blocks']} | {counts['links']} | {counts['positive']} |")
        lines.extend(
            [
                "",
                "Notes:",
                "",
                "- These labels are weaker than Costa Rica's direct similar/very-similar labels.",
                "- Use them for impact analysis or coarse retrieval checks, not as exact source-recommendation match labels.",
                "",
            ]
        )
        sections.append("\n".join(lines))

    # Keep the existing Costa Rica section and append/replace matrix sections.
    for config in CONFIGS:
        heading = f"## {config.country} {config.cycle_year}"
        existing = re.sub(rf"\n## {re.escape(config.country)} {config.cycle_year}\n.*?(?=\n## |\Z)", "", existing, flags=re.S)
    path.write_text(existing.rstrip() + "\n\n" + "\n".join(sections) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
