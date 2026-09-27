"""Central configuration — env-driven, single source of truth for paths and limits."""
from __future__ import annotations

import os
from pathlib import Path

BASE = Path(os.getenv("BASE_DIR", Path(__file__).resolve().parent.parent))

# Data directories (overridable via DATA_DIR for containerized/deployed setups)
DATA = BASE / os.getenv("DATA_DIR", "data")
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
WORKROOMS = DATA / "workrooms"
AUDIT_FILE = DATA / "audit.jsonl"

# Limits
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))  # 25 MB default
PREVIEW_CHARS = int(os.getenv("PREVIEW_CHARS", 5000))

# App metadata — single version source
APP_NAME = "Universal Document OS"
APP_VERSION = os.getenv("APP_VERSION", "3.2.6")

def ensure_dirs() -> None:
    """Create runtime directories if missing."""
    for p in (UPLOADS, OUTPUTS, WORKROOMS):
        p.mkdir(parents=True, exist_ok=True)
