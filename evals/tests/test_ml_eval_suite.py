"""Regression tests for ML eval suite orchestration and paid-call guards."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "evals" / "tools"))

import run_ml_eval_suite as suite  # noqa: E402


def command_args(**overrides: object) -> Namespace:
    values: dict[str, object] = {
        "python": "python",
        "candidate_top_k": 10,
        "reranker_top_k": 10,
        "reranker_limit_sources": 5,
        "trace_root": Path("traces"),
        "report_root": Path("reports"),
        "allow_openrouter_embeddings": False,
        "allow_openrouter_reranker": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_baseline_command_requires_explicit_embedding_opt_in() -> None:
    without_opt_in = suite.build_baseline_command("es", "run", command_args())
    with_opt_in = suite.build_baseline_command(
        "es", "run", command_args(allow_openrouter_embeddings=True)
    )

    assert "--allow-openrouter-embeddings" not in without_opt_in
    assert "--allow-openrouter-embeddings" in with_opt_in


def test_reranker_command_forwards_both_paid_stage_opt_ins() -> None:
    command = suite.build_reranker_command(
        "en",
        "run",
        command_args(
            allow_openrouter_embeddings=True,
            allow_openrouter_reranker=True,
        ),
    )

    assert "--allow-openrouter-embeddings" in command
    assert "--allow-openrouter-reranker" in command


def test_missing_baselines_do_not_trigger_implicit_paid_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = Namespace(
        es_trace=tmp_path / "missing-es.json",
        en_trace=tmp_path / "missing-en.json",
        refresh_baselines=False,
    )
    monkeypatch.setattr(suite, "parse_args", lambda: args)
    run_command = monkeypatch.setattr(
        suite,
        "run_command",
        lambda command: pytest.fail(f"unexpected subprocess: {command}"),
    )

    with pytest.raises(FileNotFoundError, match="--refresh-baselines"):
        suite.main()

    assert run_command is None


def test_final_quality_gate_uses_complete_label_readiness() -> None:
    partial = {"overall": {"metrics_ready": False, "precision": 1.0}}
    complete = {"overall": {"metrics_ready": True, "precision": 0.5}}

    assert suite.final_quality_gate_status(partial) == "metrics blocked on labels"
    assert suite.final_quality_gate_status(complete) == "metrics available"
