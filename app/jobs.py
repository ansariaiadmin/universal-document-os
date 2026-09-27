"""Durable job store — SQLite-backed so records survive restarts and are
visible to every worker (v4.2). Powers /api/job/{id} polling without the
in-memory-only limitation of earlier versions."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class JobStore:
    """Thread-safe SQLite job store with TTL cleanup of finished entries.

    One connection per thread (sqlite3 default safety); WAL journal keeps
    concurrent readers/writers from blocking each other.
    """

    def __init__(self, db_path: str | Path | None = None, ttl_seconds: int = 3600) -> None:
        if db_path is None:
            # Ephemeral default (tests/tooling): a private temp DB so two
            # stores never share state. Production wiring passes DATA/jobs.db.
            import tempfile

            db_path = Path(tempfile.mkdtemp(prefix="udo-jobs-")) / "jobs.db"
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._local = threading.local()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                       job_id      TEXT PRIMARY KEY,
                       state       TEXT NOT NULL,
                       created_at  REAL NOT NULL,
                       finished_at REAL,
                       payload     TEXT NOT NULL
                   )"""
            )

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            self._local.conn = conn
        return conn

    def create(self, job_id: str, **meta: Any) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "job_id": job_id,
            "state": "QUEUED",
            "created_at": time.time(),
            "finished_at": None,
            **meta,
        }
        with self._lock:
            conn = self._conn()
            conn.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?)",
                (job_id, rec["state"], rec["created_at"], None,
                 json.dumps(meta, ensure_ascii=False)),
            )
            conn.commit()
        return rec

    def update(self, job_id: str, **fields: Any) -> None:
        rec = self.get(job_id)
        if rec is None:
            return
        rec.update(fields)
        with self._lock:
            conn = self._conn()
            conn.execute(
                "UPDATE jobs SET state=?, payload=? WHERE job_id=?",
                (rec["state"], json.dumps(
                    {k: v for k, v in rec.items()
                     if k not in {"job_id", "state", "created_at", "finished_at", "result"}},
                    ensure_ascii=False), job_id),
            )
            conn.commit()

    def finish(self, job_id: str, state: str, result: dict[str, Any]) -> None:
        with self._lock:
            conn = self._conn()
            cur = conn.execute(
                "UPDATE jobs SET state=?, finished_at=?, payload=? WHERE job_id=?",
                (state, time.time(),
                 json.dumps({"result": result}, ensure_ascii=False), job_id),
            )
            if cur.rowcount == 0:  # never lose a terminal state to a race
                conn.execute(
                    "INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?)",
                    (job_id, state, time.time(), time.time(),
                     json.dumps({"result": result}, ensure_ascii=False)),
                )
            conn.commit()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._conn()
            row = conn.execute(
                "SELECT job_id, state, created_at, finished_at, payload FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        extra = json.loads(row[4])
        rec: dict[str, Any] = {
            "job_id": row[0], "state": row[1],
            "created_at": row[2], "finished_at": row[3],
        }
        rec.update({k: v for k, v in extra.items() if k != "result"})
        if "result" in extra:
            rec["result"] = extra["result"]
        return rec

    def sweep(self) -> int:
        """Drop finished jobs older than TTL; returns number removed."""
        cutoff = time.time() - self._ttl
        with self._lock:
            conn = self._conn()
            cur = conn.execute(
                "DELETE FROM jobs WHERE finished_at IS NOT NULL AND finished_at < ?",
                (cutoff,),
            )
            conn.commit()
            return cur.rowcount

    def age(self, job_id: str, seconds: float) -> None:
        """Shift a finished job's timestamp into the past (ops/testing aid)."""
        with self._lock:
            conn = self._conn()
            conn.execute(
                "UPDATE jobs SET finished_at = finished_at - ? WHERE job_id = ?",
                (seconds, job_id),
            )
            conn.commit()

    def stats(self) -> dict[str, int]:
        with self._lock:
            conn = self._conn()
            rows = conn.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall()
        total = sum(c for _, c in rows)
        return {"total": total, **{s: c for s, c in rows}}


def _ttl_from_env() -> int:
    import os

    return int(os.getenv("JOB_TTL_SECONDS", "3600"))


def _default_store() -> JobStore:
    from app.config import DATA

    return JobStore(DATA / "jobs.db", ttl_seconds=_ttl_from_env())


JOBS = _default_store()
