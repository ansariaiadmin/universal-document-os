"""Tests for PDF/TXT/CSV/MD extraction and audit."""
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pathlib import Path

from app.adapters import extract as adapter_extract
from app.main import BASE, audit, detect, extract_text


def test_extract_txt():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.txt"
        p.write_text("Hello TXT world\nSecond line", encoding="utf-8")
        txt = extract_text(p)
        assert "Hello TXT" in txt
        assert "Second line" in txt

def test_extract_md():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.md"
        p.write_text("# Title\n\nThis is **markdown** content", encoding="utf-8")
        txt = extract_text(p)
        assert "Title" in txt
        assert "markdown" in txt

def test_extract_csv():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.csv"
        p.write_text("a,b,c\n1,2,3\n4,5,6", encoding="utf-8")
        txt = extract_text(p)
        assert "a,b,c" in txt
        assert "1,2,3" in txt

def test_extract_pdf_blank_or_error():
    # Create a minimal PDF via pypdf if possible, else test error handling
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.pdf"
        try:
            from pypdf import PdfWriter
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            with open(p, "wb") as f:
                writer.write(f)
            txt = extract_text(p)
            # Blank page may produce empty string, but should not be error marker
            assert "[EXTRACTION_ERROR]" not in txt
        except Exception:
            # If pypdf not working, at least ensure function doesn't crash
            p.write_bytes(b"%PDF-1.4 fake")
            txt = extract_text(p)
            assert isinstance(txt, str)

def test_audit_log():
    # Ensure audit creates jsonl entry
    audit_file = BASE / "data/audit.jsonl"
    # Clean up old if exists for test isolation? Don't delete, just check appends
    before = audit_file.exists()  # noqa: F841 and audit_file.stat().st_size or 0
    audit("TEST_EVENT", job_id="test123", filename="test.txt")
    assert audit_file.exists()
    content = audit_file.read_text(encoding="utf-8", errors="replace")
    assert "TEST_EVENT" in content
    # Last line should be valid json
    last_line = content.strip().splitlines()[-1]
    rec = json.loads(last_line)
    assert rec["event"] == "TEST_EVENT"
    assert rec["job_id"] == "test123"

def test_detect_and_adapter_extract_consistency():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "doc.txt"
        p.write_text("consistency check", encoding="utf-8")
        fmt = detect(p)
        assert fmt == "TXT"
        txt = adapter_extract(p, fmt=fmt)
        assert "consistency" in txt
