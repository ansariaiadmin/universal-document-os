"""Adaptive content guard — magic-byte verification + archive-bomb protection.

Extension-based format detection is trivially spoofable (rename ``evil.exe``
to ``report.pdf``). This module adds a second, *content-derived* layer:

1. ``sniff_type`` reads the first 8 KiB and matches known file signatures
   (magic bytes). It never trusts the filename.
2. ``looks_binary`` flags payloads that are not plausibly text — used to stop
   the "unknown extension → read as UTF-8" fallback from dumping binary junk
   (or huge in-memory blobs) into results.
3. ``check_zip_bomb`` rejects OOXML/ODF archives whose declared or actual
   uncompressed size exceeds a configurable budget (classic zip-bomb defense).

All checks are pure-stdlib and deterministic; failures raise
``ContentRejected`` which the pipeline converts into a clean HTTP 415.
"""
from __future__ import annotations

import zipfile

# signature (hex prefix, offset) -> canonical media type
_SIGNATURES = [
    (b"%PDF-", 0, "application/pdf"),
    (b"PK\x03\x04", 0, "application/zip"),          # OOXML / ODF containers
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0, "application/x-ole"),  # legacy Office
    (b"RTF{\\", 0, "application/rtf"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"RIFF", 0, "image/webp"),                      # WEBP checked via suffix below
    (b"II*\x00", 0, "image/tiff"),
    (b"MM\x00*", 0, "image/tiff"),
]

# Only these extensions are ever read as raw text; anything else with an
# unrecognized extension is rejected outright (no silent binary fallback).
TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".xml", ".log"}

# media type (from magic bytes) -> canonical pipeline format
_MEDIA_TO_FMT = {
    "application/pdf": "PDF",
    "image/png": "IMAGE", "image/jpeg": "IMAGE", "image/gif": "IMAGE",
    "image/webp": "IMAGE", "image/tiff": "IMAGE",
}


class ContentRejected(Exception):
    """Raised when content fails adaptive safety verification."""


def sniff_type(path) -> str | None:
    """Return media type derived from magic bytes, or None if unknown."""
    try:
        with open(path, "rb") as f:
            head = f.read(8192)
    except OSError:
        return None
    if not head:
        return "application/x-empty"
    for sig, off, media in _SIGNATURES:
        if head[off : off + len(sig)] == sig:
            if media == "image/webp" and head[8:12] != b"WEBP":
                continue
            return media
    return None


def looks_binary(path, sample_bytes: int = 4096) -> bool:
    """Heuristic: NUL bytes or a high ratio of non-text control chars."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_bytes)
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    if not chunk:
        return False
    texty = sum(
        1 for b in chunk
        if 32 <= b < 127 or b in (9, 10, 13) or b >= 128  # utf-8 multibyte ok
    )
    return texty / len(chunk) < 0.85


def check_zip_bomb(path, max_total_bytes: int, max_ratio: float = 200.0) -> None:
    """Reject zip-based documents (docx/xlsx/pptx/odt…) that unpack absurdly.

    Two independent guards: declared sizes (FileHeaderSize) and an actual
    streaming decompression budget — attackers can lie about the header.
    Raises ContentRejected on violation.
    """
    if not zipfile.is_zipfile(path):
        return
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            declared = sum(i.file_size for i in infos)
            compressed = sum(i.compress_size for i in infos) or 1
            if declared > max_total_bytes:
                raise ContentRejected(
                    f"archive declares {declared} bytes uncompressed (limit {max_total_bytes})"
                )
            ratio = declared / compressed
            if ratio > max_ratio and declared > 1024 * 1024:
                raise ContentRejected(f"suspicious compression ratio {ratio:.0f}x")
            # streaming budget — catches lying headers
            budget = min(max_total_bytes, 64 * 1024 * 1024)
            seen = 0
            for info in infos:
                if info.is_dir():
                    continue
                with zf.open(info) as member:
                    while True:
                        block = member.read(1 << 16)
                        if not block:
                            break
                        seen += len(block)
                        if seen > budget:
                            raise ContentRejected(
                                f"archive streams beyond {budget}-byte budget"
                            )
    except zipfile.BadZipFile as e:
        raise ContentRejected(f"corrupt zip container: {e}") from e


def verify(path, fmt: str, max_extract_bytes: int) -> None:
    """Full adaptive gate for one uploaded file. Raises ContentRejected."""
    media = sniff_type(path)
    ext = path.suffix.lower()

    # Unknown extension: only the whitelisted text family survives, and even
    # then the payload must actually look like text.
    # A recognized magic byte wins over an unknown extension — e.g. a real
    # PDF named ".weird" should still be processed, not rejected.
    sniffed_fmt = _MEDIA_TO_FMT.get(media or "")
    if fmt.upper() == "UNKNOWN" and sniffed_fmt is None:
        if ext not in TEXT_EXTS:
            raise ContentRejected(
                f"unrecognized type: extension '{ext}' is not an accepted document format"
                + (f" and content sniffed as {media}" if media else "")
            )
        if looks_binary(path):
            raise ContentRejected(f"text-family extension '{ext}' carries a binary payload")
    # Text-family claims (.txt/.md/…) must actually carry text — magic bytes
    # that resolve to a *document container* mean the name is lying.
    if ext in TEXT_EXTS and media in ("application/x-ole", "application/zip", "application/pdf"):
        raise ContentRejected(f"extension '{ext}' claims text but content is {media}")
    if fmt.upper() == "TXT" and looks_binary(path):
        raise ContentRejected("extension says TXT but payload is binary")
    if fmt.upper() == "PDF" and media not in (None, "application/pdf"):
        raise ContentRejected(f"claims PDF but magic bytes say {media}")
    if fmt.upper() in ("DOCX", "XLSX", "PPTX", "ODT", "ODS", "ODP") and media not in (
        None,
        "application/zip",
    ):
        raise ContentRejected(f"claims {fmt} but content is not an OOXML/ODF zip ({media})")
    if fmt.upper() in ("DOCX", "XLSX", "PPTX", "ODT", "ODS", "ODP", "UNKNOWN"):
        check_zip_bomb(path, max_extract_bytes)
