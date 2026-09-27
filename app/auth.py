"""API-key authentication middleware (v3.5).

Behavior:
- If ``UDO_API_KEYS`` env var is unset/empty, auth is DISABLED (dev mode).
- Otherwise every request to a protected path (/api/* except /api/health)
  must carry ``X-API-Key: <key>`` matching one of the comma-separated keys.
- Health and docs stay public so uptime probes and API browsing work;
  the UI prompts for a key and stores it in sessionStorage.
"""
from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

_PROTECTED_PREFIX = "/api/"
_PUBLIC_API = {"/api/health", "/api/docs", "/api/openapi.json"}


def api_keys() -> list[str]:
    raw = os.getenv("UDO_API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def auth_enabled() -> bool:
    return len(api_keys()) > 0


async def api_key_guard(request: Request, call_next):
    """FastAPI middleware enforcing X-API-Key when configured."""
    keys = api_keys()
    path = request.url.path
    if keys and path.startswith(_PROTECTED_PREFIX) and path not in _PUBLIC_API:
        supplied = request.headers.get("x-api-key", "")
        if not any(supplied == k for k in keys):
            return JSONResponse(
                status_code=401,
                content={"detail": "missing or invalid X-API-Key header"},
            )
    return await call_next(request)
