from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, ConfigDict

from .db import DatabaseAdapter, get_database
from .settings import Settings
from .similarity_search import Recommendation as FmsiRecommendation

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
    feedback: str | None = None


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


class JobEnqueuedResponse(BaseModel):
    job_id: str


class JobSummary(BaseModel):
    job_id: str
    status: Literal["pending", "processing", "completed", "failed", "unknown"]
    percent: float
    prediction_id: str | None
    source_filename: str | None
    reference_filename: str | None
    created_at: str | None
    updated_at: str | None


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
    prediction_id: str | None = None


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
        try:
            db = get_database(app_settings)
            recovered = db.fail_stale_jobs(0)
            if recovered:
                logger.warning("Marked {} orphaned job(s) as failed on startup", recovered)
        except Exception:
            logger.opt(exception=True).warning("Could not recover orphaned jobs on startup")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def _get_db_dependency() -> DatabaseAdapter:
        return get_database(app_settings)

    @app.post("/matches", response_model=JobEnqueuedResponse)
    async def create_matches(
        request: Request,
        fmsi_pdf: UploadFile = File(...),
        un_doc: UploadFile = File(...),
        job_id: str | None = Form(default=None),
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> JobEnqueuedResponse:
        async def _enqueue_job() -> JobEnqueuedResponse:
            tracking_id = job_id or str(uuid.uuid4())
            user_email: str | None = request.headers.get("X-Auth-Request-Email")
            logger.info(
                "POST /matches: queuing job {} for user={} (fmsi_pdf={}, un_doc={})",
                tracking_id,
                user_email,
                fmsi_pdf.filename,
                un_doc.filename,
            )
            fmsi_path = await _persist_upload(fmsi_pdf, "fmsi")
            un_doc_path = await _persist_upload(un_doc, "un")
            db.create_job(
                job_id=tracking_id,
                user_email=user_email,
                source_path=str(fmsi_path),
                reference_path=str(un_doc_path),
            )
            logger.info("Job {} enqueued", tracking_id)
            return JobEnqueuedResponse(job_id=tracking_id)

        return await _enqueue_job()

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
    def get_progress(
        job_id: str,
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> ProgressStatus:
        job = db.get_job(job_id)
        if job is None:
            return ProgressStatus(
                job_id=job_id,
                status="unknown",
                percent=0.0,
                message="Job not found",
            )
        return ProgressStatus(
            job_id=job_id,
            status=job.status,  # type: ignore[arg-type]
            percent=job.percent,
            message=job.message,
            prediction_id=job.prediction_id,
        )

    @app.post("/jobs/{job_id}/cancel", status_code=204)
    def cancel_job(
        job_id: str,
        request: Request,
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> None:
        user_email: str | None = request.headers.get("X-Auth-Request-Email")
        job = db.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.user_email != user_email:
            raise HTTPException(status_code=403, detail="Not your job")
        if job.status in ("completed", "failed"):
            raise HTTPException(status_code=409, detail="Job already finished")
        db.cancel_job(job_id)

    @app.delete("/jobs/{job_id}", status_code=204)
    def delete_job(
        job_id: str,
        request: Request,
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> None:
        user_email: str | None = request.headers.get("X-Auth-Request-Email")
        job = db.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.user_email != user_email:
            raise HTTPException(status_code=403, detail="Not your job")
        db.delete_job(job_id)

    @app.get("/jobs", response_model=list[JobSummary])
    def list_jobs(
        request: Request,
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> list[JobSummary]:
        user_email: str | None = request.headers.get("X-Auth-Request-Email")
        jobs = db.list_jobs_for_user(user_email)
        return [
            JobSummary(
                job_id=job.id,
                status=job.status,  # type: ignore[arg-type]
                percent=job.percent,
                prediction_id=job.prediction_id,
                source_filename=Path(job.source_path).name if job.source_path else None,
                reference_filename=Path(job.reference_path).name if job.reference_path else None,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            for job in jobs
        ]

    @app.get("/predictions/{prediction_id}", response_model=MatchResponse)
    def get_prediction(
        prediction_id: str,
        db: DatabaseAdapter = Depends(_get_db_dependency),
    ) -> MatchResponse:
        prediction = db.get_prediction(prediction_id)
        if prediction is None:
            raise HTTPException(status_code=404, detail="Prediction not found")

        feedback_records = db.list_feedback(prediction_id)
        # keep only the latest feedback per match (list is ordered DESC by created_at)
        feedback_by_match: dict[str, str] = {}
        for fb in reversed(feedback_records):
            feedback_by_match[fb.match_id] = "correct" if fb.thumb_up else "incorrect"

        upr_category_counts = _summarize_upr_categories(prediction.un_rows)
        fmsi_category_counts = _summarize_fmsi_categories(prediction.fmsi_rows)
        match_entries = [
            MatchEntry(**m, feedback=feedback_by_match.get(m.get("match_id", ""))) for m in prediction.matches
        ]

        return MatchResponse(
            prediction_id=prediction_id,
            matches=match_entries,
            upr_total_recommendations=len(prediction.un_rows),
            upr_category_counts=upr_category_counts,
            fmsi_total_recommendations=len(prediction.fmsi_rows),
            fmsi_category_counts=fmsi_category_counts,
        )

    return app
