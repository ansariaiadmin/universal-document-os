"""Central configuration — env-driven, single source of truth for paths and limits."""
from __future__ import annotations

import os
from pathlib import Path

BASE = Path(os.getenv("BASE_DIR", Path(__file__).resolve().parent.parent))

# Data directories (overridable via DATA_DIR for containerized/deployed setups).
# An absolute DATA_DIR is honored as-is; a relative one resolves under BASE.
_data_env = os.getenv("DATA_DIR", "data")
DATA = Path(_data_env) if Path(_data_env).is_absolute() else BASE / _data_env
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
WORKROOMS = DATA / "workrooms"
AUDIT_FILE = DATA / "audit.jsonl"

# Limits
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))  # 25 MB default
PREVIEW_CHARS = int(os.getenv("PREVIEW_CHARS", 5000))
# v4.1 — extraction budgets: an upload must never expand into unbounded memory.
MAX_EXTRACT_BYTES = int(os.getenv("MAX_EXTRACT_BYTES", 64 * 1024 * 1024))  # decompressed ceiling
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", 2_000_000))               # extracted-text ceiling

# App metadata — single version source
APP_NAME = "Universal Document OS"
APP_VERSION = os.getenv("APP_VERSION", "4.2.0")

def ensure_dirs() -> None:
    """Create runtime directories if missing."""
    for p in (UPLOADS, OUTPUTS, WORKROOMS):
        p.mkdir(parents=True, exist_ok=True)
