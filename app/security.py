"""Security helpers — filename sanitization and safe path resolution.

Upload filenames come from untrusted clients. We must never let a crafted
name (e.g. ``../../etc/passwd``) escape the intended directory.
"""
from __future__ import annotations

import re
from pathlib import Path

_UNSAFE = re.compile(r"[^A-Za-z0-9._\-\u0600-\u06FF ]+")


def sanitize_filename(name: str | None, fallback: str = "upload.bin") -> str:
    """Reduce a client-supplied filename to a safe basename.

    - strips any directory components (Windows and POSIX separators)
    - removes path-traversal sequences (..)
    - blocks names that could hide files or break shells (leading dot/dash)
    - collapses everything else to a conservative character set
    """
    raw = (name or "").replace("\\", "/").split("/")[-1].strip()
    raw = raw.replace("..", "_")
    safe = _UNSAFE.sub("_", raw).strip(" .-")
    if not safe:
        return fallback
    return safe[:180]


def resolve_within(directory: Path, name: str) -> Path | None:
    """Resolve ``directory/name`` and ensure it stays inside ``directory``.

    Returns the resolved path, or ``None`` if the name escapes the directory
    or does not exist. Symlinks are resolved so they cannot be used to leak
    arbitrary files.
    """
    base = directory.resolve()
    candidate = (base / name).resolve()
    if candidate == base or base not in candidate.parents:
        return None
    if not candidate.is_file():
        return None
    return candidate
