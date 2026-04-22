import threading
from typing import Literal

JobStatus = Literal["pending", "processing", "completed", "failed", "unknown"]


class ProgressTracker:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, str | float]] = {}
        self._lock = threading.Lock()

    def start(self, job_id: str, message: str) -> None:
        with self._lock:
            self._store[job_id] = {
                "status": "processing",
                "percent": 0.0,
                "message": message,
            }

    def update(self, job_id: str, percent: float, message: str) -> None:
        with self._lock:
            if job_id in self._store:
                self._store[job_id].update(
                    status="processing",
                    percent=percent,
                    message=message,
                )

    def complete(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id in self._store:
                self._store[job_id].update(
                    status="completed",
                    percent=100.0,
                    message=message,
                )

    def fail(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id in self._store:
                self._store[job_id].update(
                    status="failed",
                    message=message,
                )
            else:
                self._store[job_id] = {
                    "status": "failed",
                    "percent": 0.0,
                    "message": message,
                }

    def get(self, job_id: str) -> dict[str, str | float] | None:
        with self._lock:
            return self._store.get(job_id)


progress_tracker = ProgressTracker()
