from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import torch
from sentence_transformers import CrossEncoder


def _default_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


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
        ce_model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2",
        min_k: int = 1,
        max_k: int = 10,
        rel_drop_threshold: float = 0.20,
        device: torch.device | None = None,
        cross_encoder: CrossEncoder | None = None,
    ) -> None:
        self.device = device or _default_device()
        self.cross_encoder = cross_encoder or CrossEncoder(ce_model_name, device=self.device)
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

        intermediate_rows = self._rerank_with_cross_encoder(queries, candidates)
        if not intermediate_rows:
            return []

        results: list[RerankResult] = []
        for row in intermediate_rows:
            results.append(
                RerankResult(
                    query_index=row["query_index"],
                    candidate_index=row["candidate_index"],
                    query=row["query"],
                    candidate=row["candidate"],
                    reranker_score=row["reranker_score"],
                )
            )

        return results

    def _rerank_with_cross_encoder(
        self,
        queries: Sequence[str],
        candidates: Sequence[str],
    ) -> list[dict[str, int | float | str]]:
        results: list[dict[str, int | float | str]] = []
        for query_index, query in enumerate(queries):
            pairs = [[query, candidate] for candidate in candidates]
            ce_scores = self.cross_encoder.predict(pairs)

            idx_sorted = np.argsort(-ce_scores)
            sorted_scores = ce_scores[idx_sorted]

            k = dynamic_k_by_drop(
                sorted_scores,
                min_k=self.min_k,
                max_k=self.max_k,
                rel_drop_threshold=self.rel_drop_threshold,
            )

            top_idx = idx_sorted[:k]
            top_scores = sorted_scores[:k]

            for candidate_index, ce_score in zip(top_idx, top_scores, strict=True):
                candidate_index_int = int(candidate_index)
                results.append(
                    {
                        "query_index": query_index,
                        "candidate_index": candidate_index_int,
                        "query": query,
                        "candidate": candidates[candidate_index_int],
                        "reranker_score": float(ce_score),
                    }
                )

        return results


def main() -> None:
    queries = [
        "Ensure access to education for girls in rural areas.",
        "Protect freedom of expression for journalists.",
    ]
    candidates = [
        "Establish scholarship programs for rural girls and improve school infrastructure.",
        "Adopt legislation safeguarding journalists from harassment and censorship.",
        "Increase funding for hospital infrastructure upgrades across the country.",
    ]

    reranker = RecommendationReranker(
        min_k=1,
        max_k=3,
        rel_drop_threshold=0.15,
    )
    results = reranker.rerank(queries, candidates)

    if not results:
        print("No matches found for the dummy data.")
        return

    for result in results:
        print(
            f"Query #{result.query_index} -> Candidate #{result.candidate_index} (reranker={result.reranker_score:.3f})"
        )
        print(f"  Query: {result.query}")
        print(f"  Candidate: {result.candidate}\n")


__all__ = ["RecommendationReranker", "RerankResult", "dynamic_k_by_drop"]


if __name__ == "__main__":
    main()
