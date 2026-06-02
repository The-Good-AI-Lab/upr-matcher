from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .settings import Settings
from .utils import get_openrouter_client

settings = Settings()


@dataclass(slots=True)
class RerankApiResult:
    candidate_index: int
    relevance_score: float


def embed_texts_openrouter(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []

    client = get_openrouter_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=list(texts),
    )
    embeddings_by_index: dict[int, list[float]] = {}
    for item in response.data:
        embeddings_by_index[item.index] = [float(value) for value in item.embedding]
    return [embeddings_by_index[index] for index in range(len(texts))]


def rerank_openrouter(
    query: str,
    documents: Sequence[str],
    *,
    top_n: int | None = None,
) -> list[RerankApiResult]:
    if not query.strip() or not documents:
        return []

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is not set.")

    base_url = settings.agent_base_url.rstrip("/")
    payload = {
        "model": settings.reranker_model,
        "query": query,
        "documents": list(documents),
    }
    if top_n is not None:
        payload["top_n"] = top_n

    request = Request(
        f"{base_url}/rerank",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter rerank failed ({exc.code}): {detail}") from exc

    data = json.loads(raw)
    return _parse_rerank_results(data)


def _parse_rerank_results(data: dict[str, Any]) -> list[RerankApiResult]:
    rows = data.get("results")
    if not isinstance(rows, list):
        return []

    results: list[RerankApiResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = row.get("index")
        score = row.get("relevance_score", row.get("score"))
        if index is None or score is None:
            continue
        results.append(RerankApiResult(candidate_index=int(index), relevance_score=float(score)))
    return results
