"""In-memory job store with TTL cleanup — powers /api/job/{id} polling (v3.3)."""
from __future__ import annotations

import threading
import time
from typing import Any


class JobStore:
    """Thread-safe dict of jobs with automatic expiry of finished entries."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def create(self, job_id: str, **meta: Any) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "job_id": job_id,
            "state": "QUEUED",
            "created_at": time.time(),
            "finished_at": None,
            **meta,
        }
        with self._lock:
            self._jobs[job_id] = rec
        return rec

    def update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is not None:
                rec.update(fields)

    def finish(self, job_id: str, state: str, result: dict[str, Any]) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is not None:
                rec.update(state=state, result=result, finished_at=time.time())

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            rec = self._jobs.get(job_id)
            return dict(rec) if rec else None

    def sweep(self) -> int:
        """Drop finished jobs older than TTL; returns number removed."""
        now = time.time()
        removed = 0
        with self._lock:
            expired = [
                jid
                for jid, r in self._jobs.items()
                if r["finished_at"] and now - r["finished_at"] > self._ttl
            ]
            for jid in expired:
                del self._jobs[jid]
                removed += 1
        return removed

    def stats(self) -> dict[str, int]:
        with self._lock:
            states: dict[str, int] = {}
            for r in self._jobs.values():
                states[r["state"]] = states.get(r["state"], 0) + 1
            return {"total": len(self._jobs), **states}


def _ttl_from_env() -> int:
    import os

    return int(os.getenv("JOB_TTL_SECONDS", "3600"))


JOBS = JobStore(ttl_seconds=_ttl_from_env())
