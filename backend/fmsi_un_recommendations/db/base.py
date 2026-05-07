from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class JobRecord:
    id: str
    user_email: str | None
    status: str
    source_path: str
    reference_path: str
    percent: float
    message: str
    prediction_id: str | None
    error: str | None
    created_at: str | None
    updated_at: str | None


@dataclass(slots=True)
class PredictionRecord:
    id: str
    input_un_path: str | None
    input_fmsi_path: str | None
    un_rows: list[dict[str, Any]]
    fmsi_rows: list[dict[str, Any]]
    matches: list[dict[str, Any]]


@dataclass(slots=True)
class FeedbackRecord:
    id: str
    prediction_id: str
    match_id: str
    thumb_up: bool
    notes: str | None = None


class DatabaseAdapter(ABC):
    @abstractmethod
    def save_prediction(
        self,
        *,
        input_un_path: str | None,
        input_fmsi_path: str | None,
        un_rows: list[dict[str, Any]],
        fmsi_rows: list[dict[str, Any]],
        matches: list[dict[str, Any]],
    ) -> str: ...

    @abstractmethod
    def list_predictions(self) -> list[PredictionRecord]: ...

    @abstractmethod
    def get_prediction(self, prediction_id: str) -> PredictionRecord | None: ...

    @abstractmethod
    def save_feedback(
        self,
        *,
        prediction_id: str,
        match_id: str,
        thumb_up: bool,
        notes: str | None = None,
    ) -> str: ...

    @abstractmethod
    def list_feedback(self, prediction_id: str | None = None) -> list[FeedbackRecord]: ...

    @abstractmethod
    def create_job(
        self,
        *,
        job_id: str,
        user_email: str | None,
        source_path: str,
        reference_path: str,
    ) -> None: ...

    @abstractmethod
    def claim_next_job(self) -> JobRecord | None: ...

    @abstractmethod
    def update_job_progress(self, job_id: str, percent: float, message: str) -> None: ...

    @abstractmethod
    def complete_job(self, job_id: str, prediction_id: str) -> None: ...

    @abstractmethod
    def fail_job(self, job_id: str, error: str) -> None: ...

    @abstractmethod
    def get_job(self, job_id: str) -> JobRecord | None: ...

    @abstractmethod
    def list_jobs_for_user(self, user_email: str | None, limit: int = 20) -> list[JobRecord]: ...

    @abstractmethod
    def cancel_job(self, job_id: str) -> None: ...

    @abstractmethod
    def delete_job(self, job_id: str) -> None: ...

    @abstractmethod
    def fail_stale_jobs(self, older_than_seconds: int) -> int: ...
