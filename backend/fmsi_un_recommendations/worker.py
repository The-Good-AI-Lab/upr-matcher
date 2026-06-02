from __future__ import annotations

import json
import multiprocessing
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from .db import get_database
from .recommendation_processing import (
    extract_fmsi_text_recommendations,
    extract_un_recommendation_rows,
)
from .reranker import RecommendationReranker
from .settings import Settings
from .similarity_search import (
    Recommendation as FmsiRecommendation,
)
from .similarity_search import (
    embed_fmsi_recommendations,
    embed_un_recommendations,
    match_recommendation_vectors,
)
from .utils import read_text_file


def _build_matches(
    un_doc: Path,
    fmsi_pdf: Path,
    threshold: float,
    report: Callable[[float, str], None] | None = None,
    rerank_candidate_limit: int = 30,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[FmsiRecommendation],
]:
    un_rows = _load_un_rows(un_doc)
    fmsi_markdown = read_text_file(fmsi_pdf)
    return _build_matches_from_text(
        un_rows,
        fmsi_markdown,
        threshold,
        report,
        rerank_candidate_limit,
    )


def _build_matches_from_text(
    un_rows: list[dict[str, Any]],
    fmsi_markdown: str,
    threshold: float,
    report: Callable[[float, str], None] | None = None,
    rerank_candidate_limit: int = 30,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[FmsiRecommendation],
]:
    if report:
        report(20, "Reading the UPR recommendations")
    embedded_un = embed_un_recommendations(un_rows)
    if report:
        report(35, "Understanding UPR recommendations")

    fmsi_recommendations = extract_fmsi_text_recommendations(fmsi_markdown)
    if report:
        report(45, "Reading the FMSI recommendations")
    embedded_fmsi = embed_fmsi_recommendations(fmsi_recommendations)
    if report:
        report(55, "Comparing recommendations")

    raw_matches = match_recommendation_vectors(embedded_fmsi, embedded_un, threshold=threshold)
    logger.info("Semantic similarity returned {} matches", len(raw_matches))

    grouped_matches: dict[int, list[dict[str, Any]]] = {}
    for match in raw_matches:
        grouped_matches.setdefault(match["source_index"], []).append(match)

    if raw_matches:
        if report:
            report(70, "Prioritizing the best matches")
        try:
            reranker = RecommendationReranker(min_k=1, max_k=10)
            matches: list[dict[str, Any]] = []
            for group in grouped_matches.values():
                limited_group = sorted(group, key=lambda item: item["score"], reverse=True)[:rerank_candidate_limit]
                fmsi_text = limited_group[0]["source_text"]
                candidate_texts = [m["target_text"] for m in limited_group]
                rerank_results = reranker.rerank([fmsi_text], candidate_texts)
                if not rerank_results:
                    matches.extend({**match} for match in limited_group)
                    continue

                logger.info(
                    "Reranker kept {} matches for source '{}'",
                    len(rerank_results),
                    fmsi_text[:80].replace("\n", " "),
                )
                for rerank_result in rerank_results:
                    original_match = limited_group[rerank_result.candidate_index]
                    matches.append(
                        {
                            **original_match,
                            "reranker_score": rerank_result.reranker_score,
                        }
                    )
        except Exception as e:
            logger.warning("Reranking failed ({}), using semantic similarity matches only", e)
            matches = [{**match} for match in raw_matches]
    else:
        matches = []

    if report:
        report(80, "Summarizing the findings")
    return embedded_un, embedded_fmsi, matches, fmsi_recommendations


