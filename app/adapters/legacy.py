"""Legacy binary Office format support (v3.4).

DOC files are OLE compound documents. When the system tool ``antiword`` is
available we shell out to it for a faithful text dump; otherwise we raise an
actionable error so the pipeline reports the gap honestly instead of
fabricating content. No network calls, no dynamic code execution — the file
path is passed as an argument (never via a shell string).
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess


class LegacyToolMissing(RuntimeError):
    """Raised when a required external converter binary is not installed."""


def extract_doc(path: pathlib.Path) -> str:
    """Extract plain text from a legacy .doc file using antiword."""
    if shutil.which("antiword") is None:
        raise LegacyToolMissing(
            "DOC extraction needs the 'antiword' binary "
            "(apt-get install antiword) — or convert the file to DOCX"
        )
    proc = subprocess.run(  # noqa: S603 — no shell, fixed argv
        ["antiword", "-m", "utf8.txt", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"antiword failed: {err}")
    return proc.stdout
