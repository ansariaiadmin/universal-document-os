"""Tests for the OCR wiring refactor (v3.2.5).

Covers:
- single source of truth for format detection (adapters.format_of)
- images route through the multi-engine OCR orchestrator
- honest failure: no engine available => UnsupportedFormat, never fake text
- OpenDocument adapters (ODT/ODS/ODP) work with zero external deps
- no circular imports between main/adapters/ocr
"""
import pathlib
import sys
import zipfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.adapters import (
    SUPPORTED_FORMATS,
    UnsupportedFormat,
    extract,
    format_of,
)


@pytest.fixture
def patch_engines(monkeypatch):
    """Replace the singleton's engine list so tests never touch real binaries."""
    import app.ocr.multi_engine as me

    def _patch(engines):
        monkeypatch.setattr(me.ocr, "engines", engines)
    return _patch


# ---------- format detection: one registry, one truth ----------

def test_format_of_mapping():
    assert format_of(pathlib.Path("a.pdf")) == "PDF"
    assert format_of(pathlib.Path("a.DOCX")) == "DOCX"
    assert format_of(pathlib.Path("scan.PNG")) == "IMAGE"
    assert format_of(pathlib.Path("photo.jpeg")) == "IMAGE"
    assert format_of(pathlib.Path("mystery.xyz123")) == "UNKNOWN"


def test_main_detect_delegates_to_adapters(tmp_path):
    """app.main.detect must agree with adapters.format_of (no duplicated table)."""
    from app.main import detect
    p = tmp_path / "doc.txt"
    p.write_text("x", encoding="utf-8")
    assert detect(p) == format_of(p) == "TXT"
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert detect(img) == "IMAGE"


# ---------- image -> OCR routing (honest behavior) ----------

def test_image_without_engine_raises_cleanly(patch_engines, tmp_path):
    """When no OCR engine is usable, extraction must fail honestly — not fabricate."""
    from app.ocr.multi_engine import OCREngine

    class _Skipped:
        def extract(self, path):
            return {"text": "", "confidence": 0.0, "engine": "fake", "skipped": True}

    patch_engines( [OCREngine("fake", _Skipped().extract)])
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    try:
        extract(img)
        assert False, "expected UnsupportedFormat when no engine is available"
    except UnsupportedFormat as e:
        assert "IMAGE" in str(e)


def test_image_with_working_engine_returns_real_text(patch_engines, tmp_path):
    """A working engine's output flows through extract() untouched."""
    from app.ocr.multi_engine import OCREngine

    patch_engines( [
        OCREngine("fake", lambda p: {"text": "hello ocr world", "confidence": 0.9, "engine": "fake"})
    ])
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    assert extract(img) == "hello ocr world"


def test_image_empty_result_reports_no_text(patch_engines, tmp_path):
    """Detected-nothing must surface as [NO_TEXT_DETECTED], never invented words."""
    from app.ocr.multi_engine import OCREngine

    patch_engines( [
        OCREngine("fake", lambda p: {"text": "   ", "confidence": 0.5, "engine": "fake"})
    ])
    img = tmp_path / "blank.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert extract(img) == "[NO_TEXT_DETECTED]"


def test_multi_engine_picks_best_confidence():
    from app.ocr.multi_engine import MultiEngineOCR, OCREngine

    engines = [
        OCREngine("low", lambda p: {"text": "weak", "confidence": 0.3, "engine": "low"}),
        OCREngine("high", lambda p: {"text": "strong", "confidence": 0.9, "engine": "high"}),
        OCREngine("skip", lambda p: {"text": "", "confidence": 0.0, "engine": "skip", "skipped": True}),
    ]
    best = MultiEngineOCR(engines=engines).extract("whatever.png")
    assert best["engine"] == "high" and best["text"] == "strong"
    assert len(best["all_results"]) == 2  # skipped engine excluded


# ---------- OpenDocument formats without external libraries ----------

def _make_odx(tmp_path, name, member_xml):
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("content.xml", member_xml)
    return p


def test_odt_extraction_zero_deps(tmp_path):
    xml = (
        '<?xml version="1.0"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        '<office:body><office:text>'
        '<text:p>Hello ODT world</text:p><text:p>Second paragraph</text:p>'
        '</office:text></office:body></office:document-content>'
    )
    p = _make_odx(tmp_path, "doc.odt", xml)
    txt = extract(p)
    assert "Hello ODT world" in txt and "Second paragraph" in txt


def test_ods_extraction_zero_deps(tmp_path):
    xml = (
        '<?xml version="1.0"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        '<office:body><office:spreadsheet><table:table>'
        '<table:table-cell><text:p>Revenue</text:p></table:table-cell>'
        '<table:table-cell><text:p>42000</text:p></table:table-cell>'
        '</table:table></office:spreadsheet></office:body></office:document-content>'
    )
    p = _make_odx(tmp_path, "sheet.ods", xml)
    txt = extract(p)
    assert "Revenue" in txt and "42000" in txt


def test_opendocument_registered_formats():
    for fmt in ("ODT", "ODS", "ODP"):
        assert fmt in SUPPORTED_FORMATS


def test_bad_zip_opendocument_raises_runtime(tmp_path):
    p = tmp_path / "broken.odt"
    p.write_bytes(b"not a zip at all")
    try:
        extract(p)
        assert False, "expected RuntimeError for corrupt archive"
    except RuntimeError as e:
        assert "zip" in str(e).lower()


# ---------- architecture guardrails ----------

def test_no_circular_import_main_to_adapters():
    """Importing adapters alone must not require app.main (no back-edge)."""
    import subprocess
    code = (
        "import sys; import app.adapters;"
        "print('app.main' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=str(pathlib.Path(__file__).parent.parent))
    assert out.stdout.strip().endswith("False"), out.stdout + out.stderr