def _load_un_rows(un_doc: Path) -> list[dict[str, str]]:
    if un_doc.suffix.lower() == ".json":
        rows = json.loads(un_doc.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("UPR rows JSON must be a list.")
        return [{str(key): str(value) for key, value in row.items()} for row in rows if isinstance(row, dict)]
    return extract_un_recommendation_rows(un_doc)


def _execute_job(job_id: str) -> None:
    """
    Runs the full ML pipeline for a single job.

    Intentionally designed to run inside a subprocess so that parser/client
    memory is released when the process exits — even after a SIGKILL (OOM).
    The parent loop stays alive to pick up the next job.
    """
    settings = Settings()
    db = get_database(settings)
    job = db.get_job(job_id)
    if job is None:
        logger.error("Job {} not found in DB", job_id)
        return

    def report(percent: float, message: str) -> None:
        try:
            db.update_job_progress(job_id, percent, message)
        except Exception:
            logger.opt(exception=True).warning("Could not update progress for job {}", job_id)

    try:
        report(10, "Inputs received. Getting them ready.")
        logger.info(
            "Starting match pipeline for job {}: extract → embed → match (threshold={})",
            job_id,
            settings.match_threshold,
        )
        if job.source_text is not None and job.reference_rows is not None:
            embedded_un, embedded_fmsi, matches, _ = _build_matches_from_text(
                job.reference_rows,
                job.source_text,
                settings.match_threshold,
                report,
                settings.rerank_candidate_limit,
            )
        elif job.reference_path and job.source_path:
            embedded_un, embedded_fmsi, matches, _ = _build_matches(
                Path(job.reference_path),
                Path(job.source_path),
                settings.match_threshold,
                report,
                settings.rerank_candidate_limit,
            )
        else:
            raise ValueError("Job is missing text payloads.")
        for match in matches:
            match.setdefault("match_id", str(uuid.uuid4()))

        if not settings.store_embeddings:
            for row in embedded_un:
                row.pop("embedding", None)
            for row in embedded_fmsi:
                row.pop("embedding", None)

        report(92, "Saving your results")
        prediction_id = db.save_prediction(
            input_un_path=job.reference_path,
            input_fmsi_path=job.source_path,
            un_rows=embedded_un,
            fmsi_rows=embedded_fmsi,
            matches=matches,
        )
        db.complete_job(job_id, prediction_id)
        logger.info("Job {} completed, prediction_id={}", job_id, prediction_id)
    except Exception as exc:
        logger.opt(exception=True).error("Job {} failed", job_id)
        try:
            db.fail_job(job_id, str(exc))
        except Exception:
            logger.opt(exception=True).error(
                "Could not mark job {} as failed — job may be stuck in processing",
                job_id,
            )


STALE_JOB_TIMEOUT_SECONDS = 3600  # 1 hour


def run_worker() -> None:
    settings = Settings()
    db = get_database(settings)
    logger.info("Worker started, polling for pending jobs every 2s")

    consecutive_errors = 0

    while True:
        try:
            expired = db.fail_stale_jobs(STALE_JOB_TIMEOUT_SECONDS)
            if expired:
                logger.warning("Marked {} stale job(s) as failed (no progress for >1h)", expired)
        except Exception:
            logger.opt(exception=True).warning("Could not expire stale jobs")

        try:
            job = db.claim_next_job()
        except Exception:
            consecutive_errors += 1
            backoff = min(2**consecutive_errors, 60)
            logger.opt(exception=True).error(
                "Failed to poll for jobs (attempt {}), retrying in {}s",
                consecutive_errors,
                backoff,
            )
            time.sleep(backoff)
            continue

        consecutive_errors = 0

        if job is None:
            time.sleep(2)
            continue

        logger.info("Picked up job {}, user={}", job.id, job.user_email)

        # Each job runs in its own subprocess so any native parser/model-client
        # memory is released between jobs.
        proc = multiprocessing.Process(
            target=_execute_job,
            args=(job.id,),
            daemon=True,
        )
        proc.start()
        proc.join()

        if proc.exitcode != 0:
            logger.error(
                "Job {} subprocess exited with code {} (likely OOM kill)",
                job.id,
                proc.exitcode,
            )
            try:
                db.fail_job(
                    job.id,
                    f"Processing was killed by the system (exit {proc.exitcode}). "
                    "The server may be running low on memory — please try again.",
                )
            except Exception:
                logger.opt(exception=True).error("Could not mark job {} as failed after subprocess crash", job.id)
