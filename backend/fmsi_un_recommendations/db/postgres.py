from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .base import DatabaseAdapter, FeedbackRecord, PredictionRecord


class PostgresDatabase(DatabaseAdapter):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._connection = psycopg.connect(self._dsn, row_factory=dict_row)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id UUID PRIMARY KEY,
                    input_un_path TEXT,
                    input_fmsi_path TEXT,
                    un_rows JSONB NOT NULL,
                    fmsi_rows JSONB NOT NULL,
                    matches JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id UUID PRIMARY KEY,
                    prediction_id UUID REFERENCES predictions(id) ON DELETE CASCADE,
                    match_id TEXT NOT NULL,
                    thumb_up BOOLEAN NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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
        prediction_id = uuid.uuid4()
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO predictions (id, input_un_path, input_fmsi_path, un_rows, fmsi_rows, matches)
                VALUES (%s, %s, %s, %s, %s, %s)
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
        return str(prediction_id)

    def list_predictions(self) -> list[PredictionRecord]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, input_un_path, input_fmsi_path, un_rows, fmsi_rows, matches FROM predictions ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
        return [self._row_to_prediction(row) for row in rows]

    def get_prediction(self, prediction_id: str) -> PredictionRecord | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, input_un_path, input_fmsi_path, un_rows, fmsi_rows, matches FROM predictions WHERE id = %s",
                (prediction_id,),
            )
            row = cursor.fetchone()
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
        feedback_id = uuid.uuid4()
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO feedback (id, prediction_id, match_id, thumb_up, notes)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    feedback_id,
                    prediction_id,
                    match_id,
                    thumb_up,
                    notes,
                ),
            )
        self._connection.commit()
        return str(feedback_id)

    def list_feedback(self, prediction_id: str | None = None) -> list[FeedbackRecord]:
        with self._connection.cursor() as cursor:
            if prediction_id:
                cursor.execute(
                    "SELECT id, prediction_id, match_id, thumb_up, notes FROM feedback WHERE prediction_id = %s ORDER BY created_at DESC",
                    (prediction_id,),
                )
            else:
                cursor.execute(
                    "SELECT id, prediction_id, match_id, thumb_up, notes FROM feedback ORDER BY created_at DESC"
                )
            rows = cursor.fetchall()
        return [self._row_to_feedback(row) for row in rows]

    @staticmethod
    def _deserialize_json(value: Any) -> Any:
        if isinstance(value, memoryview):
            value = value.tobytes()
        if isinstance(value, bytes | bytearray):
            value = value.decode("utf-8")
        if isinstance(value, str):
            return json.loads(value)
        return value

    @classmethod
    def _row_to_prediction(cls, row: dict[str, Any]) -> PredictionRecord:
        return PredictionRecord(
            id=str(row["id"]),
            input_un_path=row.get("input_un_path"),
            input_fmsi_path=row.get("input_fmsi_path"),
            un_rows=cls._deserialize_json(row["un_rows"]),
            fmsi_rows=cls._deserialize_json(row["fmsi_rows"]),
            matches=cls._deserialize_json(row["matches"]),
        )

    @classmethod
    def _row_to_feedback(cls, row: dict[str, Any]) -> FeedbackRecord:
        return FeedbackRecord(
            id=str(row["id"]),
            prediction_id=str(row["prediction_id"]),
            match_id=row["match_id"],
            thumb_up=bool(row["thumb_up"]),
            notes=row.get("notes"),
        )
