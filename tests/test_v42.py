"""v4.2 regression suite — durable jobs, conversion engine, sweep task."""
import sqlite3

from fastapi.testclient import TestClient


# ---------- durable job store (SQLite) ----------

def test_job_store_survives_reload(tmp_path, monkeypatch):
    """A job created before an app reload must still be pollable after it."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    main1 = _fresh_app(tmp_path)
    r = main1.app  # noqa: F841  (ensure module imported)
    from app.jobs import JobStore

    store = JobStore(tmp_path / "jobs.db")
    store.create("abc123", filename="x.md", format="MD")
    store.finish("abc123", "READY", {"characters": 42})
    del store
    # New process-equivalent handle on the same file:
    store2 = JobStore(tmp_path / "jobs.db")
    rec = store2.get("abc123")
    assert rec and rec["state"] == "READY"
    assert rec["result"]["characters"] == 42


def _fresh_app(data_dir):
    import os
    import sys

    os.environ["DATA_DIR"] = str(data_dir)
    for mod in ("app.config", "app.main"):
        sys.modules.pop(mod, None)
    import app.main as m

    return m


def test_job_polling_after_process(client):
    r = client.post(
        "/api/process",
        files={"file": ("a.md", b"# hello\nworld", "text/markdown")},
        data={"operation": "analyze"},
    )
    assert r.status_code == 200
    job = r.json()["job_id"]
    p = client.get(f"/api/job/{job}")
    assert p.status_code == 200
    body = p.json()
    assert body["state"] == "ANALYZED"
    assert body["result"]["job_id"] == job


def test_jobs_list_reflects_store(client):
    client.post("/api/process", files={"file": ("b.txt", b"hi", "text/plain")})
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_sweep_removes_expired(tmp_path):
    from app.jobs import JobStore

    s = JobStore(tmp_path / "j.db", ttl_seconds=0)
    s.create("old", filename="f")
    s.finish("old", "READY", {})
    assert s.sweep() == 1
    assert s.get("old") is None


def test_finish_race_creates_record(tmp_path):
    """finish() on a missing id must not silently drop the terminal state."""
    from app.jobs import JobStore

    s = JobStore(tmp_path / "j.db")
    s.finish("ghost", "READY", {"ok": True})
    rec = s.get("ghost")
    assert rec and rec["state"] == "READY" and rec["result"]["ok"] is True


def test_wal_mode_enabled(tmp_path):
    from app.jobs import JobStore

    JobStore(tmp_path / "j.db")
    conn = sqlite3.connect(tmp_path / "j.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


# ---------- conversion engine ----------

def test_convert_md_to_html(client):
    md = b"# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```py\nprint(1)\n```\n"
    r = client.post(
        "/api/process",
        files={"file": ("doc.md", md, "text/markdown")},
        data={"operation": "convert", "target_format": "html"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "READY"
    d = client.get(body["download"])
    assert d.status_code == 200
    html = d.text
    assert "<h1>Title</h1>" in html and "<table>" in html and "print(1)" in html


def test_convert_txt_export(client):
    r = client.post(
        "/api/process",
        files={"file": ("n.md", b"# hi there", "text/markdown")},
        data={"operation": "convert", "target_format": "txt"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "READY"
    txt = client.get(body["download"]).text
    assert "hi there" in txt


def test_convert_unsupported_target_400(client):
    r = client.post(
        "/api/process",
        files={"file": ("d.pdfx", b"%PDF-1.4 fake-not-real", "application/pdf")},
        data={"operation": "convert", "target_format": "docx"},
    )
    assert r.status_code == 400
    assert "not supported" in r.json()["detail"]


def test_convert_gate_docx_to_html_rejected(client):
    """Binary office formats may not claim HTML rendering (honest gate)."""
    from app.converter import can_convert

    assert can_convert("DOCX", "md") is True
    assert can_convert("DOCX", "html") is False
    assert can_convert("MARKDOWN", "html") is True
    assert can_convert("PDF", "pdf") is False


def test_converter_missing_dep_raises(monkeypatch):
    import builtins

    import app.converter as conv

    real_import = builtins.__import__

    def no_markdown(name, *a, **k):
        if name == "markdown":
            raise ImportError("blocked")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_markdown)
    try:
        conv.md_to_html("# x")
    except conv.ConversionError as e:
        assert e.code == "missing_dep"
    else:
        raise AssertionError("ConversionError expected")


# ---------- lifespan sweep task ----------

def test_lifespan_starts_and_stops_cleanly(tmp_path):
    """App context exit must not hang or leak the sweeper task."""
    main = _fresh_app(tmp_path)
    with TestClient(main.app) as c:
        assert c.get("/api/health").json()["version"] == main.APP_VERSION
    # re-import session default so other fixtures stay consistent
    _fresh_app(tmp_path)
