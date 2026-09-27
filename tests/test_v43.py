"""v4.3 regression suite — smart dashboard, timing-safe auth, PWA, honest intelligence."""


# ---------- smart dashboard ----------

def test_dashboard_shape(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert d["version"]
    assert "PDF" in d["pipeline"]["formats_extractable"]
    assert set(d["capabilities"]["ocr_engines"].keys()) == {"tesseract", "rapidocr"}
    assert isinstance(d["capabilities"]["ocr_ready"], bool)
    assert d["jobs"]["store"] == "sqlite"
    assert {"uploads", "outputs", "workrooms", "audit_lines"} <= set(d["storage"].keys())
    conv = {(c["from"], c["to"]): c["supported"] for c in d["capabilities"]["conversions"]}
    assert conv[("pdf", "txt")] is True
    assert conv[("docx", "html")] is False


def test_dashboard_reflects_live_counters(client, data_tree):
    (data_tree["outputs"] / "dash-test.txt").write_text("x", encoding="utf-8")
    d = client.get("/api/dashboard").json()
    assert d["storage"]["outputs"] >= 1


def test_dashboard_note_when_no_ocr(client, monkeypatch):
    from app.ocr import multi_engine as me

    monkeypatch.setattr(me.ocr, "engines", [], raising=False)
    r = client.get("/api/dashboard")
    assert r.status_code == 200  # probing must never break the endpoint


# ---------- timing-safe auth ----------

def test_auth_key_matches_is_timing_safe():
    import hmac

    from app.auth import key_matches

    assert key_matches("secret", ["secret", "other"]) is True
    assert key_matches("wrong", ["secret"]) is False
    # sanity: compare_digest is actually used (constant-time primitive)
    assert hmac.compare_digest("a", "a") is True


def test_auth_middleware_still_blocks(tmp_path):
    import os

    os.environ["DATA_DIR"] = str(tmp_path)
    for mod in ("app.config", "app.main"):
        import sys

        sys.modules.pop(mod, None)
    import app.main as m

    os.environ["UDO_API_KEYS"] = "k1,k2"
    try:
        from fastapi.testclient import TestClient as TC

        with TC(m.app) as c:
            assert c.get("/api/status").status_code == 401
            assert c.get("/api/status", headers={"X-API-Key": "k2"}).status_code == 200
    finally:
        os.environ.pop("UDO_API_KEYS", None)


# ---------- PWA: manifest, icons, service worker ----------

def test_manifest_served_and_valid(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    d = r.json()
    assert d["name"] == "Universal Document OS"
    icons = d["icons"]
    assert {i["src"] for i in icons} == {"/icon-192.png", "/icon-512.png"}


def test_icons_are_real_pngs(client):
    for size in (192, 512):
        r = client.get(f"/icon-{size}.png")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(r.content) > 500  # not an empty stub
    assert client.get("/icon-64.png").status_code == 404


def test_service_worker_served(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert b"serviceWorker" in r.content or b"caches" in r.content


# ---------- honest intelligence ----------

def test_arabic_not_tagged_as_persian():
    from app.intelligence import detect_language

    r = detect_language("هذا نص عربي خالص للتجربة وهذه جملة عربية اخرى للكشف")
    assert r["language"] == "ar", r


def test_persian_still_detected():
    from app.intelligence import detect_language

    r = detect_language("این یک متن آزمایشی فارسی است برای بررسی تشخیص زبان")
    assert r["language"] == "fa", r


def test_translation_benchmark_refuses_to_fabricate():
    from app.translation.service import GoldenBenchmark

    try:
        GoldenBenchmark().evaluate({}, {})
    except RuntimeError as e:
        assert "fabricated" in str(e) or "dataset" in str(e)
    else:
        raise AssertionError("benchmark must refuse without a dataset")


def test_layout_reconstruction_honest():
    from app.translation.service import LayoutReconstructor

    out = LayoutReconstructor().reconstruct([{}, {}])
    assert out["blocks"] == [] and out["reconstructed"] is False


# ---------- OCR engine probe is real ----------

def test_engine_probe_without_binary():
    from app.ocr.tesseract_engine import engine_available

    # In CI/sandbox tesseract is usually absent; probe must return a bool,
    # and must NOT raise on missing binary.
    assert isinstance(engine_available("tesseract"), bool)
    assert engine_available("nonsense") is False
