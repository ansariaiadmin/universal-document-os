"""Adapters for Universal Document OS — each format has dedicated extractor.
Supports PDF/DOCX/XLSX/TXT/CSV/MD/JSON/HTML/RTF/PPTX/ODT with clean UnsupportedFormat handling.

v4.1 hardening: every text-producing adapter is bounded by ``MAX_EXTRACT_BYTES``
— a 25 MB upload must never expand into an unbounded in-memory string.
"""
from __future__ import annotations

import pathlib

from app.config import MAX_EXTRACT_BYTES, MAX_TEXT_CHARS


def _cap(text: str) -> str:
    """Truncate extracted text to the configured character budget."""
    if len(text) > MAX_TEXT_CHARS:
        return text[:MAX_TEXT_CHARS] + f"\n[TRUNCATED at {MAX_TEXT_CHARS} chars]"
    return text


def _guard_size(path: pathlib.Path) -> None:
    size = path.stat().st_size
    if size > MAX_EXTRACT_BYTES:
        raise RuntimeError(
            f"file too large to extract safely ({size} bytes > {MAX_EXTRACT_BYTES} limit)"
        )


class UnsupportedFormat(Exception):
    """Raised when format is known but adapter library missing or not implemented."""
    def __init__(self, fmt: str, reason: str = ""):
        self.fmt = fmt
        self.reason = reason
        super().__init__(f"Unsupported format {fmt}: {reason}" if reason else f"Unsupported format {fmt}")

# Registry of format -> extractor function
_EXTRACTORS: dict[str, callable] = {}

def register(fmt: str):
    def deco(fn):
        _EXTRACTORS[fmt.upper()] = fn
        return fn
    return deco

@register("PDF")
def extract_pdf(path: pathlib.Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise UnsupportedFormat("PDF", f"pypdf missing: {e}")
    _guard_size(path)
    try:
        reader = PdfReader(str(path))
        out = []
        total = 0
        for page in reader.pages:
            t = page.extract_text() or ""
            out.append(t)
            total += len(t)
            if total > MAX_TEXT_CHARS:  # stop early on pathological PDFs
                break
        return _cap("\n".join(out))
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")

@register("DOCX")
def extract_docx(path: pathlib.Path) -> str:
    try:
        from docx import Document
    except ImportError as e:
        raise UnsupportedFormat("DOCX", f"python-docx missing: {e}")
    _guard_size(path)
    try:
        doc = Document(str(path))
        return _cap("\n".join(p.text for p in doc.paragraphs))
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}")

@register("XLSX")
def extract_xlsx(path: pathlib.Path) -> str:
    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise UnsupportedFormat("XLSX", f"openpyxl missing: {e}")
    _guard_size(path)
    try:
        # data_only=True -> cell values instead of raw formulas in the output text
        wb = load_workbook(path, read_only=True, data_only=True)
        out = []
        total = 0
        for ws in wb.worksheets:
            out.append(f"[SHEET] {ws.title}")
            for row in ws.iter_rows(values_only=True):
                line = "\t".join("" if v is None else str(v) for v in row)
                out.append(line)
                total += len(line)
                if total > MAX_TEXT_CHARS:  # huge sheets truncate, never OOM
                    break
            if total > MAX_TEXT_CHARS:
                break
        return _cap("\n".join(out))
    except Exception as e:
        raise RuntimeError(f"XLSX extraction failed: {e}")

@register("TXT")
@register("MARKDOWN")
@register("MD")
@register("CSV")
@register("JSON")
@register("HTML")
@register("RTF")
def extract_textlike(path: pathlib.Path) -> str:
    # Bounded read: never slurp more than MAX_EXTRACT_BYTES into memory.
    _guard_size(path)
    return _cap(path.read_text(encoding="utf-8", errors="replace"))

@register("PPTX")
def extract_pptx(path: pathlib.Path) -> str:
    """PPTX adapter — uses python-pptx if available, else UnsupportedFormat."""
    try:
        from pptx import Presentation
    except ImportError as e:
        raise UnsupportedFormat("PPTX", f"python-pptx not installed: {e}. Install with pip install python-pptx")
    _guard_size(path)
    try:
        prs = Presentation(str(path))
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    texts.append(shape.text)
        return _cap("\n".join(texts))
    except Exception as e:
        raise RuntimeError(f"PPTX extraction failed: {e}")

