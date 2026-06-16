from __future__ import annotations

import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VALIDATION_ROOT = (
    REPO_ROOT.parent / "un-recommendations" / "data" / "fmsi-poc-data" / "validation"
)
VALIDATION_ROOT = Path(os.environ.get("UPR_VALIDATION_ROOT", DEFAULT_VALIDATION_ROOT)).resolve()

CASE_ID = "costa_rica_2024"
SOURCE_FILE = "2024_UPR Costa Rica.pdf"
REFERENCE_FILE = "Matrix of recommendations_CostaRica_2024.docx"
SPANISH_WORKBOOK = "Tabla de Recomendaciones_Costa Rica.xlsx"
ENGLISH_WORKBOOK = "Tabla de Recomendaciones_Costa Rica_ENG.xlsx"

THEMES = [
    ("right_to_education", "RIGHT TO EDUCATION"),
    ("violence_against_children", "VIOLENCE AGAINST CHILDREN"),
    ("right_to_health", "RIGHT TO HEALTH"),
    ("young_peoples_rights", "YOUNG PEOPLE'S RIGHTS"),
    ("discrimination", "DISCRIMINATION"),
    ("sexual_exploitation_and_trafficking", "SEXUAL EXPLOITATION AND TRAFFICKING"),
    ("transport_and_infrastructure", "TRANSPORT AND INFRASTRUCTURE"),
]

XLS_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


