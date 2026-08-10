"""Regression tests for final match-quality metric readiness."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "evals" / "tools"))

from evaluate_final_match_quality import summarize_rows  # noqa: E402


def candidate(relevance: str | None, *, rank: int) -> dict[str, object]:
    return {
        "human_relevance": relevance,
        "rank": rank,
        "semantic_score": 0.9,
    }


def test_partial_labels_do_not_publish_partial_metrics() -> None:
    candidates = [candidate("similar", rank=1)] + [candidate(None, rank=rank) for rank in range(2, 11)]

    summary = summarize_rows(candidates, [], max_rank=10, min_semantic_score=None)

    assert summary["metrics_ready"] is False
    assert summary["precision"] is None
    assert summary["recall"] is None
    assert summary["f1"] is None


def test_complete_labels_publish_precision_recall_and_f1() -> None:
    candidates = [
        candidate("similar", rank=1),
        candidate("not_relevant", rank=2),
        candidate("very_similar", rank=3),
    ]

    summary = summarize_rows(candidates, [], max_rank=2, min_semantic_score=None)

    assert summary["metrics_ready"] is True
    assert summary["precision"] == pytest.approx(0.5)
    assert summary["recall"] == pytest.approx(0.5)
    assert summary["f1"] == pytest.approx(0.5)
