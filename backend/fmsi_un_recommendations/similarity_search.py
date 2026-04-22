from __future__ import annotations

from math import sqrt
from typing import Any

from loguru import logger
from pydantic import BaseModel

from fmsi_un_recommendations.settings import Settings
from fmsi_un_recommendations.utils import get_text_embedder

settings = Settings()

DEFAULT_CHUNK_CHAR_LIMIT = 80000


class Recommendation(BaseModel):
    recommendation: str
    domain: str
    beneficiaries: str
    theme: str


class RecommendationBatch(BaseModel):
    recommendations: list[Recommendation]


def _row_to_text_payload(row: dict[str, str]) -> str:
    parts: list[str] = []
    for key, value in row.items():
        if key == "embedding":
            continue
        if value:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def embed_un_recommendations(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Enrich UN recommendation rows with text embeddings."""
    if not rows:
        return []

    logger.info("Embedding {} UN rows", len(rows))
    embedder = get_text_embedder()
    payloads = [_row_to_text_payload(row) for row in rows]
    raw_embeddings = list(embedder.embed(payloads))

    enriched_rows: list[dict[str, Any]] = []
    for row, embedding in zip(rows, raw_embeddings, strict=False):
        enriched_row = dict(row)
        enriched_row["embedding"] = _embedding_to_list(embedding)
        enriched_rows.append(enriched_row)
    logger.info("Embedded UN rows: {}", len(enriched_rows))
    return enriched_rows


def embed_fmsi_recommendations(
    recommendations: list[Recommendation],
) -> list[dict[str, Any]]:
    """Enrich extracted FMSI recommendations with text embeddings."""
    if not recommendations:
        return []

    logger.info("Embedding {} FMSI recommendations", len(recommendations))
    embedder = get_text_embedder()
    payloads = [rec.recommendation for rec in recommendations]
    embeddings = list(embedder.embed(payloads))

    enriched_rows: list[dict[str, Any]] = []
    for rec, embedding in zip(recommendations, embeddings, strict=False):
        enriched_rows.append(
            {
                "recommendation": rec.recommendation,
                "theme": rec.theme,
                "beneficiaries": rec.beneficiaries,
                "domain": rec.domain,
                "embedding": _embedding_to_list(embedding),
            }
        )
    logger.info("Embedded FMSI recommendations: {}", len(enriched_rows))
    return enriched_rows


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if not vector_a or not vector_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vector_a, vector_b, strict=False))
    norm_a = sqrt(sum(a * a for a in vector_a))
    norm_b = sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def match_recommendation_vectors(
    source_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    *,
    threshold: float = 0.7,
) -> list[dict[str, Any]]:
    """Return matches between two embedding sets for all targets above the threshold."""
    logger.info("Matching {} FMSI vs {} UN rows (threshold={})", len(source_rows), len(target_rows), threshold)
    matches: list[dict[str, Any]] = []
    for source_index, source_row in enumerate(source_rows):
        source_vector = source_row.get("embedding") or []
        for target_index, target_row in enumerate(target_rows):
            score = cosine_similarity(source_vector, target_row.get("embedding") or [])
            if score >= threshold:
                matches.append(
                    {
                        "score": score,
                        "source_index": source_index,
                        "source_text": source_row.get("text") or source_row.get("recommendation", ""),
                        "source_row": {k: v for k, v in source_row.items() if k != "embedding"},
                        "target_index": target_index,
                        "target_text": _row_to_text_payload(target_row),
                        "target_row": {k: v for k, v in target_row.items() if k != "embedding"},
                    }
                )
    matches.sort(key=lambda item: item["score"], reverse=True)
    logger.info("Matching done: {} matches", len(matches))
    return matches


def _embedding_to_list(embedding: Any) -> list[float]:
    if hasattr(embedding, "tolist"):
        return [float(v) for v in embedding.tolist()]
    return [float(v) for v in embedding]
