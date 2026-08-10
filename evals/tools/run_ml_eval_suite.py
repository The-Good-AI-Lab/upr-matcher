#!/usr/bin/env python3
"""Run or assemble the staged ML evaluation suite for UPR Matcher."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "evals/tools"
DEFAULT_TRACE_ROOT = REPO_ROOT / "evals/traces/live"
DEFAULT_REPORT_ROOT = REPO_ROOT / "evals/reports/live"
DEFAULT_SUITE_REPORT = REPO_ROOT / "evals/reports/ml_eval_suite_summary.md"
DEFAULT_SUITE_JSON = REPO_ROOT / "evals/reports/ml_eval_suite_summary.json"
DEFAULT_ES_TRACE = DEFAULT_TRACE_ROOT / "costa_rica_parser_regression_es_gold.json"
DEFAULT_EN_TRACE = DEFAULT_TRACE_ROOT / "costa_rica_parser_regression_en_gold.json"
DEFAULT_CANDIDATES = REPO_ROOT / "evals/labeling/costa_rica_candidate_pairs.jsonl"
DEFAULT_MISSING = REPO_ROOT / "evals/labeling/costa_rica_missing_gold_pairs.jsonl"
DEFAULT_LABEL_REPORT = REPO_ROOT / "evals/reports/costa_rica_candidate_label_metrics.md"
DEFAULT_RERANKER_REPORT = REPO_ROOT / "evals/reports/reranker_lift.md"
DEFAULT_RERANKER_JSON = REPO_ROOT / "evals/reports/reranker_lift.json"
DEFAULT_FINAL_REPORT = REPO_ROOT / "evals/reports/costa_rica_final_match_quality.md"
DEFAULT_FINAL_JSON = REPO_ROOT / "evals/reports/costa_rica_final_match_quality.json"
DEFAULT_EMBEDDING_SWEEP_REPORT = REPO_ROOT / "evals/reports/embedding_model_sweep.md"
DEFAULT_EMBEDDING_SWEEP_JSON = REPO_ROOT / "evals/reports/embedding_model_sweep.json"
METRIC_KEYS = ("hit@10", "recall@10", "precision@10", "mrr", "ndcg@10")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def command_string(command: list[str]) -> str:
    return " ".join(command)


def run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def require_success(result: dict[str, Any]) -> None:
    if result["returncode"] == 0:
        return
    raise RuntimeError(
        "Command failed:\n"
        f"{command_string(result['command'])}\n\n"
        f"stdout:\n{result['stdout']}\n\n"
        f"stderr:\n{result['stderr']}"
    )


def macro_metric(trace: dict[str, Any], stage: str, key: str) -> float | None:
    metrics = (trace.get(stage) or {}).get("metrics") or {}
    value = (metrics.get("macro") or {}).get(key)
    return float(value) if value is not None else None


def trace_summary(path: Path) -> dict[str, Any]:
    trace = read_json(path)
    settings = trace.get("settings") or {}
    document = trace.get("document_extraction") or {}
    row = {
        "run_id": trace.get("run_id") or path.stem,
        "trace_path": str(path),
        "case_id": (trace.get("case") or {}).get("case_id"),
        "language_pair": f"{settings.get('source_language', 'unknown')}-en",
        "source_language": settings.get("source_language"),
        "source_mode": settings.get("source_mode"),
        "gold_sources_evaluated": (trace.get("matching_inputs") or {}).get("gold_sources_evaluated"),
        "gold_links_evaluated": (trace.get("matching_inputs") or {}).get("gold_links_evaluated"),
        "reference_rows": document.get("reference_rows"),
        "gold_target_id_coverage": document.get("gold_target_id_coverage"),
        "gold_target_id_text_coverage": document.get("gold_target_id_text_coverage"),
    }
    for key in METRIC_KEYS:
        row[key] = macro_metric(trace, "semantic_candidate_matching", key)
    return row


def label_summary(candidate_path: Path, missing_path: Path) -> dict[str, Any]:
    candidates = read_jsonl(candidate_path)
    missing = read_jsonl(missing_path)
    labeled = [row for row in candidates if row.get("human_relevance")]
    decisive = [row for row in labeled if row.get("human_relevance") != "unclear"]
    relevant = [row for row in decisive if row.get("human_relevance") in {"similar", "very_similar"}]
    by_language: dict[str, dict[str, int]] = {}
    for language in sorted({row.get("language_pair", "unknown") for row in candidates}):
        rows = [row for row in candidates if row.get("language_pair") == language]
        rows_labeled = [row for row in rows if row.get("human_relevance")]
        by_language[language] = {"rows": len(rows), "labeled": len(rows_labeled)}
    return {
        "candidate_rows": len(candidates),
        "labeled_rows": len(labeled),
        "decisive_rows": len(decisive),
        "relevant_rows": len(relevant),
        "precision": None if not decisive else round(len(relevant) / len(decisive), 4),
        "missing_gold_rows": len(missing),
        "missing_gold_reviewed": sum(1 for row in missing if row.get("failure_category") or row.get("review_notes")),
        "by_language": by_language,
    }


def load_reranker_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return (read_json(path).get("rows") or []) if path.suffix == ".json" else []


def load_final_quality(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return read_json(path)


def load_embedding_sweep(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return read_json(path)


def build_baseline_command(language: str, run_id: str, args: argparse.Namespace) -> list[str]:
    command = [
        args.python,
        str(TOOLS_ROOT / "run_ai_pipeline_eval.py"),
        "--source-mode",
        "gold",
        "--source-language",
        language,
        "--candidate-top-k",
        str(args.candidate_top_k),
        "--skip-reranker",
        "--run-id",
        run_id,
        "--trace-root",
        str(args.trace_root),
        "--report-root",
        str(args.report_root),
    ]
    if args.allow_openrouter_embeddings:
        command.append("--allow-openrouter-embeddings")
    return command


def build_reranker_command(language: str, run_id: str, args: argparse.Namespace) -> list[str]:
    command = [
        args.python,
        str(TOOLS_ROOT / "run_ai_pipeline_eval.py"),
        "--source-mode",
        "gold",
        "--source-language",
        language,
        "--candidate-top-k",
        str(args.candidate_top_k),
        "--reranker-top-k",
        str(args.reranker_top_k),
        "--run-id",
        run_id,
        "--trace-root",
        str(args.trace_root),
        "--report-root",
        str(args.report_root),
    ]
    if args.reranker_limit_sources:
        command.extend(["--limit-sources", str(args.reranker_limit_sources)])
    if args.allow_openrouter_embeddings:
        command.append("--allow-openrouter-embeddings")
    if args.allow_openrouter_reranker:
        command.append("--allow-openrouter-reranker")
    return command


def build_extraction_command(args: argparse.Namespace, run_id: str) -> list[str]:
    command = [
        args.python,
        str(TOOLS_ROOT / "evaluate_extraction_stability.py"),
        "--source-language",
        args.extraction_language,
        "--repeats",
        str(args.extraction_repeats),
        "--max-cost-usd",
        str(args.max_cost_usd),
        "--prompt-usd-per-1m",
        str(args.prompt_usd_per_1m),
        "--completion-usd-per-1m",
        str(args.completion_usd_per_1m),
        "--max-llm-chunks",
        str(args.max_llm_chunks),
        "--max-completion-tokens",
        str(args.max_completion_tokens),
        "--run-id",
        run_id,
        "--trace-root",
        str(args.trace_root),
        "--report-root",
        str(args.report_root),
    ]
    if args.allow_openrouter:
        command.append("--allow-openrouter")
    if args.openrouter_model:
        command.extend(["--openrouter-model", args.openrouter_model])
    return command


def build_embedding_sweep_command(args: argparse.Namespace) -> list[str]:
    command = [
        args.python,
        str(TOOLS_ROOT / "compare_embedding_models.py"),
        "--candidate-top-k",
        str(args.candidate_top_k),
        "--trace-root",
        str(args.trace_root),
        "--report-root",
        str(args.report_root),
        "--report",
        str(DEFAULT_EMBEDDING_SWEEP_REPORT),
        "--json-output",
        str(DEFAULT_EMBEDDING_SWEEP_JSON),
    ]
    for model in args.embedding_models or []:
        command.extend(["--embedding-model", model])
    for language in args.embedding_languages or []:
        command.extend(["--language", language])
    if args.embedding_provider:
        command.extend(["--embedding-provider", args.embedding_provider])
    if args.embedding_batch_size is not None:
        command.extend(["--embedding-batch-size", str(args.embedding_batch_size)])
    if args.allow_openrouter_embeddings:
        command.append("--allow-openrouter-embeddings")
    if args.dry_run_embedding_sweep:
        command.append("--dry-run")
    return command


def render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# ML Eval Suite Summary",
        "",
        f"- Created at: `{summary['created_at']}`",
        f"- Suite run ID: `{summary['suite_run_id']}`",
        "",
        "## Commands",
        "",
    ]
    for command in summary["commands"]:
        status = "ok" if command["returncode"] == 0 else f"failed ({command['returncode']})"
        lines.append(f"- `{command_string(command['command'])}`: {status}")

    lines.extend(
        [
            "",
            "## Retrieval Baselines",
            "",
            "| Pair | Run | Sources | Links | Target coverage | hit@10 | recall@10 | precision@10 | MRR | NDCG@10 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary["retrieval_baselines"]:
        lines.append(
            f"| `{row['language_pair']}` | `{row['run_id']}` | {fmt(row['gold_sources_evaluated'])} | "
            f"{fmt(row['gold_links_evaluated'])} | {fmt(row['gold_target_id_coverage'])} | "
            f"{fmt(row['hit@10'])} | {fmt(row['recall@10'])} | {fmt(row['precision@10'])} | "
            f"{fmt(row['mrr'])} | {fmt(row['ndcg@10'])} |"
        )
    gap = summary.get("language_gap") or {}
    if gap:
        lines.extend(
            [
                "",
                "## Language Gap",
                "",
                f"- Recall@10 gap (`en-en` minus `es-en`): {fmt(gap.get('recall@10'))}",
                f"- MRR gap (`en-en` minus `es-en`): {fmt(gap.get('mrr'))}",
                f"- NDCG@10 gap (`en-en` minus `es-en`): {fmt(gap.get('ndcg@10'))}",
            ]
        )

    labels = summary["labels"]
    lines.extend(
        [
            "",
            "## Human Labels",
            "",
            f"- Candidate rows: {labels['candidate_rows']}",
            f"- Labeled rows: {labels['labeled_rows']}",
            f"- Decisive rows: {labels['decisive_rows']}",
            f"- Precision over decisive labels: {fmt(labels['precision'])}",
            f"- Missed-gold rows: {labels['missing_gold_rows']}",
            f"- Reviewed missed-gold rows: {labels['missing_gold_reviewed']}",
            "",
            "| Pair | Candidate rows | Labeled rows |",
            "| --- | ---: | ---: |",
        ]
    )
    for language, values in labels["by_language"].items():
        lines.append(f"| `{language}` | {values['rows']} | {values['labeled']} |")

    lines.extend(["", "## Reranker Lift", ""])
    reranker_rows = summary["reranker_lift"]
    if reranker_rows:
        lines.extend(
            [
                "| Run | Pair | Sources | recall@10 delta | MRR delta | NDCG@10 delta |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in reranker_rows:
            lines.append(
                f"| `{row['run_id']}` | `{row['language_pair']}` | {fmt(row.get('evaluated_sources'))} | "
                f"{fmt(row.get('delta_recall@10'))} | {fmt(row.get('delta_mrr'))} | {fmt(row.get('delta_ndcg@10'))} |"
            )
    else:
        lines.append("- No reranker traces with metrics were found.")

    embedding_sweep = summary.get("embedding_model_sweep")
    lines.extend(["", "## Embedding Model Sweep", ""])
    if embedding_sweep:
        if embedding_sweep.get("dry_run"):
            lines.append("- Dry run only. No embedding calls were executed.")
        elif embedding_sweep.get("rows"):
            lines.extend(
                [
                    "| Model | Pair | recall@10 | MRR | NDCG@10 |",
                    "| --- | --- | ---: | ---: | ---: |",
                ]
            )
            for row in embedding_sweep["rows"]:
                lines.append(
                    f"| `{row['embedding_model']}` | `{row['language_pair']}` | {fmt(row.get('recall@10'))} | "
                    f"{fmt(row.get('mrr'))} | {fmt(row.get('ndcg@10'))} |"
                )
        else:
            lines.append("- No sweep rows were produced.")
        if embedding_sweep.get("failures"):
            lines.append(f"- Failed runs: {len(embedding_sweep['failures'])}")
    else:
        lines.append("- Not run. Use `--embedding-model-sweep MODEL --allow-openrouter-embeddings` to compare models.")

    final_quality = summary.get("final_match_quality")
    lines.extend(["", "## Final Match Quality", ""])
    if final_quality:
        policy = final_quality["policy"]
        overall = final_quality["overall"]
        lines.extend(
            [
                f"- Policy: rank <= {policy['max_rank']}, minimum semantic score {fmt(policy['min_semantic_score'])}",
                f"- Selected rows: {overall['selected_rows']}",
                f"- Selected decisive rows: {overall['selected_decisive_rows']}",
                f"- Precision: {fmt(overall['precision'])}",
                f"- Recall: {fmt(overall['recall'])}",
                f"- F1: {fmt(overall['f1'])}",
            ]
        )
    else:
        lines.append("- Not available.")

    extraction = summary.get("extraction_stability")
    lines.extend(["", "## Extraction Stability", ""])
    if extraction:
        aggregate = extraction["aggregate"]
        lines.extend(
            [
                f"- Run ID: `{extraction['run_id']}`",
                f"- Repeats completed: {aggregate['repeats_completed']}",
                f"- Gold coverage min/mean/max: {aggregate['gold_coverage_at_threshold']['min']} / "
                f"{aggregate['gold_coverage_at_threshold']['mean']} / {aggregate['gold_coverage_at_threshold']['max']}",
                f"- Extracted count min/mean/max: {aggregate['observed_count']['min']} / "
                f"{aggregate['observed_count']['mean']} / {aggregate['observed_count']['max']}",
                f"- Pairwise recommendation Jaccard min/mean/max: {aggregate['pairwise_recommendation_jaccard']['min']} / "
                f"{aggregate['pairwise_recommendation_jaccard']['mean']} / "
                f"{aggregate['pairwise_recommendation_jaccard']['max']}",
            ]
        )
    else:
        lines.append("- Not run. Use `--run-extraction-repeats --allow-openrouter` to spend OpenRouter budget on this stage.")

    lines.extend(
        [
            "",
            "## Gate Status",
            "",
            "| Stage | Status |",
            "| --- | --- |",
        ]
    )
    for item in summary["gate_status"]:
        lines.append(f"| {item['stage']} | {item['status']} |")
    return "\n".join(lines) + "\n"


def compute_language_gap(rows: list[dict[str, Any]]) -> dict[str, float] | None:
    by_pair = {row["language_pair"]: row for row in rows}
    if "en-en" not in by_pair or "es-en" not in by_pair:
        return None
    gap: dict[str, float] = {}
    for key in ("recall@10", "mrr", "ndcg@10"):
        left = by_pair["en-en"].get(key)
        right = by_pair["es-en"].get(key)
        if left is not None and right is not None:
            gap[key] = round(left - right, 4)
    return gap


def final_quality_gate_status(final_quality: dict[str, Any] | None) -> str:
    metrics_ready = (final_quality or {}).get("overall", {}).get("metrics_ready") is True
    return "metrics available" if metrics_ready else "metrics blocked on labels"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--suite-report", type=Path, default=DEFAULT_SUITE_REPORT)
    parser.add_argument("--suite-json", type=Path, default=DEFAULT_SUITE_JSON)
    parser.add_argument("--es-trace", type=Path, default=DEFAULT_ES_TRACE)
    parser.add_argument("--en-trace", type=Path, default=DEFAULT_EN_TRACE)
    parser.add_argument("--candidate-top-k", type=int, default=10)
    parser.add_argument("--embedding-model-sweep", action="append", dest="embedding_models")
    parser.add_argument("--embedding-provider", default=None)
    parser.add_argument("--embedding-batch-size", type=int, default=None)
    parser.add_argument("--embedding-language", choices=["es", "en"], action="append", dest="embedding_languages")
    parser.add_argument("--allow-openrouter-embeddings", action="store_true")
    parser.add_argument("--dry-run-embedding-sweep", action="store_true")
    parser.add_argument("--final-max-rank", type=int, default=10)
    parser.add_argument("--final-min-semantic-score", type=float, default=None)
    parser.add_argument("--refresh-baselines", action="store_true")
    parser.add_argument("--skip-label-artifacts", action="store_true")
    parser.add_argument("--run-reranker-sweep", action="store_true")
    parser.add_argument("--allow-openrouter-reranker", action="store_true")
    parser.add_argument("--reranker-language", choices=["en", "es"], action="append", dest="reranker_languages")
    parser.add_argument("--reranker-top-k", type=int, default=10)
    parser.add_argument("--reranker-limit-sources", type=int, default=5)
    parser.add_argument("--run-extraction-repeats", action="store_true")
    parser.add_argument("--allow-openrouter", action="store_true")
    parser.add_argument("--extraction-language", choices=["es", "en"], default="es")
    parser.add_argument("--extraction-repeats", type=int, default=3)
    parser.add_argument("--openrouter-model", default=None)
    parser.add_argument("--max-cost-usd", type=float, default=10.0)
    parser.add_argument("--prompt-usd-per-1m", type=float, default=1.0)
    parser.add_argument("--completion-usd-per-1m", type=float, default=1.0)
    parser.add_argument("--max-llm-chunks", type=int, default=1)
    parser.add_argument("--max-completion-tokens", type=int, default=4096)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite_run_id = f"ml_eval_suite_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    commands: list[dict[str, Any]] = []

    es_trace = args.es_trace
    en_trace = args.en_trace
    missing_baselines = [path for path in (es_trace, en_trace) if not path.exists()]
    if missing_baselines and not args.refresh_baselines:
        missing = ", ".join(str(path) for path in missing_baselines)
        raise FileNotFoundError(
            f"Baseline trace(s) not found: {missing}. "
            "Pass --refresh-baselines --allow-openrouter-embeddings to generate them."
        )
    if args.refresh_baselines:
        if not args.allow_openrouter_embeddings:
            raise RuntimeError("--refresh-baselines requires --allow-openrouter-embeddings")
        es_run_id = f"{suite_run_id}_es_gold"
        en_run_id = f"{suite_run_id}_en_gold"
        for language, run_id in (("es", es_run_id), ("en", en_run_id)):
            result = run_command(build_baseline_command(language, run_id, args))
            commands.append(result)
            require_success(result)
        es_trace = args.trace_root / f"{es_run_id}.json"
        en_trace = args.trace_root / f"{en_run_id}.json"

    if not es_trace.exists():
        raise FileNotFoundError(f"Spanish baseline trace not found: {es_trace}")
    if not en_trace.exists():
        raise FileNotFoundError(f"English baseline trace not found: {en_trace}")

    if not args.skip_label_artifacts:
        build_labels = [
            args.python,
            str(TOOLS_ROOT / "build_candidate_labeling_queue.py"),
            "--trace",
            str(es_trace),
            "--trace",
            str(en_trace),
        ]
        result = run_command(build_labels)
        commands.append(result)
        require_success(result)

        summarize_labels = [args.python, str(TOOLS_ROOT / "summarize_candidate_labels.py")]
        result = run_command(summarize_labels)
        commands.append(result)
        require_success(result)

    reranker_trace_paths: list[Path] = []
    if args.run_reranker_sweep:
        if not args.allow_openrouter_embeddings or not args.allow_openrouter_reranker:
            raise RuntimeError(
                "--run-reranker-sweep requires --allow-openrouter-embeddings "
                "and --allow-openrouter-reranker"
            )
        languages = args.reranker_languages or ["en", "es"]
        for language in languages:
            run_id = f"{suite_run_id}_reranker_{language}"
            result = run_command(build_reranker_command(language, run_id, args))
            commands.append(result)
            require_success(result)
            reranker_trace_paths.append(args.trace_root / f"{run_id}.json")

    reranker_command = [
        args.python,
        str(TOOLS_ROOT / "evaluate_reranker_lift.py"),
        "--report",
        str(DEFAULT_RERANKER_REPORT),
        "--json-output",
        str(DEFAULT_RERANKER_JSON),
    ]
    for path in reranker_trace_paths:
        reranker_command.extend(["--trace", str(path)])
    result = run_command(reranker_command)
    commands.append(result)
    require_success(result)

    final_quality_command = [
        args.python,
        str(TOOLS_ROOT / "evaluate_final_match_quality.py"),
        "--max-rank",
        str(args.final_max_rank),
        "--report",
        str(DEFAULT_FINAL_REPORT),
        "--json-output",
        str(DEFAULT_FINAL_JSON),
    ]
    if args.final_min_semantic_score is not None:
        final_quality_command.extend(["--min-semantic-score", str(args.final_min_semantic_score)])
    result = run_command(final_quality_command)
    commands.append(result)
    require_success(result)

    extraction_trace: dict[str, Any] | None = None
    if args.run_extraction_repeats:
        extraction_run_id = f"{suite_run_id}_extraction_{args.extraction_language}"
        result = run_command(build_extraction_command(args, extraction_run_id))
        commands.append(result)
        require_success(result)
        extraction_trace = read_json(args.trace_root / f"{extraction_run_id}.json")

    embedding_sweep: dict[str, Any] | None = None
    if args.embedding_models:
        result = run_command(build_embedding_sweep_command(args))
        commands.append(result)
        require_success(result)
        embedding_sweep = load_embedding_sweep(DEFAULT_EMBEDDING_SWEEP_JSON)

    retrieval_rows = [trace_summary(es_trace), trace_summary(en_trace)]
    final_quality = load_final_quality(DEFAULT_FINAL_JSON)
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "suite_run_id": suite_run_id,
        "commands": commands,
        "retrieval_baselines": retrieval_rows,
        "language_gap": compute_language_gap(retrieval_rows),
        "labels": label_summary(DEFAULT_CANDIDATES, DEFAULT_MISSING),
        "reranker_lift": load_reranker_rows(DEFAULT_RERANKER_JSON),
        "embedding_model_sweep": embedding_sweep,
        "final_match_quality": final_quality,
        "extraction_stability": extraction_trace,
        "gate_status": [
            {
                "stage": "Source extraction",
                "status": "repeat eval run" if extraction_trace else "not run in this suite; opt in with OpenRouter",
            },
            {"stage": "Semantic retrieval", "status": "baseline metrics available for es-en and en-en"},
            {
                "stage": "Embedding model sweep",
                "status": "completed"
                if embedding_sweep and embedding_sweep.get("rows")
                else "not run"
                if not args.embedding_models
                else "dry run" if embedding_sweep and embedding_sweep.get("dry_run") else "no rows produced",
            },
            {
                "stage": "Candidate precision",
                "status": "blocked on human labels" if label_summary(DEFAULT_CANDIDATES, DEFAULT_MISSING)["labeled_rows"] == 0 else "human labels present",
            },
            {
                "stage": "Reranker",
                "status": "lift report generated" if load_reranker_rows(DEFAULT_RERANKER_JSON) else "no reranker metrics yet",
            },
            {
                "stage": "Final match quality",
                "status": final_quality_gate_status(final_quality),
            },
            {"stage": "LLM judge validation", "status": "blocked until enough human pass/fail labels exist"},
        ],
    }
    args.suite_report.parent.mkdir(parents=True, exist_ok=True)
    args.suite_json.parent.mkdir(parents=True, exist_ok=True)
    args.suite_report.write_text(render_summary(summary), encoding="utf-8")
    args.suite_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote suite report to {args.suite_report}")
    print(f"wrote suite json to {args.suite_json}")


if __name__ == "__main__":
    main()
