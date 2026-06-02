from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .openrouter import rerank_openrouter
from .settings import Settings

settings = Settings()


def dynamic_k_by_drop(
    scores: Sequence[float],
    *,
    min_k: int = 3,
    max_k: int = 20,
    rel_drop_threshold: float = 0.25,
) -> int:
    scores = list(scores)
    n = min(len(scores), max_k)

    if n <= min_k:
        return n

    for i in range(1, n):
        prev_score = scores[i - 1]
        score = scores[i]
        if prev_score == 0:
            continue

        rel_drop = (prev_score - score) / abs(prev_score)
        if rel_drop >= rel_drop_threshold and i >= min_k:
            return i

    return n


@dataclass(slots=True)
class RerankResult:
    query_index: int
    candidate_index: int
    query: str
    candidate: str
    reranker_score: float


class RecommendationReranker:
    def __init__(
        self,
        *,
        min_k: int = 1,
        max_k: int = 10,
        rel_drop_threshold: float = 0.20,
    ) -> None:
        self.min_k = min_k
        self.max_k = max_k
        self.rel_drop_threshold = rel_drop_threshold

    def rerank(
        self,
        queries: Sequence[str],
        candidates: Sequence[str],
    ) -> list[RerankResult]:
        if not queries or not candidates:
            return []

        if settings.reranker_provider.lower() != "openrouter":
            raise NotImplementedError(f"Unsupported reranker provider: {settings.reranker_provider}")

        results: list[RerankResult] = []
        top_n = min(settings.rerank_top_n, len(candidates), self.max_k)
        for query_index, query in enumerate(queries):
            api_results = rerank_openrouter(
                query,
                candidates,
                top_n=top_n,
            )
            for result in api_results:
                if result.candidate_index >= len(candidates):
                    continue
                results.append(
                    RerankResult(
                        query_index=query_index,
                        candidate_index=result.candidate_index,
                        query=query,
                        candidate=candidates[result.candidate_index],
                        reranker_score=result.relevance_score,
                    )
                )
        return results


_RERANKER_INSTANCE: RecommendationReranker | None = None


def get_reranker(
    *,
    min_k: int = 1,
    max_k: int = 10,
    rel_drop_threshold: float = 0.20,
) -> RecommendationReranker:
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is None:
        _RERANKER_INSTANCE = RecommendationReranker(
            min_k=min_k,
            max_k=max_k,
            rel_drop_threshold=rel_drop_threshold,
        )
    return _RERANKER_INSTANCE


__all__ = ["RecommendationReranker", "RerankResult", "dynamic_k_by_drop", "get_reranker"]
