"""Tests for the v3.3–v3.6 enterprise features (jobs, auth, metrics, lifecycle).

NOTE: these tests build their own TestClient against app.main.app directly
(not the session-reloaded fixture app) because the job store lives in the
main module instance; DATA_DIR is pointed at a tmp dir so nothing touches
the repo's real data/.
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import sys

from fastapi.testclient import TestClient

from app.auth import api_keys, auth_enabled
from app.jobs import JobStore


def _fresh_main_client(tmp_path: pathlib.Path):
    """(Re)import app.config + app.main isolated to tmp_path and open a client."""
    os.environ["DATA_DIR"] = str(tmp_path / "data")
    ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    for mod in ("app.config", "app.main"):
        sys.modules.pop(mod, None)
    import app.main as main_mod

    return TestClient(main_mod.app), main_mod


def _upload(client: TestClient, name="note.md", content=b"# Hello\nSome text"):
    return client.post(
        "/api/process",
        files={"file": (name, io.BytesIO(content), "text/markdown")},
        data={"operation": "analyze"},
    )


# ---------------- job store unit tests ----------------

def test_job_store_lifecycle():
    store = JobStore(ttl_seconds=1)
    store.create("j1", filename="a.txt")
    assert store.get("j1")["state"] == "QUEUED"
    store.update("j1", state="RUNNING")
    assert store.get("j1")["state"] == "RUNNING"
    store.finish("j1", "DONE", {"ok": True})
    rec = store.get("j1")
    assert rec["state"] == "DONE" and rec["result"]["ok"] is True
    assert store.stats()["DONE"] == 1


def test_job_store_expiry(monkeypatch):
    store = JobStore(ttl_seconds=0)
    store.create("j2")
    store.finish("j2", "DONE", {})
    # force it into the past via the public aging helper
    store.age("j2", 10)
    assert store.sweep() == 1
    assert store.get("j2") is None


def test_job_store_missing_returns_none():
    assert JobStore().get("nope") is None


# ---------------- API integration tests ----------------

def test_process_registers_job_and_polling_works(tmp_path):
    client, _ = _fresh_main_client(tmp_path)
    resp = _upload(client)
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    poll = client.get(f"/api/job/{job_id}")
    assert poll.status_code == 200
    body = poll.json()
    assert body["state"] in {"ANALYZED", "READY"}
    assert body["result"]["filename"] == "note.md"

    missing = client.get("/api/job/deadbeef")
    assert missing.status_code == 404

    listing = client.get("/api/jobs")
    assert listing.status_code == 200
    assert listing.json()["count"] >= 1
    assert any(j["job_id"] == job_id for j in listing.json()["jobs"])


def test_metrics_endpoint_serves_prometheus_format(tmp_path):
    client, _ = _fresh_main_client(tmp_path)
    client.get("/api/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"udo_http_requests_total" in resp.content


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.delenv("UDO_API_KEYS", raising=False)
    assert auth_enabled() is False
    assert api_keys() == []


def test_auth_middleware_blocks_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("UDO_API_KEYS", "secret-key-1, secret-key-2")
    assert api_keys() == ["secret-key-1", "secret-key-2"]
    client, _ = _fresh_main_client(tmp_path)
    resp = client.get("/api/status")
    assert resp.status_code == 401
    ok = client.get("/api/status", headers={"X-API-Key": "secret-key-2"})
    assert ok.status_code == 200
    # health stays public for uptime probes
    assert client.get("/api/health").status_code == 200


def test_legacy_doc_error_is_actionable():
    from app.adapters import UnsupportedFormat, extract
    from app.adapters.legacy import LegacyToolMissing, extract_doc

    fake = __import__("pathlib").Path("whatever.doc")
    try:
        extract(fake, fmt="DOC")
    except UnsupportedFormat as e:
        assert "antiword" in str(e) or "convert" in str(e)
    else:
        raise AssertionError("DOC without antiword must raise UnsupportedFormat")
    assert LegacyToolMissing is not None and callable(extract_doc)


def test_json_formatter_emits_valid_lines():
    import logging

    from app.lifecycle import JsonFormatter

    rec = logging.LogRecord("udo", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    payload = json.loads(JsonFormatter().format(rec))
    assert payload["msg"] == "hello world"
    assert payload["level"] == "INFO"
    assert isinstance(payload["ts"], float)