def main() -> None:
    output_root = REPO_ROOT / "evals"
    gold_dir = output_root / "gold"
    datasets_dir = output_root / "datasets"
    reports_dir = output_root / "reports"
    for directory in (gold_dir, datasets_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    english = parse_validation_workbook(VALIDATION_ROOT / ENGLISH_WORKBOOK, language="en")
    spanish = parse_validation_workbook(VALIDATION_ROOT / SPANISH_WORKBOOK, language="es")
    source_records = merge_sources(english["sources"], spanish["sources"])
    match_links = merge_links(english["links"], spanish["links"], source_records)

    write_jsonl(gold_dir / f"{CASE_ID}_source_recommendations.jsonl", source_records)
    write_jsonl(gold_dir / f"{CASE_ID}_match_links.jsonl", match_links)
    write_document_pairs(datasets_dir / "document_pairs.yaml")
    write_report(reports_dir / "validation_inventory.md", source_records, match_links)

    similar = sum(1 for link in match_links if link["relevance"] == "similar")
    very_similar = sum(1 for link in match_links if link["relevance"] == "very_similar")
    print(
        f"Wrote {len(source_records)} source recommendations and "
        f"{len(match_links)} match links ({similar} similar, {very_similar} very_similar)."
    )


def parse_validation_workbook(path: Path, *, language: str) -> dict[str, list[dict[str, object]]]:
    sheets = [sheet for sheet in read_xlsx(path) if not sheet["name"].lower().startswith("relevant")]
    if len(sheets) != len(THEMES):
        raise ValueError(f"Expected {len(THEMES)} sheets in {path.name}, got {len(sheets)}")

    sources: list[dict[str, object]] = []
    links: list[dict[str, object]] = []
    for sheet_index, sheet in enumerate(sheets):
        theme_slug, theme = THEMES[sheet_index]
        current_source: dict[str, object] | None = None
        for row in sheet["rows"]:
            source_cell = row[0] if len(row) > 0 else ""
            similar_cell = row[1] if len(row) > 1 else ""
            very_similar_cell = row[2] if len(row) > 2 else ""

            parsed_source = parse_source_recommendation(source_cell)
            if parsed_source:
                source_number, source_text = parsed_source
                source_id = f"{CASE_ID}:{theme_slug}:{source_number}"
                current_source = {
                    "case_id": CASE_ID,
                    "source_id": source_id,
                    "source_number": source_number,
                    "theme": theme,
                    "theme_slug": theme_slug,
                    f"source_recommendation_{language}": source_text,
                    "source_file": str(VALIDATION_ROOT / SOURCE_FILE),
                    "validation_workbook": str(path),
                }
                sources.append(current_source)

            if current_source is None:
                continue

            for relevance, target_text in (
                ("similar", similar_cell),
                ("very_similar", very_similar_cell),
            ):
                if not is_target_label(target_text):
                    continue
                target_id = parse_target_recommendation_id(target_text)
                links.append(
                    {
                        "case_id": CASE_ID,
                        "source_id": current_source["source_id"],
                        "source_number": current_source["source_number"],
                        "theme": theme,
                        "theme_slug": theme_slug,
                        "relevance": relevance,
                        "relevance_score": 1 if relevance == "similar" else 2,
                        "target_recommendation_id": target_id,
                        f"target_recommendation_{language}": target_text,
                        "reference_file": str(VALIDATION_ROOT / REFERENCE_FILE),
                        "validation_workbook": str(path),
                    }
                )

    return {"sources": sources, "links": links}


def merge_sources(
    english_sources: list[dict[str, object]],
    spanish_sources: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for source in english_sources + spanish_sources:
        source_id = str(source["source_id"])
        merged.setdefault(
            source_id,
            {
                "case_id": CASE_ID,
                "source_id": source_id,
                "source_number": source["source_number"],
                "theme": source["theme"],
                "theme_slug": source["theme_slug"],
                "source_file": str(VALIDATION_ROOT / SOURCE_FILE),
                "validation_workbooks": [
                    str(VALIDATION_ROOT / ENGLISH_WORKBOOK),
                    str(VALIDATION_ROOT / SPANISH_WORKBOOK),
                ],
                "source_languages": ["es", "en"],
                "primary_source_language": "es",
            },
        )
        merged[source_id].update(
            {key: value for key, value in source.items() if key.startswith("source_recommendation_")}
        )

    return [merged[key] for key in sorted(merged, key=source_sort_key)]


def merge_links(
    english_links: list[dict[str, object]],
    spanish_links: list[dict[str, object]],
    source_records: list[dict[str, object]],
) -> list[dict[str, object]]:
    sources_by_id = {str(source["source_id"]): source for source in source_records}
    merged: dict[tuple[str, str, str], dict[str, object]] = {}

    for link in english_links + spanish_links:
        target_id = link.get("target_recommendation_id")
        target_key = str(target_id) if target_id else stable_hash(
            str(link.get("target_recommendation_en") or link.get("target_recommendation_es"))
        )
        key = (str(link["source_id"]), str(link["relevance"]), target_key)
        record = merged.setdefault(
            key,
            {
                "case_id": CASE_ID,
                "match_label_id": f"{key[0]}:{key[1]}:{target_key}",
                "source_id": link["source_id"],
                "source_number": link["source_number"],
                "theme": link["theme"],
                "theme_slug": link["theme_slug"],
                "relevance": link["relevance"],
                "relevance_score": link["relevance_score"],
                "target_recommendation_id": target_id,
                "source_file": str(VALIDATION_ROOT / SOURCE_FILE),
                "reference_file": str(VALIDATION_ROOT / REFERENCE_FILE),
                "validation_workbooks": [
                    str(VALIDATION_ROOT / ENGLISH_WORKBOOK),
                    str(VALIDATION_ROOT / SPANISH_WORKBOOK),
                ],
                "source_languages": ["es", "en"],
                "target_label_languages": ["en", "es"],
                "primary_pipeline_language_pair": "es-en",
            },
        )
        record.update({k: v for k, v in link.items() if k.startswith("target_recommendation_")})

    for record in merged.values():
        source = sources_by_id[str(record["source_id"])]
        for key, value in source.items():
            if key.startswith("source_recommendation_"):
                record[key] = value

    return [merged[key] for key in sorted(merged, key=link_sort_key)]


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


def parse_source_recommendation(value: str) -> tuple[int, str] | None:
    match = re.match(r"^\s*(\d+)\.\s*(.+)$", value)
    if not match:
        return None
    return int(match.group(1)), normalize_text(match.group(2))


def parse_target_recommendation_id(value: str) -> str | None:
    match = re.match(r"^\s*(\d{2,3}\.\d+)\b", value)
    return match.group(1) if match else None


def is_target_label(value: str) -> bool:
    if not value:
        return False
    lowered = value.lower()
    if "similar recommendation" in lowered or "recomendación" in lowered and len(value) < 80:
        return False
    return bool(parse_target_recommendation_id(value))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def source_sort_key(source_id: str) -> tuple[str, int]:
    parts = source_id.split(":")
    return parts[1], int(parts[2])


def link_sort_key(key: tuple[str, str, str]) -> tuple[str, int, int, str]:
    source_id, relevance, target_key = key
    _, theme_slug, source_number = source_id.split(":")
    return theme_slug, int(source_number), 1 if relevance == "similar" else 2, target_key


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_document_pairs(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "cases:",
                f"  - case_id: {CASE_ID}",
                "    country: Costa Rica",
                "    cycle_year: 2024",
                f"    source_pdf: {VALIDATION_ROOT / SOURCE_FILE}",
                f"    reference_docx: {VALIDATION_ROOT / REFERENCE_FILE}",
                f"    validation_workbook_en: {VALIDATION_ROOT / ENGLISH_WORKBOOK}",
                f"    validation_workbook_es: {VALIDATION_ROOT / SPANISH_WORKBOOK}",
                "    source_languages: [es, en]",
                "    reference_languages: [en]",
                "    label_languages: [en, es]",
                "    primary_pipeline_language_pair: es-en",
                "    notes: Initial normalized validation case from FMSI POC data.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_report(
    path: Path,
    source_records: list[dict[str, object]],
    match_links: list[dict[str, object]],
) -> None:
    similar = sum(1 for link in match_links if link["relevance"] == "similar")
    very_similar = sum(1 for link in match_links if link["relevance"] == "very_similar")
    per_theme: dict[str, dict[str, int]] = {}
    for source in source_records:
        per_theme.setdefault(str(source["theme"]), {"sources": 0, "similar": 0, "very_similar": 0})
        per_theme[str(source["theme"])]["sources"] += 1
    for link in match_links:
        counts = per_theme.setdefault(str(link["theme"]), {"sources": 0, "similar": 0, "very_similar": 0})
        counts[str(link["relevance"])] += 1

    lines = [
        "# Validation Inventory",
        "",
        "## Costa Rica 2024",
        "",
        f"- Source recommendations: {len(source_records)}",
        f"- Match labels: {len(match_links)}",
        f"- Similar labels: {similar}",
        f"- Very similar labels: {very_similar}",
        "",
        "| Theme | Source recommendations | Similar labels | Very similar labels |",
        "| --- | ---: | ---: | ---: |",
    ]
    for theme, counts in per_theme.items():
        lines.append(
            f"| {theme} | {counts['sources']} | {counts['similar']} | {counts['very_similar']} |"
        )
    lines.extend(
        [
            "",
            "Generated from:",
            "",
            f"- `{VALIDATION_ROOT / ENGLISH_WORKBOOK}`",
            f"- `{VALIDATION_ROOT / SPANISH_WORKBOOK}`",
            "",
            "Notes:",
            "",
            "- The source PDF is Spanish. The English workbook appears to contain translated source recommendations.",
            "- Keep both Spanish and English labels. They let us compare cross-lingual matching (`es-en`) against translated-source controls (`en-en`).",
            "- Match labels are anchored on UPR recommendation IDs when present.",
            "- Bangladesh and Papua New Guinea validation workbooks still need manual interpretation before normalization.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
