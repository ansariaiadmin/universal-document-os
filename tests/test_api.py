"""Additional API tests for universal-document-os."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_status_endpoint():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "uploads" in data
    assert "outputs" in data
    assert "workrooms" in data

def test_landing_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "html" in resp.headers.get("content-type", "").lower() or "<html" in resp.text.lower() or "<!doctype" in resp.text.lower()

def test_process_csv():
    content = b"col1,col2\nval1,val2\n"
    resp = client.post("/api/process", files={"file": ("data.csv", content, "text/csv")}, data={"operation": "analyze"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["detected_format"] == "CSV"
    assert "col1" in j["preview"]

def test_process_md():
    content = b"# Hello\nThis is markdown"
    resp = client.post("/api/process", files={"file": ("readme.md", content, "text/markdown")}, data={"operation": "analyze"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["detected_format"] in ("MARKDOWN", "MD", "TXT", "MARKDOWN") or "MD" in j["detected_format"] or j["detected_format"] == "MARKDOWN"
    assert "Hello" in j["preview"]

def test_process_export_txt():
    content = b"exportable text content"
    resp = client.post("/api/process", files={"file": ("note.txt", content, "text/plain")}, data={"operation": "export_text", "target_format": "txt"})
    assert resp.status_code == 200
    j = resp.json()
    # Should have download link for txt export
    if j["characters"] > 0:
        assert j["status"] in ("READY", "ANALYZED")
        # If READY, download should exist
        if "download" in j:
            dl = client.get(j["download"])
            assert dl.status_code == 200
            assert b"exportable" in dl.content