@register("ODT")
@register("ODS")
@register("ODP")
def extract_opendocument(path: pathlib.Path) -> str:
    """OpenDocument formats (ODT/ODS/ODP) are ZIP files with XML payloads.

    We parse directly from the archive — no external dependency required —
    and degrade to tag-stripping only if the XML itself is malformed.
    """
    import xml.etree.ElementTree as ET
    import zipfile

    _guard_size(path)
    members = {"ODT": "content.xml", "ODS": "content.xml", "ODP": "content.xml"}
    fmt = _format_of(path)
    try:
        with zipfile.ZipFile(str(path)) as z:
            name = members.get(fmt, "content.xml")
            if name not in z.namelist():
                raise UnsupportedFormat(fmt, f"{name} not found in archive")
            info = z.getinfo(name)
            if info.file_size > MAX_EXTRACT_BYTES:
                raise RuntimeError(
                    f"{fmt} member '{name}' unpacks to {info.file_size} bytes (limit {MAX_EXTRACT_BYTES})"
                )
            data = z.read(name)
    except zipfile.BadZipFile as e:
        raise RuntimeError(f"{fmt} extraction failed: not a valid zip: {e}")

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        # Malformed XML — last-resort tag strip keeps the pipeline alive.
        import re
        txt = re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="replace"))
        return re.sub(r"\s+", " ", txt).strip()

    # Collect all text nodes; paragraph boundaries become newlines.
    parts = []
    for elem in root.iter():
        tag = elem.tag.rpartition("}")[2]
        if elem.text and elem.text.strip():
            parts.append(elem.text if tag != "p" else "\n" + elem.text)
        if elem.tail and elem.tail.strip():
            parts.append(elem.tail)
    return "".join(parts).strip()


def get_extractor(fmt: str):
    """Return extractor for format, or None."""
    return _EXTRACTORS.get(fmt.upper())

_EXT_FORMATS = {
    ".pdf": "PDF", ".docx": "DOCX", ".doc": "DOC", ".xlsx": "XLSX", ".xls": "XLS",
    ".pptx": "PPTX", ".ppt": "PPT", ".odt": "ODT", ".ods": "ODS", ".odp": "ODP",
    ".rtf": "RTF", ".csv": "CSV", ".txt": "TXT", ".md": "MARKDOWN", ".html": "HTML",
    ".htm": "HTML", ".json": "JSON",
    ".png": "IMAGE", ".jpg": "IMAGE", ".jpeg": "IMAGE", ".webp": "IMAGE", ".tif": "IMAGE", ".tiff": "IMAGE",
}


def format_of(path: pathlib.Path) -> str:
    """Map a file path to its canonical format string (single source of truth)."""
    ext = path.suffix.lower()
    if ext in _EXT_FORMATS:
        return _EXT_FORMATS[ext]
    import mimetypes
    guess = mimetypes.guess_type(path.name)[0] or ""
    return guess.upper().replace("/", "_") if guess else "UNKNOWN"


def _format_of(path: pathlib.Path) -> str:
    return format_of(path)


def extract(path: pathlib.Path, fmt: str | None = None) -> str:
    """High-level extract dispatching to adapters, raising UnsupportedFormat if needed."""
    if fmt is None:
        fmt = format_of(path)
    if fmt.upper() == "IMAGE":
        from app.ocr.multi_engine import ocr as _ocr  # images go through real OCR
        result = _ocr.extract(str(path))
        if result.get("error"):
            raise UnsupportedFormat("IMAGE", result["error"])
        text = result["text"]
        if not text.strip():
            # Successful run with no detected text — report honestly, never fabricate.
            return "[NO_TEXT_DETECTED]"
        return text

    extractor = get_extractor(fmt)
    if extractor is None:
        # Unknown format -> treat as textlike if possible else unsupported
        if fmt.upper() == "UNKNOWN":
            raise UnsupportedFormat(fmt, "unknown format")
        # Legacy binary Office formats (DOC/PPT/XLS): OLE containers.
        # v3.4 — real antiword-based extraction when available; otherwise an
        # honest, actionable error instead of silent failure.
        if fmt.upper() in ("DOC", "PPT", "XLS"):
            if fmt.upper() == "DOC":
                from app.adapters.legacy import extract_doc

                try:
                    return extract_doc(path)
                except Exception as e:
                    raise UnsupportedFormat(fmt, str(e))
            raise UnsupportedFormat(
                fmt, f"{fmt} legacy format requires additional library; convert to DOCX/PPTX/XLSX/ODT"
            )
        # OpenDocument spreadsheets/presentations reuse the ODT zip-XML adapter.
        if fmt.upper() in ("ODS", "ODP"):
            odt = get_extractor("ODT")
            if odt is not None:
                return odt(path)
        # Try text fallback
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            raise UnsupportedFormat(fmt, "no adapter available")
    return extractor(path)

# Public list of supported formats
SUPPORTED_FORMATS = sorted(_EXTRACTORS.keys())
