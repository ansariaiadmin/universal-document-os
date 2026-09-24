"""Adapters for Universal Document OS — each format has dedicated extractor.
Supports PDF/DOCX/XLSX/TXT/CSV/MD/JSON/HTML/RTF/PPTX/ODT with clean UnsupportedFormat handling.
"""
from __future__ import annotations

import pathlib


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
    try:
        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")

@register("DOCX")
def extract_docx(path: pathlib.Path) -> str:
    try:
        from docx import Document
    except ImportError as e:
        raise UnsupportedFormat("DOCX", f"python-docx missing: {e}")
    try:
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}")

@register("XLSX")
def extract_xlsx(path: pathlib.Path) -> str:
    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise UnsupportedFormat("XLSX", f"openpyxl missing: {e}")
    try:
        wb = load_workbook(path, read_only=True, data_only=False)
        out = []
        for ws in wb.worksheets:
            out.append(f"[SHEET] {ws.title}")
            for row in ws.iter_rows(values_only=True):
                out.append("\t".join("" if v is None else str(v) for v in row))
        return "\n".join(out)
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
    # Try utf-8, fallback replace
    return path.read_text(encoding="utf-8", errors="replace")

@register("PPTX")
def extract_pptx(path: pathlib.Path) -> str:
    """PPTX adapter — uses python-pptx if available, else UnsupportedFormat."""
    try:
        from pptx import Presentation
    except ImportError as e:
        raise UnsupportedFormat("PPTX", f"python-pptx not installed: {e}. Install with pip install python-pptx")
    try:
        prs = Presentation(str(path))
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    texts.append(shape.text)
        return "\n".join(texts)
    except Exception as e:
        raise RuntimeError(f"PPTX extraction failed: {e}")

@register("ODT")
def extract_odt(path: pathlib.Path) -> str:
    """ODT adapter — tries odfpy, then zipfile fallback parsing content.xml."""
    # Try odfpy first
    try:
        from odf import text as odf_text
        from odf.opendocument import load
        doc = load(str(path))
        out = []
        for para in doc.getElementsByType(odf_text.P):
            # Concatenate text nodes
            txt = ""
            for node in para.childNodes:
                if node.nodeType == node.TEXT_NODE:
                    txt += node.data
                elif hasattr(node, "childNodes"):
                    for cn in node.childNodes:
                        if hasattr(cn, "data"):
                            txt += cn.data
            if txt:
                out.append(txt)
        if out:
            return "\n".join(out)
    except ImportError:
        pass  # try fallback
    except Exception:
        # If odfpy present but failed, try fallback
        pass

    # Fallback: ODT is zip containing content.xml
    try:
        import xml.etree.ElementTree as ET
        import zipfile
        with zipfile.ZipFile(str(path)) as z:
            if "content.xml" not in z.namelist():
                raise UnsupportedFormat("ODT", "content.xml not found in ODT zip")
            data = z.read("content.xml")
            # Simple text extraction from content.xml: strip tags
            # Parse XML and extract text:p
            try:
                root = ET.fromstring(data)
                # Namespace handling: search for text:p elements
                _ns = {"text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}  # namespace for future
                texts = []
                for elem in root.iter():
                    if elem.tag.endswith("}p") or elem.tag == "text:p":
                        if elem.text:
                            texts.append(elem.text)
                        # also tail and child texts
                        for child in elem.iter():
                            if child is not elem and child.text:
                                texts.append(child.text)
                if texts:
                    return "\n".join(texts)
                # If namespace search failed, fallback to regex strip
                import re
                txt = re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="replace"))
                txt = re.sub(r"\s+", " ", txt).strip()
                if txt:
                    return txt
            except ET.ParseError:
                import re
                txt = re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="replace"))
                txt = re.sub(r"\s+", " ", txt).strip()
                return txt
    except zipfile.BadZipFile as e:
        raise RuntimeError(f"ODT extraction failed: not a valid zip: {e}")
    except UnsupportedFormat:
        raise
    except Exception as e:
        raise RuntimeError(f"ODT extraction failed: {e}")

    # If we reach here, odfpy not installed and fallback produced empty -> raise UnsupportedFormat with guidance
    raise UnsupportedFormat("ODT", "odfpy not installed and fallback empty; install odfpy: pip install odfpy")

def get_extractor(fmt: str):
    """Return extractor for format, or None."""
    return _EXTRACTORS.get(fmt.upper())

def extract(path: pathlib.Path, fmt: str | None = None) -> str:
    """High-level extract dispatching to adapters, raising UnsupportedFormat if needed."""
    if fmt is None:
        from ..main import detect as _detect  # lazy to avoid circular
        fmt = _detect(path)
    extractor = get_extractor(fmt)
    if extractor is None:
        # Unknown format -> treat as textlike if possible else unsupported
        if fmt.upper() in ("UNKNOWN",):
            raise UnsupportedFormat(fmt, "unknown format")
        # For formats like DOC, PPT, XLS, ODS, ODP which we haven't implemented fully
        if fmt.upper() in ("DOC", "PPT", "XLS", "ODS", "ODP"):
            raise UnsupportedFormat(fmt, f"{fmt} legacy format requires additional library; convert to DOCX/PPTX/XLSX/ODT")
        # Try text fallback
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            raise UnsupportedFormat(fmt, "no adapter available")
    return extractor(path)

# Public list of supported formats
SUPPORTED_FORMATS = sorted(_EXTRACTORS.keys())
