#!/usr/bin/env python3
"""Run staged AI evals for the UPR matcher pipeline on real documents."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_TRACE_ROOT = REPO_ROOT / "evals/traces/live"
DEFAULT_REPORT_ROOT = REPO_ROOT / "evals/reports/live"
DEFAULT_CASE_ID = "costa_rica_2024"
DEFAULT_GOLD_SOURCES = REPO_ROOT / "evals/gold/costa_rica_2024_source_recommendations.jsonl"
DEFAULT_GOLD_LINKS = REPO_ROOT / "evals/gold/costa_rica_2024_match_links.jsonl"
DEFAULT_VALIDATION_ROOT = (
    REPO_ROOT.parent / "un-recommendations" / "data" / "fmsi-poc-data" / "validation"
)
VALIDATION_ROOT = Path(os.environ.get("UPR_VALIDATION_ROOT", DEFAULT_VALIDATION_ROOT)).resolve()


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


_load_env_file(BACKEND_ROOT / ".env")
sys.path.insert(0, str(BACKEND_ROOT))

from fmsi_un_recommendations.recommendation_processing import (  # noqa: E402
    DEFAULT_CHUNK_CHAR_LIMIT,
    DEFAULT_PROMPT_PATH,
    Recommendation as ExtractionRecommendation,
    _chunk_text,
    extract_un_recommendation_rows,
)
from fmsi_un_recommendations.openrouter import rerank_openrouter  # noqa: E402
from fmsi_un_recommendations.settings import Settings  # noqa: E402
from fmsi_un_recommendations.similarity_search import (  # noqa: E402
    Recommendation as MatchRecommendation,
    embed_fmsi_recommendations,
    embed_un_recommendations,
    match_recommendation_vectors,
)
from fmsi_un_recommendations.utils import get_openrouter_client, read_text_file  # noqa: E402


@dataclass(slots=True)
class BudgetTracker:
    """Conservative per-run OpenRouter budget guard.

    OpenRouter models have model-specific pricing. The CLI exposes the assumed
    prices so runs can be made more conservative without code changes.
    """

    max_cost_usd: float
    prompt_usd_per_1m: float
    completion_usd_per_1m: float
    calls: int = 0
    estimated_cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def reserve(self, prompt_text: str, max_completion_tokens: int) -> None:
        prompt_tokens = estimate_tokens(prompt_text)
        estimated = self._cost(prompt_tokens, max_completion_tokens)
        if self.estimated_cost_usd + estimated > self.max_cost_usd:
            raise RuntimeError(
                "OpenRouter budget would be exceeded before request: "
                f"current=${self.estimated_cost_usd:.4f}, request_estimate=${estimated:.4f}, "
                f"cap=${self.max_cost_usd:.4f}"
            )

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.estimated_cost_usd += self._cost(prompt_tokens, completion_tokens)

    def _cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens * self.prompt_usd_per_1m / 1_000_000
            + completion_tokens * self.completion_usd_per_1m / 1_000_000
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "max_cost_usd": self.max_cost_usd,
            "prompt_usd_per_1m": self.prompt_usd_per_1m,
            "completion_usd_per_1m": self.completion_usd_per_1m,
        }


@dataclass(slots=True)
class EvalCase:
    case_id: str
    source_pdf: Path
    reference_doc: Path
    gold_sources: list[dict[str, Any]]
    gold_links: list[dict[str, Any]]


@dataclass(slots=True)
class StageTimer:
    timings: dict[str, float] = field(default_factory=dict)

    def run(self, name: str, func: Any) -> Any:
        start = time.perf_counter()
        try:
            return func()
        finally:
            self.timings[name] = round(time.perf_counter() - start, 3)


def estimate_tokens(text: str) -> int:
    # Good enough for budget guards; exact provider tokenization is model-specific.
    return max(1, math.ceil(len(text) / 4))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve_validation_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() and path.exists():
        return path
    if path.is_absolute():
        return VALIDATION_ROOT / path.name
    return VALIDATION_ROOT / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_set(text: str) -> set[str]:
    return {token for token in normalize_text(text).split() if len(token) > 2}


def token_jaccard(left: str, right: str) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def extract_target_id(text: str) -> str | None:
    match = re.search(r"\b(\d{2,3}\.\d{1,3})\b", text)
    return match.group(1) if match else None


def target_id_for_row(row: dict[str, Any]) -> str | None:
    preferred_keys = (
        "Recommendation and recommending State",
        "Recommendation",
        "recommendation",
        "target_recommendation",
    )
    for key in preferred_keys:
        value = row.get(key)
        if isinstance(value, str):
            target_id = extract_target_id(value)
            if target_id:
                return target_id
    for value in row.values():
        if isinstance(value, str):
            target_id = extract_target_id(value)
            if target_id:
                return target_id
    return None


def row_text(row: dict[str, Any]) -> str:
    parts = []
    for key, value in row.items():
        if key == "embedding" or value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            parts.append(f"{key}: {cleaned}")
    return "\n".join(parts)


def load_costa_rica_case(args: argparse.Namespace) -> EvalCase:
    gold_sources = read_jsonl(Path(args.gold_sources))
    gold_links = read_jsonl(Path(args.gold_links))
    if not gold_sources:
        raise ValueError(f"No gold source recommendations found in {args.gold_sources}")
    if not gold_links:
        raise ValueError(f"No gold match links found in {args.gold_links}")

    source_pdf = resolve_validation_path(str(gold_sources[0]["source_file"]))
    reference_doc = resolve_validation_path(str(gold_links[0]["reference_file"]))
    return EvalCase(
        case_id=args.case_id,
        source_pdf=source_pdf,
        reference_doc=reference_doc,
        gold_sources=gold_sources,
        gold_links=gold_links,
    )


def build_gold_source_recommendations(
    gold_sources: list[dict[str, Any]],
    *,
    language: str,
    limit: int | None,
) -> tuple[list[MatchRecommendation], list[str], list[dict[str, Any]]]:
    rows = gold_sources[:limit] if limit else gold_sources
    recs: list[MatchRecommendation] = []
    source_ids: list[str] = []
    compact_rows: list[dict[str, Any]] = []
    field = "source_recommendation_en" if language == "en" else "source_recommendation_es"
    for row in rows:
        text = row.get(field) or row.get("source_recommendation_en") or row.get("source_recommendation_es")
        if not text:
            continue
        source_ids.append(row["source_id"])
        compact_rows.append(
            {
                "source_id": row["source_id"],
                "theme": row.get("theme", ""),
                "text": text,
                "language": language,
            }
        )
        recs.append(
            MatchRecommendation(
                recommendation=text,
                domain=row.get("theme", ""),
                beneficiaries="",
                theme=row.get("theme", ""),
            )
        )
    return recs, source_ids, compact_rows


def parse_llm_recommendations(raw_content: str) -> list[ExtractionRecommendation]:
    content = raw_content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    if not content.startswith("["):
        start = content.find("[")
        end = content.rfind("]")
        if start >= 0 and end > start:
            content = content[start : end + 1]
    payload = json.loads(content)
    if not isinstance(payload, list):
        raise ValueError("Expected the extraction model to return a JSON list")
    return [ExtractionRecommendation.model_validate(item) for item in payload]


def extract_fmsi_with_openrouter(
    case: EvalCase,
    args: argparse.Namespace,
    budget: BudgetTracker,
) -> dict[str, Any]:
    if not args.allow_openrouter:
        raise RuntimeError("Refusing live OpenRouter calls without --allow-openrouter")
    settings = Settings()
    prompt_path = Path(args.prompt_path)
    if not prompt_path.is_absolute():
        prompt_path = BACKEND_ROOT / prompt_path
    system_prompt = prompt_path.read_text(encoding="utf-8")
    document_text = read_text_file(case.source_pdf)
    chunks = _chunk_text(document_text, args.max_chunk_chars)
    if args.max_llm_chunks:
        chunks = chunks[: args.max_llm_chunks]

    client = get_openrouter_client()
    recommendations: list[ExtractionRecommendation] = []
    raw_responses: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        user_prompt = (
            f"Document chunk {index} of {len(chunks)}:\n"
            f"{chunk}\n\nReturn only the JSON object specified by the system instructions."
        )
        prompt_for_budget = system_prompt + "\n\n" + user_prompt
        budget.reserve(prompt_for_budget, args.max_completion_tokens)
        response = client.chat.completions.create(
            model=args.openrouter_model or settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
            temperature=0,
            max_tokens=args.max_completion_tokens,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        if usage:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or estimate_tokens(prompt_for_budget))
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or estimate_tokens(content))
        else:
            prompt_tokens = estimate_tokens(prompt_for_budget)
            completion_tokens = estimate_tokens(content)
        budget.record(prompt_tokens, completion_tokens)
        chunk_recommendations = parse_llm_recommendations(content)
        recommendations.extend(chunk_recommendations)
        raw_responses.append(
            {
                "chunk_index": index,
                "chunk_chars": len(chunk),
                "recommendations_count": len(chunk_recommendations),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "raw_content": content,
            }
        )

    deduped: list[ExtractionRecommendation] = []
    seen: set[str] = set()
    for recommendation in recommendations:
        cleaned = re.sub(r"\s+", " ", recommendation.recommendation).strip()
        key = normalize_text(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(recommendation.model_copy(update={"recommendation": cleaned}, deep=True))
    return {
        "recommendations": deduped,
        "chunks": raw_responses,
        "document_chars": len(document_text),
    }


def evaluate_llm_extraction(
    extracted: list[ExtractionRecommendation],
    gold_sources: list[dict[str, Any]],
    *,
    language: str,
    similarity_threshold: float,
) -> dict[str, Any]:
    gold_field = "source_recommendation_en" if language == "en" else "source_recommendation_es"
    gold_texts = [(row["source_id"], row.get(gold_field) or row.get("source_recommendation_en", "")) for row in gold_sources]
    extracted_texts = [rec.recommendation for rec in extracted]

    best_by_gold = []
    matched_gold = 0
    for source_id, gold_text in gold_texts:
        best_score = max((token_jaccard(gold_text, text) for text in extracted_texts), default=0.0)
        if best_score >= similarity_threshold:
            matched_gold += 1
        best_by_gold.append({"source_id": source_id, "best_similarity": round(best_score, 4)})

    duplicate_keys = [
        key for key, count in Counter(normalize_text(text) for text in extracted_texts if text.strip()).items() if count > 1
    ]
    return {
        "expected_gold_count": len(gold_sources),
        "observed_count": len(extracted),
        "gold_coverage_at_threshold": round(matched_gold / len(gold_sources), 4) if gold_sources else 0.0,
        "similarity_threshold": similarity_threshold,
        "average_best_similarity": round(
            sum(item["best_similarity"] for item in best_by_gold) / len(best_by_gold), 4
        )
        if best_by_gold
        else 0.0,
        "duplicate_recommendation_count": len(duplicate_keys),
        "best_by_gold": best_by_gold,
    }


def build_gold_links(gold_links: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    links: dict[str, dict[str, int]] = defaultdict(dict)
    for link in gold_links:
        source_id = link.get("source_id")
        target_id = link.get("target_recommendation_id")
        if source_id and target_id:
            links[source_id][target_id] = max(int(link.get("relevance_score", 1)), links[source_id].get(target_id, 0))
    return dict(links)


def dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(relevances))


def ranking_metrics(
    rankings: dict[str, list[str]],
    gold_links: dict[str, dict[str, int]],
    *,
    ks: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, Any]:
    per_source: dict[str, Any] = {}
    aggregate: dict[str, list[float]] = defaultdict(list)
    for source_id, expected in gold_links.items():
        expected_ids = set(expected)
        # A recommendation ID can appear in more than one parsed table row.
        # Metrics operate on IDs, so preserve only the highest-ranked occurrence.
        ranking = list(dict.fromkeys(target_id for target_id in rankings.get(source_id, []) if target_id))
        source_metrics: dict[str, Any] = {
            "expected_count": len(expected_ids),
            "returned_count": len(ranking),
        }

        first_rank = None
        for index, target_id in enumerate(ranking, start=1):
            if target_id in expected_ids:
                first_rank = index
                break
        reciprocal_rank = 1 / first_rank if first_rank else 0.0
        source_metrics["mrr"] = round(reciprocal_rank, 4)
        aggregate["mrr"].append(reciprocal_rank)

        for k in ks:
            top_k = ranking[:k]
            hits = [target_id for target_id in top_k if target_id in expected_ids]
            recall = len(set(hits)) / len(expected_ids) if expected_ids else 0.0
            precision = len(hits) / len(top_k) if top_k else 0.0
            hit_rate = 1.0 if hits else 0.0
            rels = [expected.get(target_id, 0) for target_id in top_k]
            ideal_rels = sorted(expected.values(), reverse=True)[:k]
            ndcg = dcg(rels) / dcg(ideal_rels) if ideal_rels and dcg(ideal_rels) else 0.0
            source_metrics[f"recall@{k}"] = round(recall, 4)
            source_metrics[f"precision@{k}"] = round(precision, 4)
            source_metrics[f"hit@{k}"] = round(hit_rate, 4)
            source_metrics[f"ndcg@{k}"] = round(ndcg, 4)
            aggregate[f"recall@{k}"].append(recall)
            aggregate[f"precision@{k}"].append(precision)
            aggregate[f"hit@{k}"].append(hit_rate)
            aggregate[f"ndcg@{k}"].append(ndcg)

        per_source[source_id] = source_metrics

    macro = {
        key: round(sum(values) / len(values), 4) if values else 0.0 for key, values in sorted(aggregate.items())
    }
    return {
        "macro": macro,
        "evaluated_sources": len(gold_links),
        "per_source": per_source,
    }


def top_matches_for_trace(
    grouped_matches: dict[str, list[dict[str, Any]]],
    *,
    limit_per_source: int,
) -> dict[str, list[dict[str, Any]]]:
    trace: dict[str, list[dict[str, Any]]] = {}
    for source_id, matches in grouped_matches.items():
        rows = []
        for match in matches[:limit_per_source]:
            target_row = match.get("target_row") or {}
            rows.append(
                {
                    "target_id": match.get("_eval_target_id"),
                    "score": round(float(match.get("score", 0.0)), 6),
                    "reranker_score": round(float(match["reranker_score"]), 6)
                    if match.get("reranker_score") is not None
                    else None,
                    "target_text": row_text(target_row)[:1000],
                }
            )
        trace[source_id] = rows
    return trace


def group_matches_by_source(matches: list[dict[str, Any]], source_ids: list[str], target_ids: list[str | None]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        source_index = int(match["source_index"])
        target_index = int(match["target_index"])
        match["_eval_source_id"] = source_ids[source_index] if source_index < len(source_ids) else f"source_{source_index}"
        match["_eval_target_id"] = target_ids[target_index] if target_index < len(target_ids) else None
        grouped[match["_eval_source_id"]].append(match)
    for source_matches in grouped.values():
        source_matches.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return dict(grouped)


def ranking_from_grouped(grouped: dict[str, list[dict[str, Any]]], *, k: int | None = None) -> dict[str, list[str]]:
    rankings: dict[str, list[str]] = {}
    for source_id, matches in grouped.items():
        selected = matches[:k] if k else matches
        rankings[source_id] = [match.get("_eval_target_id") for match in selected if match.get("_eval_target_id")]
    return rankings


def rerank_grouped_matches(
    grouped: dict[str, list[dict[str, Any]]],
    *,
    candidate_top_k: int,
    reranker_top_k: int,
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    reranked: dict[str, list[dict[str, Any]]] = {}
    try:
        for source_id, matches in grouped.items():
            candidates = matches[:candidate_top_k]
            if not candidates:
                reranked[source_id] = []
                continue
            source_text = candidates[0].get("source_text", "")
            candidate_texts = [match.get("target_text", "") for match in candidates]
            rerank_results = rerank_openrouter(
                source_text,
                candidate_texts,
                top_n=min(reranker_top_k, len(candidate_texts)),
            )
            source_results = []
            for result in rerank_results:
                original = dict(candidates[result.candidate_index])
                original["reranker_score"] = result.relevance_score
                source_results.append(original)
            source_results.sort(key=lambda item: item.get("reranker_score", 0.0), reverse=True)
            reranked[source_id] = source_results
    except Exception as exc:  # pragma: no cover - environment/model dependent
        return {}, f"Reranking failed: {exc}"
    return reranked, None


def require_openrouter_opt_ins(args: argparse.Namespace, run_settings: Settings) -> None:
    if run_settings.embedding_provider.lower() == "openrouter" and not args.allow_openrouter_embeddings:
        raise RuntimeError("Refusing paid OpenRouter embedding calls without --allow-openrouter-embeddings")
    if (
        not args.skip_reranker
        and run_settings.reranker_provider.lower() == "openrouter"
        and not args.allow_openrouter_reranker
    ):
        raise RuntimeError("Refusing paid OpenRouter reranker calls without --allow-openrouter-reranker")


def evaluate_case(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    timer = StageTimer()
    budget = BudgetTracker(
        max_cost_usd=args.max_cost_usd,
        prompt_usd_per_1m=args.prompt_usd_per_1m,
        completion_usd_per_1m=args.completion_usd_per_1m,
    )

    run_settings = Settings()
    require_openrouter_opt_ins(args, run_settings)

    case = load_costa_rica_case(args)
    if not case.source_pdf.exists():
        raise FileNotFoundError(case.source_pdf)
    if not case.reference_doc.exists():
        raise FileNotFoundError(case.reference_doc)

    source_text = timer.run("source_pdf_text_extraction", lambda: read_text_file(case.source_pdf))
    reference_text = timer.run("reference_text_extraction", lambda: read_text_file(case.reference_doc))
    reference_rows = timer.run("reference_doc_row_extraction", lambda: extract_un_recommendation_rows(case.reference_doc))
    if args.limit_targets:
        reference_rows = reference_rows[: args.limit_targets]
    target_ids = [target_id_for_row(row) for row in reference_rows]
    gold_target_ids = {link["target_recommendation_id"] for link in case.gold_links if link.get("target_recommendation_id")}
    parsed_target_ids = {target_id for target_id in target_ids if target_id}
    raw_text_target_ids = {target_id for target_id in gold_target_ids if target_id in reference_text}
    normalized_source_text = normalize_text(source_text)
    source_gold_field = "source_recommendation_es"
    source_gold_ids_in_text = {
        row["source_id"]
        for row in case.gold_sources
        if normalize_text(row.get(source_gold_field, "")) and normalize_text(row.get(source_gold_field, "")) in normalized_source_text
    }
    all_source_gold_ids = {row["source_id"] for row in case.gold_sources}

    extraction_trace: dict[str, Any] = {
        "source_mode": args.source_mode,
        "live_openrouter": False,
    }
    llm_recommendations: list[ExtractionRecommendation] = []
    if args.source_mode in {"llm", "both"}:
        llm_result = timer.run("llm_fmsi_extraction", lambda: extract_fmsi_with_openrouter(case, args, budget))
        llm_recommendations = llm_result["recommendations"]
        extraction_trace = {
            "source_mode": args.source_mode,
            "live_openrouter": True,
            "document_chars": llm_result["document_chars"],
            "chunks": [
                {
                    "chunk_index": chunk["chunk_index"],
                    "chunk_chars": chunk["chunk_chars"],
                    "recommendations_count": chunk["recommendations_count"],
                    "prompt_tokens": chunk["prompt_tokens"],
                    "completion_tokens": chunk["completion_tokens"],
                }
                for chunk in llm_result["chunks"]
            ],
            "metrics": evaluate_llm_extraction(
                llm_recommendations,
                case.gold_sources,
                language=args.source_language,
                similarity_threshold=args.extraction_similarity_threshold,
            ),
            "recommendations": [
                {
                    "recommendation": rec.recommendation,
                    "domain": rec.domain,
                    "beneficiaries": rec.beneficiaries,
                    "theme": rec.theme,
                }
                for rec in llm_recommendations
            ],
        }

    if args.source_mode in {"gold", "both"}:
        source_recs, source_ids, source_rows = build_gold_source_recommendations(
            case.gold_sources,
            language=args.source_language,
            limit=args.limit_sources or None,
        )
    else:
        source_recs = [
            MatchRecommendation(
                recommendation=rec.recommendation,
                domain=rec.domain,
                beneficiaries=rec.beneficiaries,
                theme=rec.theme,
            )
            for rec in llm_recommendations[: args.limit_sources or None]
        ]
        source_ids = [f"llm_source_{index + 1}" for index in range(len(source_recs))]
        source_rows = [
            {"source_id": source_ids[index], "text": rec.recommendation, "theme": rec.theme, "language": "model_output"}
            for index, rec in enumerate(llm_recommendations[: args.limit_sources or None])
        ]

    embedded_un = timer.run("reference_embedding", lambda: embed_un_recommendations(reference_rows))
    embedded_fmsi = timer.run("source_embedding", lambda: embed_fmsi_recommendations(source_recs))
    raw_matches = timer.run(
        "semantic_candidate_matching",
        lambda: match_recommendation_vectors(embedded_fmsi, embedded_un, threshold=args.match_threshold),
    )
    grouped_semantic = group_matches_by_source(raw_matches, source_ids, target_ids)
    for source_id in source_ids:
        grouped_semantic.setdefault(source_id, [])

    gold_links = build_gold_links(case.gold_links)
    if args.limit_sources:
        allowed_sources = set(source_ids)
        gold_links = {source_id: links for source_id, links in gold_links.items() if source_id in allowed_sources}
    if args.limit_targets:
        allowed_targets = parsed_target_ids
        gold_links = {
            source_id: {target_id: rel for target_id, rel in links.items() if target_id in allowed_targets}
            for source_id, links in gold_links.items()
        }
        gold_links = {source_id: links for source_id, links in gold_links.items() if links}

    semantic_rankings = ranking_from_grouped(grouped_semantic, k=args.candidate_top_k)
    semantic_metrics = ranking_metrics(semantic_rankings, gold_links)

    reranked_grouped: dict[str, list[dict[str, Any]]] = {}
    reranker_error = None
    reranker_metrics: dict[str, Any] | None = None
    if not args.skip_reranker:
        reranked_grouped, reranker_error = timer.run(
            "reranking",
            lambda: rerank_grouped_matches(
                grouped_semantic,
                candidate_top_k=args.candidate_top_k,
                reranker_top_k=args.reranker_top_k,
            ),
        )
        if reranked_grouped:
            reranker_rankings = ranking_from_grouped(reranked_grouped, k=args.reranker_top_k)
            reranker_metrics = ranking_metrics(reranker_rankings, gold_links)

    trace = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "case": {
            "case_id": case.case_id,
            "source_pdf": str(case.source_pdf),
            "reference_doc": str(case.reference_doc),
            "source_file_sha256": sha256_file(case.source_pdf),
            "reference_file_sha256": sha256_file(case.reference_doc),
        },
        "settings": {
            "source_mode": args.source_mode,
            "source_language": args.source_language,
            "match_threshold": args.match_threshold,
            "candidate_top_k": args.candidate_top_k,
            "skip_reranker": args.skip_reranker,
            "allow_openrouter_embeddings": args.allow_openrouter_embeddings,
            "allow_openrouter_reranker": args.allow_openrouter_reranker,
            "reranker_top_k": args.reranker_top_k,
            "limit_sources": args.limit_sources,
            "limit_targets": args.limit_targets,
            "openrouter_model": args.openrouter_model or run_settings.model,
            "embedding_model": run_settings.embedding_model,
            "embedding_provider": getattr(run_settings, "embedding_provider", "fastembed"),
            "reranker_model": getattr(run_settings, "reranker_model", None),
            "reranker_provider": getattr(run_settings, "reranker_provider", None),
        },
        "document_extraction": {
            "source_text_chars": len(source_text),
            "gold_source_recommendations": len(all_source_gold_ids),
            "gold_source_recommendations_present_in_source_text": len(source_gold_ids_in_text),
            "gold_source_text_coverage": round(len(source_gold_ids_in_text) / len(all_source_gold_ids), 4)
            if all_source_gold_ids
            else 0.0,
            "gold_source_ids_missing_from_source_text": sorted(all_source_gold_ids - source_gold_ids_in_text),
            "reference_text_chars": len(reference_text),
            "reference_rows": len(reference_rows),
            "reference_rows_with_target_id": sum(1 for target_id in target_ids if target_id),
            "duplicate_target_ids": {
                target_id: count
                for target_id, count in Counter(target_id for target_id in target_ids if target_id).items()
                if count > 1
            },
            "gold_target_ids": len(gold_target_ids),
            "gold_target_ids_present_in_reference_text": len(raw_text_target_ids),
            "gold_target_id_text_coverage": round(len(raw_text_target_ids) / len(gold_target_ids), 4)
            if gold_target_ids
            else 0.0,
            "gold_target_ids_present_in_reference": len(gold_target_ids & parsed_target_ids),
            "gold_target_id_coverage": round(len(gold_target_ids & parsed_target_ids) / len(gold_target_ids), 4)
            if gold_target_ids
            else 0.0,
            "gold_target_ids_missing_from_parsed_rows": sorted(gold_target_ids - parsed_target_ids),
            "gold_target_ids_missing_from_reference_text": sorted(gold_target_ids - raw_text_target_ids),
        },
        "fmsi_extraction": extraction_trace,
        "matching_inputs": {
            "source_recommendations": len(source_recs),
            "source_rows": source_rows,
            "reference_rows": len(reference_rows),
            "gold_sources_evaluated": len(gold_links),
            "gold_links_evaluated": sum(len(links) for links in gold_links.values()),
        },
        "semantic_candidate_matching": {
            "raw_match_count": len(raw_matches),
            "metrics": semantic_metrics,
            "top_matches": top_matches_for_trace(grouped_semantic, limit_per_source=args.trace_top_matches),
        },
        "reranking": {
            "skipped": args.skip_reranker,
            "error": reranker_error,
            "metrics": reranker_metrics,
            "top_matches": top_matches_for_trace(reranked_grouped, limit_per_source=args.trace_top_matches)
            if reranked_grouped
            else {},
        },
        "openrouter_usage": budget.as_dict(),
        "timings_seconds": timer.timings,
    }
    return trace


def write_outputs(trace: dict[str, Any], args: argparse.Namespace) -> tuple[Path, Path]:
    trace_root = Path(args.trace_root)
    report_root = Path(args.report_root)
    trace_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    run_id = trace["run_id"]
    trace_path = trace_root / f"{run_id}.json"
    report_path = report_root / f"{run_id}.md"
    trace_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown_report(trace, trace_path), encoding="utf-8")
    return trace_path, report_path


def render_metric_block(metrics: dict[str, Any] | None) -> list[str]:
    if not metrics:
        return ["- No metrics recorded."]
    macro = metrics.get("macro", {})
    lines = [f"- Evaluated sources: {metrics.get('evaluated_sources', 0)}"]
    for key in ("hit@1", "hit@3", "hit@5", "hit@10", "recall@1", "recall@3", "recall@5", "recall@10", "mrr"):
        if key in macro:
            lines.append(f"- `{key}`: {macro[key]}")
    return lines


def render_markdown_report(trace: dict[str, Any], trace_path: Path) -> str:
    doc = trace["document_extraction"]
    fmsi = trace["fmsi_extraction"]
    usage = trace["openrouter_usage"]
    lines = [
        f"# AI Pipeline Eval: {trace['case']['case_id']}",
        "",
        f"- Run ID: `{trace['run_id']}`",
        f"- Trace JSON: `{trace_path}`",
        f"- Source mode: `{trace['settings']['source_mode']}`",
        f"- Source language: `{trace['settings']['source_language']}`",
        f"- Embedding model: `{trace['settings'].get('embedding_model', 'unknown')}`",
        f"- Embedding provider: `{trace['settings'].get('embedding_provider', 'unknown')}`",
        f"- OpenRouter extraction calls: {usage['calls']} (~${usage['estimated_cost_usd']:.6f} estimated)",
        "- Embedding and reranker costs are separately opt-in and are not included in the extraction budget.",
        "",
        "## Document Extraction",
        "",
        f"- Source text chars: {doc['source_text_chars']}",
        f"- Gold source recommendation coverage in source text: {doc['gold_source_text_coverage']}",
        f"- Reference rows: {doc['reference_rows']}",
        f"- Rows with target IDs: {doc['reference_rows_with_target_id']}",
        f"- Gold target ID coverage in raw reference text: {doc['gold_target_id_text_coverage']}",
        f"- Gold target ID coverage in parsed rows: {doc['gold_target_id_coverage']}",
        "",
        "## FMSI Extraction",
        "",
    ]
    if fmsi.get("live_openrouter"):
        metrics = fmsi.get("metrics", {})
        lines.extend(
            [
                f"- LLM extracted recommendations: {metrics.get('observed_count', 0)}",
                f"- Expected gold recommendations: {metrics.get('expected_gold_count', 0)}",
                f"- Gold coverage at similarity threshold: {metrics.get('gold_coverage_at_threshold', 0.0)}",
                f"- Average best similarity: {metrics.get('average_best_similarity', 0.0)}",
            ]
        )
    else:
        lines.append("- Live extraction was not run for this eval.")

    lines.extend(
        [
            "",
            "## Semantic Candidate Matching",
            "",
            f"- Raw matches: {trace['semantic_candidate_matching']['raw_match_count']}",
            *render_metric_block(trace["semantic_candidate_matching"].get("metrics")),
            "",
            "## Reranking",
            "",
        ]
    )
    if trace["reranking"].get("skipped"):
        lines.append("- Reranking skipped by CLI flag.")
    elif trace["reranking"].get("error"):
        lines.append(f"- Reranking error: {trace['reranking']['error']}")
    else:
        lines.extend(render_metric_block(trace["reranking"].get("metrics")))

    lines.extend(
        [
            "",
            "## Timings",
            "",
        ]
    )
    for name, seconds in trace["timings_seconds"].items():
        lines.append(f"- `{name}`: {seconds}s")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID, choices=[DEFAULT_CASE_ID])
    parser.add_argument("--gold-sources", default=str(DEFAULT_GOLD_SOURCES))
    parser.add_argument("--gold-links", default=str(DEFAULT_GOLD_LINKS))
    parser.add_argument("--source-mode", choices=["gold", "llm", "both"], default="gold")
    parser.add_argument("--source-language", choices=["es", "en"], default="es")
    parser.add_argument("--limit-sources", type=int, default=0)
    parser.add_argument("--limit-targets", type=int, default=0)
    parser.add_argument("--match-threshold", type=float, default=0.0)
    parser.add_argument("--candidate-top-k", type=int, default=30)
    parser.add_argument("--skip-reranker", action="store_true")
    parser.add_argument("--reranker-top-k", type=int, default=10)
    parser.add_argument("--trace-top-matches", type=int, default=10)
    parser.add_argument("--allow-openrouter", action="store_true")
    parser.add_argument("--allow-openrouter-embeddings", action="store_true")
    parser.add_argument("--allow-openrouter-reranker", action="store_true")
    parser.add_argument("--openrouter-model", default=None)
    parser.add_argument("--max-cost-usd", type=float, default=10.0)
    parser.add_argument("--prompt-usd-per-1m", type=float, default=1.0)
    parser.add_argument("--completion-usd-per-1m", type=float, default=1.0)
    parser.add_argument("--max-llm-chunks", type=int, default=1)
    parser.add_argument("--max-chunk-chars", type=int, default=DEFAULT_CHUNK_CHAR_LIMIT)
    parser.add_argument("--max-completion-tokens", type=int, default=4096)
    parser.add_argument("--extraction-similarity-threshold", type=float, default=0.35)
    parser.add_argument("--prompt-path", default=str(DEFAULT_PROMPT_PATH))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--trace-root", default=str(DEFAULT_TRACE_ROOT))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trace = evaluate_case(args)
    trace_path, report_path = write_outputs(trace, args)
    print(f"wrote trace: {trace_path}")
    print(f"wrote report: {report_path}")
    semantic_macro = trace["semantic_candidate_matching"]["metrics"]["macro"]
    print(
        "semantic "
        f"hit@10={semantic_macro.get('hit@10', 0.0)} "
        f"recall@10={semantic_macro.get('recall@10', 0.0)} "
        f"mrr={semantic_macro.get('mrr', 0.0)}"
    )
    if trace["reranking"].get("metrics"):
        rerank_macro = trace["reranking"]["metrics"]["macro"]
        print(
            "rerank "
            f"hit@10={rerank_macro.get('hit@10', 0.0)} "
            f"recall@10={rerank_macro.get('recall@10', 0.0)} "
            f"mrr={rerank_macro.get('mrr', 0.0)}"
        )
    if trace["openrouter_usage"]["calls"]:
        print(f"openrouter estimated_cost=${trace['openrouter_usage']['estimated_cost_usd']:.6f}")


if __name__ == "__main__":
    main()
