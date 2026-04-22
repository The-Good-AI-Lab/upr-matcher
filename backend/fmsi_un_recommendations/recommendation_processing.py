from __future__ import annotations

import json
import re
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ValidationError

# Support both relative and absolute imports
try:
    from .settings import Settings
    from .utils import (
        chat_with_openrouter,
        docx_tables_to_json,
        read_text_file,
    )
except ImportError:
    # Allow running as a standalone script
    from fmsi_un_recommendations.settings import Settings
    from fmsi_un_recommendations.utils import (
        chat_with_openrouter,
        docx_tables_to_json,
        read_text_file,
    )

settings = Settings()

DEFAULT_PROMPT_PATH = Path("prompts/recommendation_extraction.txt")
DEFAULT_CHUNK_CHAR_LIMIT = 80000


class Recommendation(BaseModel):
    recommendation: str
    domain: str
    beneficiaries: str
    theme: str


class RecommendationBatch(BaseModel):
    recommendations: list[Recommendation]


def extract_un_recommendation_rows(docx_path: str | Path) -> list[dict[str, str]]:
    """Parse the UN DOCX table and return structured rows."""
    path = Path(docx_path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find DOCX file at {path}")
    rows = docx_tables_to_json(path)
    logger.info("Extracted {} UN recommendation rows from DOCX", len(rows))
    return rows


def extract_fmsi_pdf_recommendations(
    pdf_path: str | Path,
    *,
    prompt_path: Path | None = None,
    max_chunk_chars: int = DEFAULT_CHUNK_CHAR_LIMIT,
) -> list[Recommendation]:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find PDF file at {path}")

    document_text = read_text_file(path)
    prompt_file = prompt_path or DEFAULT_PROMPT_PATH

    try:
        prompt_text = prompt_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}") from exc

    if not prompt_text.strip():
        raise ValueError(f"Prompt file {prompt_file} is empty.")

    document_chunks = _chunk_text(document_text, max_chunk_chars)
    logger.info("Extracting FMSI recommendations from PDF: {} chunks", len(document_chunks))

    collected: list[Recommendation] = []
    for index, chunk in enumerate(document_chunks, start=1):
        logger.info("Processing PDF chunk {}/{}", index, len(document_chunks))
        user_prompt = (
            f"Document chunk {index} of {len(document_chunks)}:\n"
            f"{chunk}\n\nReturn only the JSON object specified by the system instructions."
        )
        response = chat_with_openrouter(system_prompt=prompt_text, user_prompt=user_prompt)
        try:
            recommendations = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError("Failed to parse LLM response as JSON") from e

        try:
            batch: RecommendationBatch = [Recommendation.model_validate(item) for item in recommendations]
            logger.info("Chunk {}: extracted {} recommendations", index, len(batch))
        except ValidationError as e:
            raise ValueError("Validation failed") from e

        collected.extend(batch)

    deduped = _dedupe_recommendations(collected)
    if not deduped:
        raise ValueError("No recommendations extracted from LLM responses.")
    logger.info("FMSI extraction done: {} recommendations (after dedupe)", len(deduped))
    return deduped


def extract_fmsi_recommendations_algo(pdf_text: str) -> list[dict[str, str]]:
    """Heuristically extract recommendations and conclusion summaries from an FMSI PDF text dump."""
    if not pdf_text:
        return []

    normalized = pdf_text.replace("\r", "")
    lowered = normalized.lower()

    recommendations_section_start = 0
    rec_match = re.search(r"(?:\b\d+\.\d+\s+)?recommendations\b", lowered)
    if rec_match:
        recommendations_section_start = rec_match.start()

    conclusion_start = len(normalized)
    conclusion_match = re.search(r"\bconclusion\b", lowered)
    if conclusion_match:
        conclusion_start = conclusion_match.start()

    recommendations_section = normalized[recommendations_section_start:conclusion_start]
    conclusion_section = normalized[conclusion_start:]

    recommendation_entries = _parse_letter_bullets(recommendations_section, include_sub_bullets=True)
    summary_entries = _parse_letter_bullets(conclusion_section, include_sub_bullets=False)

    results: list[dict[str, str]] = []
    for letter, text in recommendation_entries.items():
        results.append(
            {
                "text": text,
                "summary": summary_entries.get(letter, ""),
            }
        )
    return results


def _chunk_text(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        paragraph_len = len(paragraph)
        if current and current_len + paragraph_len + 2 > max_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = paragraph_len
            continue
        current.append(paragraph)
        current_len += paragraph_len + 2
    if current:
        chunks.append("\n\n".join(current))
    if not chunks:
        return [text]
    return chunks


def _dedupe_recommendations(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    unique: list[Recommendation] = []
    seen: set[str] = set()
    for recommendation in recommendations:
        cleaned = re.sub(r"\s+", " ", recommendation.recommendation).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(recommendation.model_copy(update={"recommendation": cleaned}, deep=True))
    return unique


def _parse_letter_bullets(section_text: str, *, include_sub_bullets: bool) -> dict[str, str]:
    letter_pattern = re.compile(r"^\s*([a-z])[\.\)]\s+(.*)$", re.IGNORECASE)
    bullet_pattern = re.compile(r"^\s*[-\u2022\u2023\u25AA•–—]\s+(.*)$")

    entries: dict[str, str] = {}
    current_letter: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines, current_letter
        if current_letter and current_lines:
            merged = " ".join(current_lines).strip()
            merged = re.sub(r"\s+", " ", merged)
            entries[current_letter] = merged
        current_letter = None
        current_lines = []

    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush()
            continue

        letter_match = letter_pattern.match(raw_line)
        if letter_match:
            flush()
            current_letter = letter_match.group(1).lower()
            current_lines = [letter_match.group(2).strip()]
            continue

        if include_sub_bullets and current_letter:
            bullet_match = bullet_pattern.match(raw_line)
            if bullet_match:
                current_lines.append(bullet_match.group(1).strip())
                continue

        if current_letter:
            current_lines.append(stripped)

    flush()
    return entries
