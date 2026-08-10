"""Offline regression tests for paid-call guards and reranker cardinality."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "evals" / "tools"))
sys.path.insert(0, str(REPO / "backend"))

import run_ai_pipeline_eval as eval_harness  # noqa: E402


def _args(**overrides: object) -> SimpleNamespace:
    values = {
        "allow_openrouter_embeddings": False,
        "allow_openrouter_reranker": False,
        "skip_reranker": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_openrouter_embeddings_require_their_own_opt_in() -> None:
    settings = SimpleNamespace(embedding_provider="openrouter", reranker_provider="openrouter")

    with pytest.raises(RuntimeError, match="--allow-openrouter-embeddings"):
        eval_harness.require_openrouter_opt_ins(_args(), settings)

    eval_harness.require_openrouter_opt_ins(_args(allow_openrouter_embeddings=True), settings)


def test_openrouter_reranker_requires_its_own_opt_in() -> None:
    settings = SimpleNamespace(embedding_provider="local", reranker_provider="openrouter")

    with pytest.raises(RuntimeError, match="--allow-openrouter-reranker"):
        eval_harness.require_openrouter_opt_ins(_args(skip_reranker=False), settings)

    eval_harness.require_openrouter_opt_ins(
        _args(skip_reranker=False, allow_openrouter_reranker=True),
        settings,
    )


def test_reranker_api_receives_requested_top_n() -> None:
    matches = [
        {"source_text": "source", "target_text": f"target {index}", "target_index": index}
        for index in range(30)
    ]
    api_results = [
        SimpleNamespace(candidate_index=index, relevance_score=1.0 - index / 100)
        for index in range(10)
    ]

    with patch.object(eval_harness, "rerank_openrouter", return_value=api_results) as rerank:
        grouped, error = eval_harness.rerank_grouped_matches(
            {"s1": matches},
            candidate_top_k=30,
            reranker_top_k=10,
        )

    assert error is None
    assert len(grouped["s1"]) == 10
    assert rerank.call_args.kwargs["top_n"] == 10
