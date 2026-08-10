#!/usr/bin/env python3
"""Build a human-labeling queue from eval trace top candidates."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_LINKS = REPO_ROOT / "evals/gold/costa_rica_2024_match_links.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "evals/labeling/costa_rica_candidate_pairs.jsonl"
DEFAULT_ENRICHED_OUTPUT = REPO_ROOT / "evals/labeling/costa_rica_candidate_pairs_with_gold.jsonl"
DEFAULT_MISSING_OUTPUT = REPO_ROOT / "evals/labeling/costa_rica_missing_gold_pairs.jsonl"
DEFAULT_TRACES = [
    REPO_ROOT / "evals/traces/live/costa_rica_parser_regression_es_gold.json",
    REPO_ROOT / "evals/traces/live/costa_rica_parser_regression_en_gold.json",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def gold_link_lookup(gold_links: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for link in gold_links:
        source_id = str(link.get("source_id") or "")
        target_id = str(link.get("target_recommendation_id") or "")
        if source_id and target_id:
            grouped[(source_id, target_id)].append(link)

    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for key, links in grouped.items():
        best = max(links, key=lambda item: int(item.get("relevance_score") or 0))
        lookup[key] = {
            "existing_gold_relevance": best.get("relevance"),
            "existing_gold_relevance_score": best.get("relevance_score"),
            "gold_match_label_ids": sorted(str(item.get("match_label_id")) for item in links if item.get("match_label_id")),
            "gold_source_text_en": best.get("source_recommendation_en"),
            "gold_source_text_es": best.get("source_recommendation_es"),
            "gold_target_text_en": best.get("target_recommendation_en"),
            "gold_target_text_es": best.get("target_recommendation_es"),
            "theme": best.get("theme"),
        }
    return lookup


def source_rows_by_id(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = trace.get("matching_inputs", {}).get("source_rows") or []
    return {str(row["source_id"]): row for row in rows if row.get("source_id")}


def queue_rows_for_trace(trace: dict[str, Any], gold_lookup: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    settings = trace.get("settings", {})
    source_language = str(settings.get("source_language") or "unknown")
    language_pair = f"{source_language}-en"
    sources = source_rows_by_id(trace)
    top_matches = trace.get("semantic_candidate_matching", {}).get("top_matches") or {}
    rows: list[dict[str, Any]] = []

    for source_id in sorted(top_matches):
        source = sources.get(source_id, {})
        source_text = source.get("text", "")
        source_theme = source.get("theme", "")
        for rank, match in enumerate(top_matches[source_id], start=1):
            target_id = str(match.get("target_id") or "")
            gold = gold_lookup.get((source_id, target_id), {})
            rows.append(
                {
                    "case_id": trace.get("case", {}).get("case_id"),
                    "run_id": trace.get("run_id"),
                    "language_pair": language_pair,
                    "source_language": source_language,
                    "source_id": source_id,
                    "source_theme": source_theme,
                    "source_text": source_text,
                    "target_id": target_id,
                    "target_text": match.get("target_text", ""),
                    "rank": rank,
                    "semantic_score": match.get("score"),
                    "reranker_score": match.get("reranker_score"),
                    "existing_gold_relevance": gold.get("existing_gold_relevance"),
                    "existing_gold_relevance_score": gold.get("existing_gold_relevance_score"),
                    "gold_match_label_ids": gold.get("gold_match_label_ids", []),
                    "human_relevance": "",
                    "failure_category": "",
                    "review_notes": "",
                }
            )
    return rows


def blind_candidate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gold_fields = {
        "existing_gold_relevance",
        "existing_gold_relevance_score",
        "gold_match_label_ids",
    }
    return [{key: value for key, value in row.items() if key not in gold_fields} for row in rows]


def missing_gold_rows_for_trace(
    trace: dict[str, Any],
    gold_lookup: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    settings = trace.get("settings", {})
    source_language = str(settings.get("source_language") or "unknown")
    language_pair = f"{source_language}-en"
    sources = source_rows_by_id(trace)
    top_matches = trace.get("semantic_candidate_matching", {}).get("top_matches") or {}
    rows: list[dict[str, Any]] = []

    for source_id in sorted(top_matches):
        source = sources.get(source_id, {})
        candidate_target_ids = {str(match.get("target_id") or "") for match in top_matches[source_id]}
        gold_items = [
            (target_id, gold)
            for (gold_source_id, target_id), gold in gold_lookup.items()
            if gold_source_id == source_id and target_id not in candidate_target_ids
        ]
        for target_id, gold in sorted(gold_items):
            rows.append(
                {
                    "case_id": trace.get("case", {}).get("case_id"),
                    "run_id": trace.get("run_id"),
                    "language_pair": language_pair,
                    "source_language": source_language,
                    "source_id": source_id,
                    "source_theme": source.get("theme") or gold.get("theme"),
                    "source_text": source.get("text", ""),
                    "target_id": target_id,
                    "target_text": gold.get("gold_target_text_en") or "",
                    "rank": None,
                    "semantic_score": None,
                    "reranker_score": None,
                    "missing_reason": "gold_not_in_top_k",
                    "existing_gold_relevance": gold.get("existing_gold_relevance"),
                    "existing_gold_relevance_score": gold.get("existing_gold_relevance_score"),
                    "gold_match_label_ids": gold.get("gold_match_label_ids", []),
                    "gold_source_text_en": gold.get("gold_source_text_en"),
                    "gold_source_text_es": gold.get("gold_source_text_es"),
                    "gold_target_text_en": gold.get("gold_target_text_en"),
                    "gold_target_text_es": gold.get("gold_target_text_es"),
                    "failure_category": "",
                    "review_notes": "",
                }
            )
    return rows


def validate_rows(candidate_rows: list[dict[str, Any]], enriched_rows: list[dict[str, Any]], missing_rows: list[dict[str, Any]]) -> None:
    candidate_keys = [(row["source_id"], row["target_id"], row["language_pair"]) for row in candidate_rows]
    if len(candidate_keys) != len(set(candidate_keys)):
        raise ValueError("Candidate queue contains duplicate source/target/language rows.")
    enriched_keys = [(row["source_id"], row["target_id"], row["language_pair"]) for row in enriched_rows]
    if candidate_keys != enriched_keys:
        raise ValueError("Blinded and enriched candidate queues are not aligned.")
    missing_keys = [(row["source_id"], row["target_id"], row["language_pair"]) for row in missing_rows]
    if len(missing_keys) != len(set(missing_keys)):
        raise ValueError("Missed-gold output contains duplicate source/target/language rows.")
    candidate_key_set = set(candidate_keys)
    overlap = candidate_key_set & set(missing_keys)
    if overlap:
        raise ValueError(f"Missed-gold rows overlap with top-candidate rows: {sorted(overlap)[:5]}")

    leaked_gold_fields = {
        "existing_gold_relevance",
        "existing_gold_relevance_score",
        "gold_match_label_ids",
        "gold_source_text_en",
        "gold_source_text_es",
        "gold_target_text_en",
        "gold_target_text_es",
    }
    for row in candidate_rows:
        leaked = leaked_gold_fields & set(row)
        if leaked:
            raise ValueError(f"Blinded candidate row leaks gold fields: {sorted(leaked)}")
        if not row.get("source_text") or not row.get("target_text"):
            raise ValueError("Candidate queue contains a row with missing source or target text.")
        rank = row.get("rank")
        if not isinstance(rank, int) or rank < 1:
            raise ValueError(f"Candidate queue contains invalid rank: {rank!r}")
        if row.get("human_relevance") != "" or row.get("failure_category") != "" or row.get("review_notes") != "":
            raise ValueError("Candidate queue human label fields must be blank.")

    for row in enriched_rows:
        if not row.get("source_text") or not row.get("target_text"):
            raise ValueError("Enriched candidate queue contains a row with missing source or target text.")
        rank = row.get("rank")
        if not isinstance(rank, int) or rank < 1:
            raise ValueError(f"Enriched candidate queue contains invalid rank: {rank!r}")

    for row in missing_rows:
        if row.get("missing_reason") != "gold_not_in_top_k":
            raise ValueError(f"Missed-gold row has invalid reason: {row.get('missing_reason')!r}")
        if row.get("failure_category") != "" or row.get("review_notes") != "":
            raise ValueError("Missed-gold review fields must be blank.")
        if not row.get("existing_gold_relevance"):
            raise ValueError("Missed-gold row is missing existing gold relevance.")
        if row.get("rank") is not None or row.get("semantic_score") is not None:
            raise ValueError("Missed-gold rows must not have candidate rank or semantic score.")
        if not row.get("target_text"):
            raise ValueError("Missed-gold row is missing target text.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-links", type=Path, default=DEFAULT_GOLD_LINKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--enriched-output", type=Path, default=DEFAULT_ENRICHED_OUTPUT)
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_MISSING_OUTPUT)
    parser.add_argument("--trace", type=Path, action="append", dest="traces")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trace_paths = args.traces or DEFAULT_TRACES
    gold_lookup = gold_link_lookup(read_jsonl(args.gold_links))
    enriched_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for trace_path in trace_paths:
        trace = read_json(trace_path)
        enriched_rows.extend(queue_rows_for_trace(trace, gold_lookup))
        missing_rows.extend(missing_gold_rows_for_trace(trace, gold_lookup))

    enriched_rows.sort(key=lambda row: (row["source_id"], row["language_pair"], row["rank"], row["target_id"]))
    candidate_rows = blind_candidate_rows(enriched_rows)
    missing_rows.sort(key=lambda row: (row["source_id"], row["language_pair"], row["target_id"]))
    validate_rows(candidate_rows, enriched_rows, missing_rows)
    write_jsonl(args.output, candidate_rows)
    write_jsonl(args.enriched_output, enriched_rows)
    write_jsonl(args.missing_output, missing_rows)

    labeled = sum(1 for row in enriched_rows if row["existing_gold_relevance"])
    print(f"wrote {len(candidate_rows)} blinded candidate rows to {args.output}")
    print(f"wrote {len(enriched_rows)} enriched candidate rows to {args.enriched_output}")
    print(f"existing positive gold labels attached in enriched output: {labeled}")
    print(f"wrote {len(missing_rows)} missed gold rows to {args.missing_output}")


if __name__ == "__main__":
    main()
