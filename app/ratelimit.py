"""Sliding-window rate limiter middleware — dependency-free, opt-in.

Env: ``RATE_LIMIT_PER_MIN``  max requests per client per minute (0/unset = off).
Only mutating endpoints (/api/* POST/PUT/DELETE) and the panel's polling
targets are counted; static assets and docs are exempt so a full page load
never burns budget. Client identity = first entry of ``X-Forwarded-For`` when
present (trusted-proxy deployments) else ``request.client.host``.

State is per-process; behind multiple workers set the limit accordingly or
move enforcement to the edge proxy. 429 responses carry ``Retry-After``.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse


def _limit() -> int:
    try:
        return int(os.getenv("RATE_LIMIT_PER_MIN", "0"))
    except ValueError:
        return 0


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                retry = window - (now - q[0])
                return False, max(1.0, round(retry))
            q.append(now)
            return True, 0.0

    def sweep(self) -> int:
        """Drop idle buckets (called from the lifespan janitor)."""
        now = time.monotonic()
        removed = 0
        with self._lock:
            for k in [k for k, q in self._hits.items() if not q or now - q[-1] > 300]:
                del self._hits[k]
                removed += 1
        return removed


_LIMITER = SlidingWindowLimiter()

_COUNTED_PREFIXES = ("/api/process", "/api/download", "/api/job", "/api/jobs", "/api/status")


def _bucket(path: str) -> str:
    """Coarse bucket so /api/job/<id> variants share one budget."""
    parts = [p for p in path.split("/") if p]  # ['api','job','<id>']
    return "/".join(parts[:2]) if len(parts) >= 2 else path


async def rate_limit_guard(request, call_next):
    limit = _limit()
    path = request.url.path
    if limit and any(path.startswith(p) for p in _COUNTED_PREFIXES):
        fwd = request.headers.get("x-forwarded-for", "")
        client = (
            fwd.split(",")[0].strip()
            if fwd
            else (request.client.host if request.client else "unknown")
        )
        ok, retry_after = _LIMITER.allow(f"{client}:{_bucket(path)}", limit)
        if not ok:
            return JSONResponse(
                status_code=429,
                content={"detail": f"rate limit exceeded ({limit}/min)"},
                headers={"Retry-After": str(int(retry_after))},
            )
    return await call_next(request)
