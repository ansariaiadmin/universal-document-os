"""v4.1 — adaptive intelligence, content guard, rate limiting, extraction budgets."""
import io
import pytest
import zipfile

from app.intelligence import analyze, classify_document, detect_language


def test_detect_persian():
    r = detect_language("این یک سند آزمایشی فارسی است که با کلمات پرکاربرد نوشته شده است.")
    assert r["language"] == "fa" and r["confidence"] >= 0.5


def test_detect_english_and_direction():
    r = detect_language(
        "The quick brown document is a report that lists the findings "
        "and the analysis of this quarter with their recommendations."
    )
    assert r["language"] == "en"
    full = analyze("The report summarizes the findings and their conclusions for the team.")
    assert full["direction"] == "ltr"


def test_classify_invoice_vs_resume():
    inv = classify_document("INVOICE Total Due: $500 VAT ID 123 Bill To Acme qty price")
    res = classify_document("Curriculum Vitae — work experience, education, skills")
    assert inv["category"] == "invoice"
    assert res["category"] == "resume"


def test_unknown_when_too_short():
    assert detect_language("hi")["language"] == "und"


def test_process_returns_intelligence(client):
    data = {"file": ("doc.md", io.BytesIO(b"# Report\n\nThis report contains the analysis and its findings."), "text/markdown")}
    r = client.post("/api/process", files=data, data={"operation": "analyze"})
    assert r.status_code == 200
    intel = r.json()["intelligence"]
    assert intel["language"] == "en"
    assert intel["category"] in {"report", "general"}


def test_binary_spoof_rejected(client, tmp_path):
    # OLE magic bytes renamed to .txt -> UNKNOWN format + binary payload -> 415
    payload = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(range(256)) * 40
    r = client.post(
        "/api/process",
        files={"file": ("evil.txt", io.BytesIO(payload), "text/plain")},
        data={"operation": "analyze"},
    )
    assert r.status_code == 415
    assert "content rejected" in r.json()["detail"]


def test_pdf_spoof_rejected(client):
    # zip magic claiming .pdf extension
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.txt", "hello")
    r = client.post(
        "/api/process",
        files={"file": ("fake.pdf", io.BytesIO(buf.getvalue()), "application/pdf")},
        data={"operation": "analyze"},
    )
    assert r.status_code == 415


def test_legit_docx_still_works(client):
    from docx import Document

    buf = io.BytesIO()
    d = Document()
    d.add_paragraph("Hello universal document world, the report of findings.")
    d.save(buf)
    r = client.post(
        "/api/process",
        files={"file": ("ok.docx", io.BytesIO(buf.getvalue()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"operation": "analyze"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["detected_format"] == "DOCX"
    assert "Hello" in body["preview"]
    assert body["intelligence"]["language"] == "en"


def test_zip_bomb_guard(tmp_path):
    import pytest

    from app.content_guard import ContentRejected, check_zip_bomb

    p = tmp_path / "bomb.docx"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.xml", b"A" * (5 * 1024 * 1024))  # 5 MB declared
    with pytest.raises(ContentRejected):
        check_zip_bomb(p, max_total_bytes=1024 * 1024)  # 1 MB budget


def test_status_reports_features(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert "uptime_seconds" in body
    assert set(body["features"]) == {"auth", "rate_limit_per_min", "max_upload_bytes"}


def test_rate_limiter_unit():
    from app.ratelimit import SlidingWindowLimiter

    lim = SlidingWindowLimiter()
    results = [lim.allow("k", 3)[0] for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_extraction_budget_cap(monkeypatch, tmp_path):
    from app import adapters

    monkeypatch.setattr(adapters, "MAX_TEXT_CHARS", 100)
    f = tmp_path / "long.txt"
    f.write_text("word " * 500, encoding="utf-8")
    out = adapters.extract(f, fmt="TXT")
    assert "[TRUNCATED" in out
    assert len(out) < 200


def test_guard_blocks_dosexec_disguised_as_pdf(tmp_path):
    """MZ header renamed to .pdf must be rejected (live-bypass found in audit)."""
    from app.content_guard import ContentRejected, verify
    p = tmp_path / "report.pdf"
    p.write_bytes(b"MZ\x90\x00" + b"x" * 200)
    with pytest.raises(ContentRejected):
        verify(p, "PDF", 10_000_000)


def test_guard_blocks_elf_disguised_as_docx(tmp_path):
    from app.content_guard import ContentRejected, verify
    p = tmp_path / "invoice.docx"
    p.write_bytes(b"\x7fELF\x02\x01" + b"x" * 200)
    with pytest.raises(ContentRejected):
        verify(p, "DOCX", 10_000_000)


def test_guard_blocks_shebang_script_as_txt_ext(tmp_path):
    from app.content_guard import ContentRejected, verify
    p = tmp_path / "notes.sh"
    p.write_bytes(b"#!/bin/sh\nrm -rf /\n")
    with pytest.raises(ContentRejected):
        verify(p, "UNKNOWN", 10_000_000)
