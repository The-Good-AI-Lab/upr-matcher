from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .base import DatabaseAdapter, FeedbackRecord, PredictionRecord

DB_FILENAME = "recommendations.db"


class LocalDatabase(DatabaseAdapter):
    def __init__(self, *, db_path: Path | str | None = None) -> None:
        resolved = Path(db_path) if db_path else Path("data") / DB_FILENAME
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.path = resolved
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                input_un_path TEXT,
                input_fmsi_path TEXT,
                un_rows TEXT NOT NULL,
                fmsi_rows TEXT NOT NULL,
                matches TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                prediction_id TEXT NOT NULL,
                match_id TEXT NOT NULL,
                thumb_up INTEGER NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(prediction_id) REFERENCES predictions(id)
            )
            """
        )
        self._connection.commit()

    def save_prediction(
        self,
        *,
        input_un_path: str | None,
        input_fmsi_path: str | None,
        un_rows: list[dict[str, Any]],
        fmsi_rows: list[dict[str, Any]],
        matches: list[dict[str, Any]],
    ) -> str:
        prediction_id = str(uuid.uuid4())
        cursor = self._connection.cursor()
        cursor.execute(
            """
            INSERT INTO predictions (id, input_un_path, input_fmsi_path, un_rows, fmsi_rows, matches)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                prediction_id,
                input_un_path,
                input_fmsi_path,
                json.dumps(un_rows, ensure_ascii=False),
                json.dumps(fmsi_rows, ensure_ascii=False),
                json.dumps(matches, ensure_ascii=False),
            ),
        )
        self._connection.commit()
        return prediction_id

    def list_predictions(self) -> list[PredictionRecord]:
        cursor = self._connection.cursor()
        rows = cursor.execute(
            "SELECT id, input_un_path, input_fmsi_path, un_rows, fmsi_rows, matches FROM predictions ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_prediction(row) for row in rows]

    def get_prediction(self, prediction_id: str) -> PredictionRecord | None:
        cursor = self._connection.cursor()
        row = cursor.execute(
            "SELECT id, input_un_path, input_fmsi_path, un_rows, fmsi_rows, matches FROM predictions WHERE id = ?",
            (prediction_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_prediction(row)

    def save_feedback(
        self,
        *,
        prediction_id: str,
        match_id: str,
        thumb_up: bool,
        notes: str | None = None,
    ) -> str:
        feedback_id = str(uuid.uuid4())
        cursor = self._connection.cursor()
        cursor.execute(
            """
            INSERT INTO feedback (id, prediction_id, match_id, thumb_up, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                prediction_id,
                match_id,
                1 if thumb_up else 0,
                notes,
            ),
        )
        self._connection.commit()
        return feedback_id

    def list_feedback(self, prediction_id: str | None = None) -> list[FeedbackRecord]:
        cursor = self._connection.cursor()
        if prediction_id:
            rows = cursor.execute(
                "SELECT id, prediction_id, match_id, thumb_up, notes FROM feedback WHERE prediction_id = ? ORDER BY created_at DESC",
                (prediction_id,),
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT id, prediction_id, match_id, thumb_up, notes FROM feedback ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_feedback(row) for row in rows]

    @staticmethod
    def _row_to_prediction(row: sqlite3.Row) -> PredictionRecord:
        return PredictionRecord(
            id=row["id"],
            input_un_path=row["input_un_path"],
            input_fmsi_path=row["input_fmsi_path"],
            un_rows=json.loads(row["un_rows"]),
            fmsi_rows=json.loads(row["fmsi_rows"]),
            matches=json.loads(row["matches"]),
        )

    @staticmethod
    def _row_to_feedback(row: sqlite3.Row) -> FeedbackRecord:
        return FeedbackRecord(
            id=row["id"],
            prediction_id=row["prediction_id"],
            match_id=row["match_id"],
            thumb_up=bool(row["thumb_up"]),
            notes=row["notes"],
        )
