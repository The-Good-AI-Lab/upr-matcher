"""Unit tests for the ranking metrics that every eval result rests on.

`ranking_metrics` / `dcg` (evals/tools/run_ai_pipeline_eval.py) compute the
recall@k / precision@k / hit@k / MRR / NDCG@k numbers reported throughout the
ML eval framework. If their math silently drifts, every metric in the reports
is wrong but still looks plausible — so this pins the semantics with values
derived by hand from the definitions (NOT copied from the functions' output).

Pure + offline: no network, no API keys, no backend services. Run with:
    uv run --project backend --with pytest pytest evals/tests/test_ranking_metrics.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "evals" / "tools"))
sys.path.insert(0, str(REPO / "backend"))

from run_ai_pipeline_eval import dcg, ranking_metrics  # noqa: E402

APPROX = dict(abs=1e-4)  # functions round to 4 dp; this catches any semantic drift


def test_dcg_matches_log2_definition() -> None:
    # dcg = sum(rel / log2(i + 2)) with i 0-based, i.e. ranks 1,2,3 -> /log2(2),/log2(3),/log2(4)
    expected = 3 / math.log2(2) + 2 / math.log2(3) + 3 / math.log2(4)  # = 3 + 1.26186 + 1.5
    assert dcg([3, 2, 3]) == pytest.approx(expected, **APPROX)
    assert dcg([]) == 0.0


def test_perfect_ranking_single_relevant_at_rank_1() -> None:
    m = ranking_metrics({"s1": ["t1", "t2", "t3"]}, {"s1": {"t1": 1}})
    s = m["per_source"]["s1"]
    assert s["mrr"] == pytest.approx(1.0, **APPROX)  # first hit at rank 1 -> 1/1
    for k in (1, 3, 5, 10):
        assert s[f"recall@{k}"] == pytest.approx(1.0, **APPROX)  # 1 of 1 expected
        assert s[f"hit@{k}"] == pytest.approx(1.0, **APPROX)
        assert s[f"ndcg@{k}"] == pytest.approx(1.0, **APPROX)  # relevant at top -> ideal
    assert s["precision@1"] == pytest.approx(1.0, **APPROX)  # 1 hit / 1 returned
    assert s["precision@3"] == pytest.approx(1 / 3, **APPROX)  # 1 hit / 3 returned


def test_first_relevant_at_rank_2() -> None:
    m = ranking_metrics({"s1": ["x", "t1", "y"]}, {"s1": {"t1": 1}})
    s = m["per_source"]["s1"]
    assert s["mrr"] == pytest.approx(0.5, **APPROX)  # 1/2
    assert s["recall@1"] == pytest.approx(0.0, **APPROX)  # t1 not in top-1
    assert s["hit@1"] == pytest.approx(0.0, **APPROX)
    assert s["ndcg@1"] == pytest.approx(0.0, **APPROX)  # rels=[0]
    assert s["recall@3"] == pytest.approx(1.0, **APPROX)  # t1 in top-3
    assert s["precision@3"] == pytest.approx(1 / 3, **APPROX)
    # rels=[0,1,0] -> dcg = 1/log2(3); ideal=[1] -> dcg = 1/log2(2) = 1
    assert s["ndcg@3"] == pytest.approx(1 / math.log2(3), **APPROX)  # 0.6309


def test_partial_recall_denominator_is_expected_count() -> None:
    # 2 relevant, only 1 retrieved -> recall capped at 0.5 even at large k
    m = ranking_metrics({"s1": ["t1", "x", "y"]}, {"s1": {"t1": 1, "t2": 1}})
    s = m["per_source"]["s1"]
    assert s["recall@1"] == pytest.approx(0.5, **APPROX)
    assert s["recall@10"] == pytest.approx(0.5, **APPROX)  # t2 never retrieved
    assert s["precision@1"] == pytest.approx(1.0, **APPROX)
    # rels=[1,0,0] -> dcg=1; ideal=[1,1] -> dcg = 1 + 1/log2(3)
    assert s["ndcg@3"] == pytest.approx(1.0 / (1.0 + 1 / math.log2(3)), **APPROX)  # 0.6131


def test_graded_relevance_penalizes_wrong_order() -> None:
    # higher-relevance t1 (rel=2) ranked below t2 (rel=1) -> NDCG < 1
    m = ranking_metrics({"s1": ["t2", "t1"]}, {"s1": {"t1": 2, "t2": 1}})
    s = m["per_source"]["s1"]
    assert s["mrr"] == pytest.approx(1.0, **APPROX)  # t2 is relevant, at rank 1
    assert s["recall@3"] == pytest.approx(1.0, **APPROX)
    # ndcg@1: rels=[1] dcg=1; ideal=[2] dcg=2 -> 0.5
    assert s["ndcg@1"] == pytest.approx(0.5, **APPROX)
    # ndcg@3: dcg([1,2]) / dcg([2,1])
    got = dcg([1, 2]) / dcg([2, 1])
    assert s["ndcg@3"] == pytest.approx(got, **APPROX)  # 0.8597


def test_gold_source_with_no_predictions_scores_zero() -> None:
    m = ranking_metrics({"s1": []}, {"s1": {"t1": 1}})
    s = m["per_source"]["s1"]
    assert s["returned_count"] == 0
    assert s["expected_count"] == 1
    assert s["mrr"] == pytest.approx(0.0, **APPROX)
    for k in (1, 3, 5, 10):
        assert s[f"recall@{k}"] == pytest.approx(0.0, **APPROX)
        assert s[f"precision@{k}"] == pytest.approx(0.0, **APPROX)
        assert s[f"hit@{k}"] == pytest.approx(0.0, **APPROX)
        assert s[f"ndcg@{k}"] == pytest.approx(0.0, **APPROX)


def test_macro_is_mean_over_sources_not_links() -> None:
    # one perfect source + one missed source -> macro = mean of the two
    m = ranking_metrics(
        {"s1": ["t1"], "s2": []},
        {"s1": {"t1": 1}, "s2": {"t9": 1}},
    )
    macro = m["macro"]
    assert m["evaluated_sources"] == 2
    assert macro["recall@1"] == pytest.approx(0.5, **APPROX)  # (1.0 + 0.0) / 2
    assert macro["mrr"] == pytest.approx(0.5, **APPROX)
    assert macro["hit@1"] == pytest.approx(0.5, **APPROX)
    assert macro["ndcg@1"] == pytest.approx(0.5, **APPROX)


def test_empty_gold_yields_empty_macro() -> None:
    m = ranking_metrics({"s1": ["t1"]}, {})
    assert m["evaluated_sources"] == 0
    assert m["per_source"] == {}
    assert m["macro"] == {}


def test_duplicate_target_ids_count_only_at_their_highest_rank() -> None:
    m = ranking_metrics({"s1": ["t1", "t1", "x"]}, {"s1": {"t1": 1}})
    source = m["per_source"]["s1"]

    assert source["returned_count"] == 2
    assert source["precision@3"] == pytest.approx(0.5, **APPROX)
    assert source["ndcg@3"] == pytest.approx(1.0, **APPROX)
