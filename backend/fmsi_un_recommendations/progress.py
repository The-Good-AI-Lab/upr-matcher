import threading
from typing import Literal

JobStatus = Literal["pending", "processing", "completed", "failed", "unknown"]


class ProgressTracker:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, str | float]] = {}
        self._lock = threading.Lock()

    def _set_entry(self, job_id: str, *, status: str, percent: float, message: str) -> None:
        self._store[job_id] = {
            "status": status,
            "percent": percent,
            "message": message,
        }

    def start(self, job_id: str, message: str) -> None:
        with self._lock:
            self._set_entry(job_id, status="processing", percent=0.0, message=message)

    def update(self, job_id: str, percent: float, message: str) -> None:
        with self._lock:
            if job_id in self._store:
                self._set_entry(job_id, status="processing", percent=percent, message=message)

    def complete(self, job_id: str, message: str) -> None:
        with self._lock:
            if job_id in self._store:
                self._set_entry(job_id, status="completed", percent=100.0, message=message)

    def fail(self, job_id: str, message: str) -> None:
        with self._lock:
            percent = float(self._store[job_id]["percent"]) if job_id in self._store else 0.0
            self._set_entry(job_id, status="failed", percent=percent, message=message)

    def get(self, job_id: str) -> dict[str, str | float] | None:
        with self._lock:
            status = self._store.get(job_id)
            if status is None:
                return None
            return dict(status)


progress_tracker = ProgressTracker()
