from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, ConfigDict

from .db import DatabaseAdapter, get_database
from .progress import progress_tracker
from .recommendation_processing import (
    extract_fmsi_pdf_recommendations,
    extract_un_recommendation_rows,
)
from .settings import Settings
from .similarity_search import (
    Recommendation as FmsiRecommendation,
)
from .similarity_search import (
    embed_fmsi_recommendations,
    embed_un_recommendations,
    match_recommendation_vectors,
)

UPLOAD_ROOT = Path("data/uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


class MatchEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    match_id: str
    score: float
    reranker_score: float | None = None
    source_index: int
    source_text: str
    source_row: dict[str, Any] | None = None
    target_index: int
    target_text: str
    target_row: dict[str, Any]


class CategoryCount(BaseModel):
    name: str
    count: int


class MatchResponse(BaseModel):
    prediction_id: str
    matches: list[MatchEntry]
    upr_total_recommendations: int
    upr_category_counts: list[CategoryCount]
    fmsi_total_recommendations: int
    fmsi_category_counts: list[CategoryCount]


class FeedbackRequest(BaseModel):
    prediction_id: str
    match_id: str
    thumb_up: bool
    notes: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str


class ProgressStatus(BaseModel):
    job_id: str
    status: Literal["pending", "processing", "completed", "failed", "unknown"]
    percent: float
    message: str


def _get_settings() -> Settings:
    return Settings()


async def _persist_upload(upload: UploadFile, category: str) -> Path:
    destination_dir = UPLOAD_ROOT / category
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(upload.filename or f"{category}.bin").name
    destination_path = destination_dir / f"{uuid.uuid4()}_{filename}"
    with destination_path.open("wb") as buffer:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            buffer.write(chunk)
    await upload.close()
    return destination_path


def _extract_upr_theme(row: dict[str, Any]) -> str:
    for key in (
        "Theme",
        "theme",
        "Human rights themes and groups of persons",
        "Human rights themes",
        "Human rights themes & groups of persons",
        "domain",
    ):
        value = row.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return "Uncategorized"


def _summarize_upr_categories(rows: list[dict[str, Any]]) -> list[CategoryCount]:
    counts: dict[str, int] = {}
    for row in rows:
        name = _extract_upr_theme(row)
        counts[name] = counts.get(name, 0) + 1
    return [
        CategoryCount(name=name, count=count)
        for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _summarize_fmsi_categories(
    recommendations: list[dict[str, Any]] | list[FmsiRecommendation],
) -> list[CategoryCount]:
    counts: dict[str, int] = {}
    for rec in recommendations:
        if hasattr(rec, "theme"):
            name = rec.theme or getattr(rec, "domain", None) or "Uncategorized"
        else:
            name = rec.get("theme") or rec.get("domain") or "Uncategorized"
        cleaned = name.strip() if isinstance(name, str) else ""
        key = cleaned or "Uncategorized"
        counts[key] = counts.get(key, 0) + 1
    return [
        CategoryCount(name=name, count=count)
        for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _build_matches(
    un_doc: Path,
    fmsi_pdf: Path,
    threshold: float,
    job_id: str | None = None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[FmsiRecommendation],
]:
    def _report(percent: float, message: str) -> None:
        if job_id:
            progress_tracker.update(job_id, percent, message)

    def _process_un() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        un_rows = extract_un_recommendation_rows(un_doc)
        _report(20, "Reading the UPR document")
        embedded_un = embed_un_recommendations(un_rows)
        _report(35, "Understanding UPR recommendations")
        return un_rows, embedded_un

    def _process_fmsi() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        fmsi_recommendations = extract_fmsi_pdf_recommendations(fmsi_pdf)
        _report(25, "Reading the FMSI document")
        embedded_fmsi = embed_fmsi_recommendations(fmsi_recommendations)
        _report(45, "Understanding FMSI recommendations")
        return fmsi_recommendations, embedded_fmsi

    with ThreadPoolExecutor(max_workers=2) as executor:
        un_future = executor.submit(_process_un)
        fmsi_future = executor.submit(_process_fmsi)
        un_rows, embedded_un = un_future.result()
        fmsi_recommendations, embedded_fmsi = fmsi_future.result()

    _report(55, "Comparing recommendations")
    # Step 1: Semantic similarity matching
    raw_matches = match_recommendation_vectors(embedded_fmsi, embedded_un, threshold=threshold)
    logger.info("Semantic similarity returned {} matches", len(raw_matches))

    grouped_matches: dict[int, list[dict[str, Any]]] = {}
    for match in raw_matches:
        grouped_matches.setdefault(match["source_index"], []).append(match)

    # Step 2: Rerank matches using cross-encoder (lazy import to avoid startup issues)
    if raw_matches:
        _report(70, "Prioritizing the best matches")
        try:
            from .reranker import RecommendationReranker

            reranker = RecommendationReranker(min_k=1, max_k=10)
            matches: list[dict[str, Any]] = []
            for group in grouped_matches.values():
                fmsi_text = group[0]["source_text"]
                candidate_texts = [m["target_text"] for m in group]
                rerank_results = reranker.rerank([fmsi_text], candidate_texts)
                if not rerank_results:
                    matches.extend({**match} for match in group)
                    continue

                logger.info(
                    "Reranker kept {} matches for source '{}'",
                    len(rerank_results),
                    fmsi_text[:80].replace("\n", " "),
                )
                for rerank_result in rerank_results:
                    original_match = group[rerank_result.candidate_index]
                    match_with_reranker = {
                        **original_match,
                        "reranker_score": rerank_result.reranker_score,
                    }
                    matches.append(match_with_reranker)
        except Exception as e:
            logger.warning("Reranking failed ({}), using semantic similarity matches only", e)
            matches = [{**match} for match in raw_matches]
    else:
        matches = []

    _report(80, "Summarizing the findings")
    return embedded_un, embedded_fmsi, matches, fmsi_recommendations


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or _get_settings()
    app = FastAPI(title="FMSI UN Recommendations API", version="0.1.0")
    app.state.settings = app_settings
    allow_origins = app_settings.cors_origins or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _log_startup() -> None:
        logger.info(
            "FMSI UN Recommendations API started; POST /matches (fmsi_pdf, un_doc), POST /feedback, GET /health"
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def _get_db_dependency() -> DatabaseAdapter:
        return get_database(app_settings)

    @app.post("/matches", response_model=MatchResponse)
    async def create_matches(
        fmsi_pdf: UploadFile = File(...),
        un_doc: UploadFile = File(...),
        job_id: str | None = Form(default=None),
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> MatchResponse:
        logger.info("POST /matches: received uploads (fmsi_pdf={}, un_doc={})", fmsi_pdf.filename, un_doc.filename)
        tracking_id = job_id or str(uuid.uuid4())
        progress_tracker.start(tracking_id, "Preparing your documents")
        fmsi_path = await _persist_upload(fmsi_pdf, "fmsi")
        un_doc_path = await _persist_upload(un_doc, "un")
        logger.info("Uploads saved: fmsi={}, un_doc={}", fmsi_path, un_doc_path)
        progress_tracker.update(tracking_id, 10, "Files received. Getting them ready.")

        embedded_un: list[dict[str, Any]] = []
        upr_category_counts: list[CategoryCount] = []
        fmsi_recommendations: list[FmsiRecommendation] = []
        fmsi_category_counts: list[CategoryCount] = []

        try:
            logger.info(
                "Starting match pipeline: extract → embed → match (threshold={})",
                app_settings.match_threshold,
            )
            embedded_un, embedded_fmsi, matches, fmsi_recommendations = await run_in_threadpool(
                _build_matches, un_doc_path, fmsi_path, app_settings.match_threshold, tracking_id
            )
            plain_upr_rows = [{k: v for k, v in row.items() if k != "embedding"} for row in embedded_un]
            upr_category_counts = _summarize_upr_categories(plain_upr_rows)
            fmsi_category_counts = _summarize_fmsi_categories(fmsi_recommendations)
            progress_tracker.update(tracking_id, 85, "Finishing up the results")
            logger.info(
                "Match pipeline done: {} matches (threshold={})",
                len(matches),
                app_settings.match_threshold,
            )
            for match in matches:
                match.setdefault("match_id", str(uuid.uuid4()))
        except (FileNotFoundError, ValueError) as exc:
            progress_tracker.fail(tracking_id, str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            logger.opt(exception=True).error("Failed to process documents")
            progress_tracker.fail(tracking_id, "We couldn't finish analyzing the documents")
            raise HTTPException(status_code=500, detail=f"Failed to process documents: {exc}") from exc

        def _save_and_build_response() -> tuple[str, list[MatchEntry]]:
            prediction_id = db.save_prediction(
                input_un_path=str(un_doc_path),
                input_fmsi_path=str(fmsi_path),
                un_rows=embedded_un,
                fmsi_rows=embedded_fmsi,
                matches=matches,
            )
            return prediction_id, [MatchEntry(**m) for m in matches]

        try:
            progress_tracker.update(tracking_id, 92, "Saving your results")
            prediction_id, match_entries = await run_in_threadpool(_save_and_build_response)
        except Exception as exc:  # pragma: no cover
            progress_tracker.fail(tracking_id, "We couldn't save the results")
            raise HTTPException(status_code=500, detail="Failed to save prediction") from exc
        progress_tracker.complete(tracking_id, "Analysis complete")
        logger.info("Prediction saved: id={}, returning {} matches", prediction_id, len(match_entries))
        return MatchResponse(
            prediction_id=prediction_id,
            matches=match_entries,
            upr_total_recommendations=len(embedded_un),
            upr_category_counts=upr_category_counts,
            fmsi_total_recommendations=len(fmsi_recommendations),
            fmsi_category_counts=fmsi_category_counts,
        )

    @app.post("/feedback", response_model=FeedbackResponse)
    def create_feedback(
        payload: FeedbackRequest,
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> FeedbackResponse:
        prediction = db.get_prediction(payload.prediction_id)
        if prediction is None:
            raise HTTPException(status_code=404, detail="Prediction not found")

        match_exists = any(match.get("match_id") == payload.match_id for match in prediction.matches)
        if not match_exists:
            raise HTTPException(status_code=404, detail="Match not found for prediction")

        feedback_id = db.save_feedback(
            prediction_id=payload.prediction_id,
            match_id=payload.match_id,
            thumb_up=payload.thumb_up,
            notes=payload.notes,
        )
        return FeedbackResponse(feedback_id=feedback_id)

    @app.get("/progress/{job_id}", response_model=ProgressStatus)
    def get_progress(job_id: str) -> ProgressStatus:
        status = progress_tracker.get(job_id)
        if status is None:
            return ProgressStatus(
                job_id=job_id,
                status="pending",
                percent=0.0,
                message="Waiting for analysis to start",
            )
        return ProgressStatus(
            job_id=job_id,
            status=status["status"],
            percent=status["percent"],
            message=status["message"],
        )

    return app
