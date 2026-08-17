from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .settings import Settings
from .utils import get_openrouter_client

settings = Settings()

# Rerank uses a raw HTTP call (no SDK retry), so transient failures are retried here.
_RERANK_MAX_ATTEMPTS = 5
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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

    raw: str | None = None
    last_exc: Exception | None = None
    for attempt in range(_RERANK_MAX_ATTEMPTS):
        try:
            with urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
            break
        except HTTPError as exc:
            if exc.code in _RETRYABLE_STATUS and attempt < _RERANK_MAX_ATTEMPTS - 1:
                last_exc = exc
                time.sleep(min(2.0**attempt, 16.0))
                continue
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter rerank failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            last_exc = exc
            if attempt < _RERANK_MAX_ATTEMPTS - 1:
                time.sleep(min(2.0**attempt, 16.0))
                continue
            raise RuntimeError(f"OpenRouter rerank connection failed: {exc.reason}") from exc

    if raw is None:  # pragma: no cover - defensive
        raise RuntimeError("OpenRouter rerank failed after retries") from last_exc

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
