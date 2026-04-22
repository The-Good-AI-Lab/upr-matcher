from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


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
