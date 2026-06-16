#!/usr/bin/env python3
"""Inventory unlabeled UPR materials for eval/regression coverage."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MATERIALS_ROOT = Path(
    "/home/arthur/Documents/gail/"
    "UPR Materials - TheGoodAILab-20260615T015654Z-3-001/"
    "UPR Materials - TheGoodAILab"
)
OUT_JSONL = REPO_ROOT / "evals/datasets/upr_materials_document_pairs.jsonl"
OUT_REPORT = REPO_ROOT / "evals/reports/upr_materials_inventory.md"
PDF_SAMPLE_PAGES = 5
PDF_SAMPLE_TIMEOUT_SECONDS = 20
TEXT_SAMPLE_LIMIT = 60000
LANGUAGE_METHOD = "text_sample_stopword_heuristic_v1"


ALIASES = {
    "Costa Rica": "CostaRica",
    "Ivory Coast": "IvoryCoast",
    "Italia": "Italy",
    "Spagna": "Spain",
    "Philiphines": "Philippines",
    "PNG": "PapuaNewGuinea",
    "Timor Est": "TimorLeste",
    "TimoreLeste": "TimorLeste",
    "Solomon Islands": "SolomonIslands",
}

DISPLAY_NAMES = {
    "CentralAfricanRepublic": "Central African Republic",
    "CostaRica": "Costa Rica",
    "DRC": "DRC",
    "ElSalvador": "El Salvador",
    "IvoryCoast": "Ivory Coast",
    "PapuaNewGuinea": "Papua New Guinea",
    "SouthAfrica": "South Africa",
    "SolomonIslands": "Solomon Islands",
    "SriLanka": "Sri Lanka",
    "TimorLeste": "Timor Leste",
    "USA": "USA",
}

ROLE_ORDER = [
    "source_pdf",
    "reference_doc",
    "stakeholder_file",
    "working_group_report_pdf",
    "addendum_pdf",
]

LANGUAGE_MARKERS = {
    "en": {
        "the",
        "and",
        "shall",
        "with",
        "rights",
        "children",
        "women",
        "recommendations",
        "government",
        "state",
        "ensure",
        "protect",
        "promote",
        "implementation",
        "national",
    },
    "es": {
        "los",
        "las",
        "del",
        "una",
        "para",
        "derechos",
        "ninos",
        "ninas",
        "mujeres",
        "recomendaciones",
        "gobierno",
        "estado",
        "garantizar",
        "proteger",
        "promover",
        "aplicacion",
        "nacional",
    },
    "fr": {
        "aux",
        "avec",
        "droits",
        "enfants",
        "femmes",
        "recommandations",
        "gouvernement",
        "etat",
        "garantir",
        "proteger",
        "promouvoir",
        "mise",
        "nationale",
    },
    "it": {
        "degli",
        "delle",
        "diritti",
        "donne",
        "bambini",
        "raccomandazioni",
        "governo",
        "stato",
        "garantire",
        "proteggere",
        "promuovere",
        "attuazione",
        "nazionale",
    },
    "pt": {
        "dos",
        "das",
        "direitos",
        "criancas",
        "mulheres",
        "recomendacoes",
        "governo",
        "estado",
        "assegurar",
        "proteger",
        "promover",
        "implementacao",
        "nacional",
    },
}


def compact_country(raw: str, year: str | None = None) -> str:
    cleaned = raw.strip()
    if year:
        cleaned = re.sub(rf"[_ ]{re.escape(year)}$", "", cleaned)
    cleaned = ALIASES.get(cleaned, cleaned)
    return cleaned.replace(" ", "").replace("_", "")


def display_country(compact: str) -> str:
    if compact in DISPLAY_NAMES:
        return DISPLAY_NAMES[compact]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", compact)


def slugify_country(compact: str) -> str:
    display = display_country(compact).lower()
    return re.sub(r"[^a-z0-9]+", "_", display).strip("_")


def parse_file(path: Path) -> tuple[str, str, str] | None:
    stem = path.stem
    suffix = path.suffix.lower()

    match = re.match(r"^(?P<year>\d{4})_UPR (?P<country>.+)$", stem)
    if match and suffix == ".pdf":
        year = match.group("year")
        return "source_pdf", compact_country(match.group("country"), year), year

    match = re.match(
        r"^Matrix (?:of|or) recommendations_(?P<country>.+)_(?P<year>\d{4})$",
        stem,
        flags=re.IGNORECASE,
    )
    if match and suffix in {".doc", ".docx"}:
        return "reference_doc", compact_country(match.group("country")), match.group("year")

    match = re.match(
        r"^Summary of (?:the )?Stakeholders?_(?P<country>.+)_(?P<year>\d{4})$",
        stem,
        flags=re.IGNORECASE,
    )
    if match and suffix in {".doc", ".docx", ".pdf"}:
        return "stakeholder_file", compact_country(match.group("country")), match.group("year")

    match = re.match(
        r"^Report of the Working Group_(?P<country>.+)_(?P<year>\d{4})$",
        stem,
        flags=re.IGNORECASE,
    )
    if match and suffix == ".pdf":
        return "working_group_report_pdf", compact_country(match.group("country")), match.group("year")

    match = re.match(
        r"^Addendum_(?P<country>.+)_(?P<year>\d{4})$",
        stem,
        flags=re.IGNORECASE,
    )
    if match and suffix == ".pdf":
        return "addendum_pdf", compact_country(match.group("country")), match.group("year")

    return None


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def detect_language(text: str) -> tuple[str, float, int]:
    normalized = strip_accents(text).lower()
    tokens = re.findall(r"[a-z]+", normalized)
    if not tokens:
        return "unknown", 0.0, 0

    token_counts = Counter(tokens)
    scores = {
        language: sum(token_counts[token] for token in markers)
        for language, markers in LANGUAGE_MARKERS.items()
    }
    best_language, best_score = max(scores.items(), key=lambda item: item[1])
    total_score = sum(scores.values())
    if best_score < 8 or total_score == 0:
        return "unknown", 0.0, len(tokens)
    confidence = round(best_score / total_score, 3)
    if confidence < 0.38:
        return "other", confidence, len(tokens)
    return best_language, confidence, len(tokens)


def extract_pdf_text(path: Path) -> str:
    if shutil.which("pdftotext") is None:
        return ""
    try:
        result = subprocess.run(
            [
                "pdftotext",
                "-f",
                "1",
                "-l",
                str(PDF_SAMPLE_PAGES),
                "-q",
                str(path),
                "-",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=PDF_SAMPLE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout[:TEXT_SAMPLE_LIMIT]


def extract_docx_text(path: Path) -> str:
    if path.suffix.lower() != ".docx":
        return ""
    try:
        with zipfile.ZipFile(path) as archive:
            with archive.open("word/document.xml") as handle:
                xml = handle.read().decode("utf-8", errors="ignore")
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml)
    text = " ".join(re.sub(r"<[^>]+>", "", part) for part in parts)
    return text[:TEXT_SAMPLE_LIMIT]


def add_language_hint(record: dict, field: str, text: str) -> None:
    language, confidence, tokens = detect_language(text)
    record[f"detected_{field}_language"] = language
    record[f"detected_{field}_language_confidence"] = confidence
    record[f"detected_{field}_language_method"] = LANGUAGE_METHOD
    record[f"detected_{field}_language_tokens"] = tokens


def annotate_languages(record: dict) -> None:
    source_path = record.get("source_pdf")
    if isinstance(source_path, str):
        add_language_hint(record, "source", extract_pdf_text(Path(source_path)))

    reference_path = record.get("reference_doc")
    if isinstance(reference_path, str):
        path = Path(reference_path)
        if path.suffix.lower() == ".docx":
            add_language_hint(record, "reference", extract_docx_text(path))
        else:
            record["detected_reference_language"] = "unknown"
            record["detected_reference_language_confidence"] = 0.0
            record["detected_reference_language_method"] = "legacy_doc_not_sampled"
            record["detected_reference_language_tokens"] = 0


def one_or_many(paths: list[Path]) -> str | list[str] | None:
    if not paths:
        return None
    values = [str(path) for path in sorted(paths)]
    return values[0] if len(values) == 1 else values


def build_inventory() -> tuple[list[dict], list[dict], list[Path], Counter]:
    cases: dict[tuple[str, str], dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))
    unknown: list[Path] = []
    suffix_counts: Counter = Counter()

    files = sorted(path for path in MATERIALS_ROOT.rglob("*") if path.is_file())
    for path in files:
        suffix_counts[path.suffix.lower() or "<none>"] += 1
        parsed = parse_file(path)
        if parsed is None:
            unknown.append(path)
            continue
        role, country, year = parsed
        cases[(country, year)][role].append(path)

    all_cases = []
    pair_cases = []
    for (country, year), roles in sorted(cases.items(), key=lambda item: (item[0][0], item[0][1])):
        case_id = f"{slugify_country(country)}_{year}"
        record = {
            "case_id": case_id,
            "country": display_country(country),
            "country_key": country,
            "cycle_year": int(year),
            "label_kind": "unlabeled_documents",
            "source_languages": ["unknown"],
            "reference_languages": ["unknown"],
            "notes": "Raw UPR materials only; no human match labels found in this folder.",
        }
        for role in ROLE_ORDER:
            value = one_or_many(roles.get(role, []))
            if value:
                record[role] = value
        annotate_languages(record)

        all_cases.append(record)
        if roles.get("source_pdf") and roles.get("reference_doc"):
            pair_cases.append(record)

    return all_cases, pair_cases, unknown, suffix_counts


def write_jsonl(records: list[dict]) -> None:
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def role_counts(records: list[dict]) -> Counter:
    counts = Counter()
    for record in records:
        for role in ROLE_ORDER:
            if role in record:
                counts[role] += 1
    return counts


def language_counts(records: list[dict], field: str) -> Counter:
    return Counter(record.get(f"detected_{field}_language", "not_sampled") for record in records)


def format_counter(counter: Counter) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={count}" for key, count in sorted(counter.items()))


def markdown_table(records: list[dict]) -> list[str]:
    lines = [
        "| case_id | country | year | src_lang | ref_lang | source | matrix | stakeholder | report | addendum |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| {case_id} | {country} | {year} | {src_lang} | {ref_lang} | {source} | {matrix} | {stakeholder} | {report} | {addendum} |".format(
                case_id=record["case_id"],
                country=record["country"],
                year=record["cycle_year"],
                src_lang=record.get("detected_source_language", ""),
                ref_lang=record.get("detected_reference_language", ""),
                source="yes" if "source_pdf" in record else "",
                matrix="yes" if "reference_doc" in record else "",
                stakeholder="yes" if "stakeholder_file" in record else "",
                report="yes" if "working_group_report_pdf" in record else "",
                addendum="yes" if "addendum_pdf" in record else "",
            )
        )
    return lines


def write_report(all_cases: list[dict], pair_cases: list[dict], unknown: list[Path], suffix_counts: Counter) -> None:
    counts = role_counts(all_cases)
    complete_context = [
        record
        for record in pair_cases
        if "stakeholder_file" in record and "working_group_report_pdf" in record
    ]
    doc_pairs = Counter(
        Path(record["reference_doc"]).suffix.lower()
        for record in pair_cases
        if isinstance(record.get("reference_doc"), str)
    )
    source_languages = language_counts(pair_cases, "source")
    reference_languages = language_counts(pair_cases, "reference")

    lines = [
        "# UPR Materials Inventory",
        "",
        f"Source folder: `{MATERIALS_ROOT}`",
        "",
        "This folder contains raw UPR materials, not validation workbooks. Treat these cases as unlabeled regression/eval coverage unless a separate human-labeled sheet is added.",
        "",
        "Language fields in this report are heuristic hints from sampled text, not human labels.",
        "",
        "## Summary",
        "",
        f"- Total files: {sum(suffix_counts.values())}",
        f"- File types: {format_counter(suffix_counts)}",
        f"- Parsed cases: {len(all_cases)}",
        f"- Source + recommendation-matrix pairs: {len(pair_cases)}",
        f"- Pairs with stakeholder summary and working-group report: {len(complete_context)}",
        f"- Matrix formats among pairs: {format_counter(doc_pairs)}",
        f"- Detected source languages among pairs: {format_counter(source_languages)}",
        f"- Detected reference languages among pairs: {format_counter(reference_languages)}",
        "",
        "## Parsed Role Counts",
        "",
    ]
    lines.extend(f"- `{role}`: {counts.get(role, 0)}" for role in ROLE_ORDER)
    lines.extend(
        [
            "",
            "## Unlabeled Document Pairs",
            "",
            f"JSONL manifest: `{OUT_JSONL.relative_to(REPO_ROOT)}`",
            "",
            *markdown_table(pair_cases),
            "",
            "## Parsed Cases Without A Source+Matrix Pair",
            "",
        ]
    )
    partial_cases = [record for record in all_cases if record not in pair_cases]
    if partial_cases:
        lines.extend(markdown_table(partial_cases))
    else:
        lines.append("None.")

    lines.extend(["", "## Unparsed Files", ""])
    if unknown:
        lines.extend(f"- `{path}`" for path in unknown)
    else:
        lines.append("None.")

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not MATERIALS_ROOT.exists():
        raise SystemExit(f"Missing materials folder: {MATERIALS_ROOT}")
    all_cases, pair_cases, unknown, suffix_counts = build_inventory()
    write_jsonl(pair_cases)
    write_report(all_cases, pair_cases, unknown, suffix_counts)
    print(f"wrote {len(pair_cases)} unlabeled pairs to {OUT_JSONL}")
    print(f"wrote inventory report to {OUT_REPORT}")
    if unknown:
        print(f"unparsed files: {len(unknown)}")


if __name__ == "__main__":
    main()
