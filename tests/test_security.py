"""Regression tests for security hardening and bug fixes (v3.2.4)."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import OUTPUTS, app
from app.security import resolve_within, sanitize_filename

client = TestClient(app)


# ---------- filename sanitization ----------

def test_sanitize_strips_traversal():
    assert "/" not in sanitize_filename("../../etc/passwd")
    assert ".." not in sanitize_filename("../../etc/passwd")
    safe = sanitize_filename("..\\..\\windows\\system32\\cmd.exe")
    assert "\\" not in safe and "/" not in safe and ".." not in safe


def test_sanitize_blocks_hidden_and_empty():
    assert sanitize_filename(".env") == "env"  # leading dot stripped
    assert sanitize_filename("") == "upload.bin"
    assert sanitize_filename(None) == "upload.bin"
    assert sanitize_filename("///") == "upload.bin"
    # Persian filenames remain readable
    assert sanitize_filename("گزارش-سالانه.pdf") == "گزارش-سالانه.pdf"


# ---------- download path safety ----------

def test_download_rejects_traversal(data_tree):
    secret = data_tree["outputs"].parent / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")
    resp = client.get("/api/download/..%2Fsecret.txt")
    assert resp.status_code == 404
    resp2 = client.get("/api/download/....//secret.txt")
    assert resp2.status_code == 404
    assert "TOP SECRET" not in resp.text + resp2.text


def test_resolve_within_returns_none_for_outside():
    assert resolve_within(OUTPUTS, "../config.py") is None


def test_download_roundtrip(data_tree):
    name = "abc123.txt"
    (data_tree["outputs"] / name).write_text("hello download", encoding="utf-8")
    resp = client.get(f"/api/download/{name}")
    assert resp.status_code == 200
    assert b"hello download" in resp.content


# ---------- upload processing ----------

def test_process_sanitizes_malicious_filename(data_tree):
    resp = client.post(
        "/api/process",
        files={"file": ("../../evil.txt", b"payload", "text/plain")},
        data={"operation": "analyze"},
    )
    assert resp.status_code == 200
    j = resp.json()
    assert "/" not in j["filename"]
    assert "\\" not in j["filename"]
    assert ".." not in j["filename"]
    # all written files stay inside the uploads dir
    names = [p.name for p in data_tree["uploads"].iterdir()]
    assert len(names) == 1
    escaped = list(data_tree["uploads"].parent.parent.rglob("evil*"))
    assert escaped == []


def test_process_rejects_oversized_file(data_tree, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    resp = client.post(
        "/api/process",
        files={"file": ("big.txt", b"x" * 100, "text/plain")},
        data={"operation": "analyze"},
    )
    assert resp.status_code == 413
    # no leftover file in uploads
    assert list(data_tree["uploads"].iterdir()) == []


def test_workroom_written_per_job(data_tree):
    resp = client.post(
        "/api/process",
        files={"file": ("note.txt", b"workroom content", "text/plain")},
        data={"operation": "analyze"},
    )
    job = resp.json()["job_id"]
    wr = data_tree["workrooms"] / f"{job}.json"
    assert wr.exists()
    doc = json.loads(wr.read_text(encoding="utf-8"))
    assert doc["characters"] >= len("workroom content")


# ---------- version consistency ----------

def test_version_consistent_across_app():
    from app.config import APP_VERSION

    assert client.get("/api/health").json()["version"] == APP_VERSION
    assert app.version == APP_VERSION


# ---------- notification inbox persistence bug ----------

def test_notification_inbox_persists_new_user(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTIF_INBOX_FILE", str(tmp_path / "inbox.json"))
    # re-import service so INBOX_FILE picks up the env var
    for mod in list(sys.modules):
        if "notification" in mod:
            del sys.modules[mod]
    from app.services.notification.service import NotificationService
    from app.services.notification.types import NotificationChannel, NotificationKind, NotificationPayload

    svc = NotificationService()
    payload = NotificationPayload(
        user_id="u1", kind=NotificationKind.SYSTEM,
        title="t", title_fa="ت", body="b", body_fa="ب",
        channels=[NotificationChannel.IN_APP],
    )
    results = __import__("asyncio").run(svc.send(payload))
    assert results[0].success
    # the old bug: first message for a NEW user was appended to a throwaway list
    assert svc.list_in_app("u1") != []
    assert json.loads((tmp_path / "inbox.json").read_text(encoding="utf-8"))["u1"]
