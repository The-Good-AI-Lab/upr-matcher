#!/usr/bin/env python3
"""Compare retrieval metrics across embedding models."""

from __future__ import annotations

import argparse
import json
import os
import re
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
DEFAULT_REPORT = REPO_ROOT / "evals/reports/embedding_model_sweep.md"
DEFAULT_JSON = REPO_ROOT / "evals/reports/embedding_model_sweep.json"
METRIC_KEYS = ("hit@10", "recall@10", "precision@10", "mrr", "ndcg@10")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug[:80] or "model"


def command_string(command: list[str], env_overrides: dict[str, str] | None = None) -> str:
    env_part = ""
    if env_overrides:
        env_part = " ".join(f"{key}={value}" for key, value in sorted(env_overrides.items())) + " "
    return env_part + " ".join(command)


def run_command(command: list[str], env_overrides: dict[str, str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(env_overrides)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "env_overrides": env_overrides,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def require_success(result: dict[str, Any]) -> None:
    if result["returncode"] == 0:
        return
    raise RuntimeError(
        "Command failed:\n"
        f"{command_string(result['command'], result.get('env_overrides'))}\n\n"
        f"stdout:\n{result['stdout']}\n\n"
        f"stderr:\n{result['stderr']}"
    )


def build_eval_command(language: str, run_id: str, args: argparse.Namespace) -> list[str]:
    return [
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


def macro_metric(trace: dict[str, Any], key: str) -> float | None:
    value = (((trace.get("semantic_candidate_matching") or {}).get("metrics") or {}).get("macro") or {}).get(key)
    return float(value) if value is not None else None


def trace_row(trace_path: Path, *, embedding_model: str, embedding_provider: str | None) -> dict[str, Any]:
    trace = read_json(trace_path)
    settings = trace.get("settings") or {}
    timings = trace.get("timings_seconds") or {}
    row = {
        "embedding_model": embedding_model,
        "embedding_provider": embedding_provider or settings.get("embedding_provider"),
        "run_id": trace.get("run_id") or trace_path.stem,
        "trace_path": str(trace_path),
        "case_id": (trace.get("case") or {}).get("case_id"),
        "language_pair": f"{settings.get('source_language', 'unknown')}-en",
        "source_language": settings.get("source_language"),
        "source_mode": settings.get("source_mode"),
        "gold_sources_evaluated": (trace.get("matching_inputs") or {}).get("gold_sources_evaluated"),
        "gold_links_evaluated": (trace.get("matching_inputs") or {}).get("gold_links_evaluated"),
        "reference_embedding_seconds": timings.get("reference_embedding"),
        "source_embedding_seconds": timings.get("source_embedding"),
        "semantic_matching_seconds": timings.get("semantic_candidate_matching"),
    }
    for key in METRIC_KEYS:
        row[key] = macro_metric(trace, key)
    return row


def failure_row(model: str, language: str, result: dict[str, Any]) -> dict[str, Any]:
    stderr = str(result.get("stderr") or "").strip()
    stdout = str(result.get("stdout") or "").strip()
    error_text = stderr or stdout
    summary = summarize_error(error_text)
    return {
        "embedding_model": model,
        "language_pair": f"{language}-en",
        "returncode": result.get("returncode"),
        "command": command_string(result["command"], result.get("env_overrides")),
        "error": summary,
    }


def summarize_error(text: str) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith(("ValueError:", "RuntimeError:", "openai.", "Error code:")):
            return line[:500]
    return lines[-1][:500] if lines else text[-500:]


def compute_language_gaps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for model in sorted({row["embedding_model"] for row in rows}):
        by_pair = {row["language_pair"]: row for row in rows if row["embedding_model"] == model}
        if "en-en" not in by_pair or "es-en" not in by_pair:
            continue
        gap: dict[str, Any] = {"embedding_model": model}
        for key in ("recall@10", "mrr", "ndcg@10"):
            en_value = by_pair["en-en"].get(key)
            es_value = by_pair["es-en"].get(key)
            gap[key] = round(en_value - es_value, 4) if en_value is not None and es_value is not None else None
        gaps.append(gap)
    return gaps


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Embedding Model Sweep",
        "",
        "This report compares semantic retrieval metrics while changing only the embedding model.",
        "",
    ]
    if summary["dry_run"]:
        lines.extend(
            [
                "Dry run only. No model calls were executed.",
                "",
                "## Planned Commands",
                "",
            ]
        )
        for command in summary["commands"]:
            lines.append(f"- `{command_string(command['command'], command.get('env_overrides'))}`")
        return "\n".join(lines) + "\n"

    rows = summary["rows"]
    failures = summary.get("failures") or []
    if not rows and not failures:
        lines.append("No sweep rows were produced.")
        return "\n".join(lines) + "\n"

    if rows:
        lines.extend(
            [
                "| Model | Provider | Pair | Sources | Links | hit@10 | recall@10 | precision@10 | MRR | NDCG@10 | Embed seconds |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in rows:
            embed_seconds = None
            if row.get("reference_embedding_seconds") is not None and row.get("source_embedding_seconds") is not None:
                embed_seconds = round(row["reference_embedding_seconds"] + row["source_embedding_seconds"], 3)
            lines.append(
                f"| `{row['embedding_model']}` | `{row.get('embedding_provider') or 'n/a'}` | `{row['language_pair']}` | "
                f"{fmt(row.get('gold_sources_evaluated'))} | {fmt(row.get('gold_links_evaluated'))} | "
                f"{fmt(row.get('hit@10'))} | {fmt(row.get('recall@10'))} | {fmt(row.get('precision@10'))} | "
                f"{fmt(row.get('mrr'))} | {fmt(row.get('ndcg@10'))} | {fmt(embed_seconds)} |"
            )

    gaps = summary["language_gaps"]
    if gaps:
        lines.extend(
            [
                "",
                "## Language Gaps",
                "",
                "| Model | Recall@10 gap | MRR gap | NDCG@10 gap |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for gap in gaps:
            lines.append(
                f"| `{gap['embedding_model']}` | {fmt(gap.get('recall@10'))} | "
                f"{fmt(gap.get('mrr'))} | {fmt(gap.get('ndcg@10'))} |"
            )
    if failures:
        lines.extend(
            [
                "",
                "## Failed Runs",
                "",
                "| Model | Pair | Return code | Error |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for failure in failures:
            error = str(failure.get("error") or "").replace("\n", "<br>")
            lines.append(
                f"| `{failure['embedding_model']}` | `{failure['language_pair']}` | "
                f"{fmt(failure.get('returncode'))} | {error} |"
            )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--embedding-model", action="append", dest="embedding_models", required=True)
    parser.add_argument("--embedding-provider", default=None)
    parser.add_argument("--embedding-batch-size", type=int, default=None)
    parser.add_argument("--language", choices=["es", "en"], action="append", dest="languages")
    parser.add_argument("--candidate-top-k", type=int, default=10)
    parser.add_argument("--allow-openrouter-embeddings", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--run-prefix", default=None)
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dry_run and not args.allow_openrouter_embeddings:
        raise RuntimeError(
            "Embedding model sweeps can make paid OpenRouter embedding calls. "
            "Pass --allow-openrouter-embeddings to run, or --dry-run to inspect commands."
        )
    languages = args.languages or ["es", "en"]
    prefix = args.run_prefix or f"embedding_sweep_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    commands: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for model in args.embedding_models:
        env_overrides = {"EMBEDDING_MODEL": model}
        if args.embedding_provider:
            env_overrides["EMBEDDING_PROVIDER"] = args.embedding_provider
        if args.embedding_batch_size is not None:
            env_overrides["EMBEDDING_BATCH_SIZE"] = str(args.embedding_batch_size)
        for language in languages:
            run_id = f"{prefix}_{slugify(model)}_{language}"
            command = build_eval_command(language, run_id, args)
            command_record = {
                "command": command,
                "env_overrides": env_overrides,
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
            if args.dry_run:
                commands.append(command_record)
                continue
            result = run_command(command, env_overrides)
            commands.append(result)
            if result["returncode"] != 0:
                failures.append(failure_row(model, language, result))
                if args.fail_fast:
                    require_success(result)
                continue
            rows.append(
                trace_row(
                    args.trace_root / f"{run_id}.json",
                    embedding_model=model,
                    embedding_provider=args.embedding_provider,
                )
            )

    rows.sort(key=lambda row: (row["embedding_model"], row["language_pair"]))
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "dry_run": args.dry_run,
        "run_prefix": prefix,
        "commands": commands,
        "rows": rows,
        "failures": failures,
        "language_gaps": compute_language_gaps(rows),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(summary), encoding="utf-8")
    args.json_output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote report to {args.report}")
    print(f"wrote json to {args.json_output}")


if __name__ == "__main__":
    main()
