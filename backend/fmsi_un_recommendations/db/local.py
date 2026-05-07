from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .base import DatabaseAdapter, FeedbackRecord, JobRecord, PredictionRecord

DB_FILENAME = "recommendations.db"


class LocalDatabase(DatabaseAdapter):
    def __init__(self, *, db_path: Path | str | None = None) -> None:
        resolved = Path(db_path) if db_path else Path("data") / DB_FILENAME
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.path = resolved
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id            TEXT PRIMARY KEY,
                user_email    TEXT,
                status        TEXT NOT NULL DEFAULT 'pending',
                source_path   TEXT NOT NULL,
                reference_path TEXT NOT NULL,
                percent       REAL NOT NULL DEFAULT 0.0,
                message       TEXT NOT NULL DEFAULT '',
                prediction_id TEXT,
                error         TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def create_job(
        self,
        *,
        job_id: str,
        user_email: str | None,
        source_path: str,
        reference_path: str,
    ) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            INSERT INTO jobs (id, user_email, status, source_path, reference_path, percent, message)
            VALUES (?, ?, 'pending', ?, ?, 0.0, 'Waiting in queue')
            """,
            (job_id, user_email, source_path, reference_path),
        )
        self._connection.commit()

    def claim_next_job(self) -> JobRecord | None:
        cursor = self._connection.cursor()
        row = cursor.execute("SELECT id FROM jobs WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1").fetchone()
        if row is None:
            return None
        job_id = row["id"]
        cursor.execute(
            "UPDATE jobs SET status = 'processing', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
            (job_id,),
        )
        self._connection.commit()
        if cursor.rowcount == 0:
            return None
        row = cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row)

    def update_job_progress(self, job_id: str, percent: float, message: str) -> None:
        self._connection.execute(
            "UPDATE jobs SET percent = ?, message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (percent, message, job_id),
        )
        self._connection.commit()

    def complete_job(self, job_id: str, prediction_id: str) -> None:
        self._connection.execute(
            "UPDATE jobs SET status = 'completed', percent = 100.0, prediction_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (prediction_id, job_id),
        )
        self._connection.commit()

    def fail_job(self, job_id: str, error: str) -> None:
        self._connection.execute(
            "UPDATE jobs SET status = 'failed', error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (error, job_id),
        )
        self._connection.commit()

    def get_job(self, job_id: str) -> JobRecord | None:
        row = self._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def cancel_job(self, job_id: str) -> None:
        self._connection.execute(
            """
            UPDATE jobs SET status = 'failed', error = 'Cancelled by user',
                message = 'Cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (job_id,),
        )
        self._connection.commit()

    def delete_job(self, job_id: str) -> None:
        self._connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        self._connection.commit()

    def fail_stale_jobs(self, older_than_seconds: int) -> int:
        cursor = self._connection.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                error  = 'Job timed out — no progress for over an hour',
                message = 'Timed out',
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('pending', 'processing')
              AND (UNIXEPOCH('now') - UNIXEPOCH(updated_at)) > ?
            """,
            (older_than_seconds,),
        )
        self._connection.commit()
        return cursor.rowcount

    def list_jobs_for_user(self, user_email: str | None, limit: int = 20) -> list[JobRecord]:
        if user_email is None:
            rows = self._connection.execute(
                "SELECT * FROM jobs WHERE user_email IS NULL ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM jobs WHERE user_email = ? ORDER BY created_at DESC LIMIT ?",
                (user_email, limit),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            user_email=row["user_email"],
            status=row["status"],
            source_path=row["source_path"],
            reference_path=row["reference_path"],
            percent=row["percent"],
            message=row["message"],
            prediction_id=row["prediction_id"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
