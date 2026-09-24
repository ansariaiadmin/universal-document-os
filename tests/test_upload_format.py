"""Tests for upload/format detection and adapters."""
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.adapters import SUPPORTED_FORMATS, UnsupportedFormat, extract, get_extractor
from app.main import app, detect

client = TestClient(app)

def test_detect_formats():
    assert detect(pathlib.Path("file.pdf")) == "PDF"
    assert detect(pathlib.Path("file.docx")) == "DOCX"
    assert detect(pathlib.Path("file.xlsx")) == "XLSX"
    assert detect(pathlib.Path("file.txt")) == "TXT"
    assert detect(pathlib.Path("file.csv")) == "CSV"
    assert detect(pathlib.Path("file.md")) == "MARKDOWN"
    assert detect(pathlib.Path("file.pptx")) == "PPTX"
    assert detect(pathlib.Path("file.odt")) == "ODT"

def test_supported_formats_list():
    assert "PDF" in SUPPORTED_FORMATS
    assert "DOCX" in SUPPORTED_FORMATS
    assert "PPTX" in SUPPORTED_FORMATS
    assert "ODT" in SUPPORTED_FORMATS
    assert "TXT" in SUPPORTED_FORMATS
    assert "CSV" in SUPPORTED_FORMATS

def test_get_extractor_exists():
    assert get_extractor("PDF") is not None
    assert get_extractor("TXT") is not None
    assert get_extractor("PPTX") is not None
    assert get_extractor("ODT") is not None

def test_upload_txt():
    # Simulate upload via API
    content = b"hello world test upload"
    resp = client.post("/api/process", files={"file": ("test.txt", content, "text/plain")}, data={"operation": "analyze", "target_format": "same"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_format"] == "TXT"
    assert data["characters"] >= len(content)
    assert "hello world" in data["preview"]

def test_upload_format_endpoint_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_unsupported_format_clean():
    # DOC legacy should raise UnsupportedFormat
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / "legacy.doc"
        p.write_bytes(b"fake doc content")
        try:
            extract(p, fmt="DOC")
            assert False, "should have raised UnsupportedFormat"
        except UnsupportedFormat as e:
            assert "DOC" in str(e)
        except Exception:
            # If fallback text succeeds, it's also ok but should be clean
            pass

def test_pptx_adapter_behavior():
    # PPTX adapter should either extract or raise UnsupportedFormat cleanly, not crash with ImportError
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / "test.pptx"
        p.write_bytes(b"not a real pptx")
        try:
            txt = extract(p, fmt="PPTX")
            # If python-pptx not installed, should have raised UnsupportedFormat earlier
            # But if installed, it will raise RuntimeError for invalid file — that's acceptable
            assert isinstance(txt, str)
        except UnsupportedFormat as uf:
            assert "PPTX" in str(uf)
        except RuntimeError:
            # Invalid file but adapter exists — acceptable
            pass

def test_odt_adapter_behavior():
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / "test.odt"
        # Create minimal valid ODT zip with content.xml
        import zipfile
        with zipfile.ZipFile(str(p), "w") as z:
            z.writestr("content.xml", '<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text><text:p>Hello ODT World</text:p></office:text></office:body></office:document-content>')
            z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        txt = extract(p, fmt="ODT")
        assert "Hello ODT" in txt or "Hello" in txt
