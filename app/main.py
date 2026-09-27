"""Universal Document OS — FastAPI application entry point."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    APP_NAME,
    APP_VERSION,
    AUDIT_FILE,
    BASE,
    MAX_EXTRACT_BYTES,
    MAX_UPLOAD_BYTES,
    OUTPUTS,
    PREVIEW_CHARS,
    UPLOADS,
    WORKROOMS,
    ensure_dirs,
)
from app.jobs import JOBS
from app.security import resolve_within, sanitize_filename

logger = logging.getLogger("udo")

_START_TS = time.time()

ensure_dirs()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """v3.6 — graceful startup/shutdown hooks; v4.2 adds periodic job sweep."""
    import asyncio

    from app.lifecycle import configure_json_logging, graceful_shutdown

    configure_json_logging()
    logger.info("Universal Document OS %s started", APP_VERSION)
    stop = asyncio.Event()

    async def _sweeper():
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=_SWEEP_INTERVAL)
            except TimeoutError:
                removed = JOBS.sweep()
                if removed:
                    logger.info("job sweep removed %d expired records", removed)

    sweeper = asyncio.create_task(_sweeper())
    yield
    stop.set()
    await sweeper
    await graceful_shutdown(_app)


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE / "app/static"), name="static")
templates = Jinja2Templates(directory=BASE / "app/templates")

# --- v3.5: optional API-key guard + Prometheus metrics -------------------
from app.auth import api_key_guard  # noqa: E402
from app.content_guard import ContentRejected  # noqa: E402
from app.content_guard import verify as content_verify  # noqa: E402
from app.metrics import metrics_response, request_counter  # noqa: E402
from app.ratelimit import rate_limit_guard  # noqa: E402

app.middleware("http")(api_key_guard)
app.middleware("http")(rate_limit_guard)


@app.middleware("http")
async def count_requests(request: Request, call_next):
    request_counter.labels(request.method).inc()
    return await call_next(request)


# v4.2 — periodic TTL sweep so the durable job store never grows unbounded.
_SWEEP_INTERVAL = 300.0


@app.get("/metrics")
async def metrics():
    return metrics_response()


def audit(event: str, **kw) -> None:
    """Append a structured audit record (single atomic write)."""
    rec = {"ts": time.time(), "event": event, **kw}
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:  # never let auditing crash the request path
        logger.warning("audit write failed: %s", e)


def detect(path) -> str:
    """Canonical format detection — delegates to the adapters registry."""
    from app.adapters import format_of
    return format_of(path)


def extract_text(path) -> str:
    """Dispatch to adapters package with clean UnsupportedFormat handling."""
    from app.adapters import UnsupportedFormat
    from app.adapters import extract as adapter_extract

    fmt = detect(path)
    try:
        return adapter_extract(path, fmt=fmt)
    except UnsupportedFormat as uf:
        return f"[UNSUPPORTED_FORMAT] {uf.fmt}: {uf.reason or 'no adapter'}"
    except Exception:
        logger.exception("extraction failed for %s", path.name)
        return "[EXTRACTION_ERROR] extraction failed; see server log for details"


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html")


@app.get("/app", response_class=HTMLResponse)
async def panel(request: Request):
    return templates.TemplateResponse(
        request, "panel_vscode.html", {"version": APP_VERSION}
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


@app.get("/api/dashboard")
async def dashboard():
    """Smart dashboard feed (v4.3) — live, honest facts about THIS deployment.

    Everything here is measured at request time: formats come from the real
    adapter registry, OCR engine availability is probed for real, counts come
    from the live job store and the data/ tree. No fabricated numbers.
    """
    from app.adapters import SUPPORTED_FORMATS
    from app.auth import auth_enabled
    from app.intelligence import _CATEGORIES
    from app.ratelimit import _limit

    def _dir_size(d) -> int:
        try:
            return sum(f.stat().st_size for f in d.iterdir() if f.is_file())
        except OSError:
            return 0

    def _line_count(p) -> int:
        try:
            with open(p, "rb") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0

    # Real OCR engine probes (deps + binary), not guesses.
    try:
        from app.ocr.multi_engine import ocr as _ocr
        ocr_engines = {name: ok for name, ok in _ocr.health().items()}
        ocr_ready = any(ocr_engines.values())
    except Exception:  # probing must never break the dashboard
        ocr_engines, ocr_ready = {}, False

    # Converter capabilities, straight from the engine's gate.
    from app.converter import can_convert
    conversions = [
        {"from": fmt.lower(), "to": target, "supported": can_convert(fmt, target)}
        for fmt in ("PDF", "DOCX", "MARKDOWN", "TXT")
        for target in ("txt", "md", "html")
    ]

    stats = JOBS.stats()
    return {
        "version": APP_VERSION,
        "uptime_seconds": round(time.time() - _START_TS, 1),
        "pipeline": {
            "formats_extractable": SUPPORTED_FORMATS,
            "formats_detected": [
                "PDF", "DOCX", "DOC", "XLSX", "XLS", "PPTX", "PPT",
                "ODT", "ODS", "ODP", "TXT", "MARKDOWN", "MD", "CSV",
                "JSON", "HTML", "RTF", "IMAGE",
            ],
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "preview_chars": PREVIEW_CHARS,
        },
        "capabilities": {
            "ocr_engines": ocr_engines,
            "ocr_ready": ocr_ready,
            "ocr_langs": __import__("os").getenv("OCR_LANGS", "eng+fas"),
            "conversions": conversions,
            "intelligence_categories": sorted(_CATEGORIES.keys()),
            "translation_wired": False,  # honest: service exists, no endpoint yet
        },
        "security": {
            "auth_enabled": auth_enabled(),
            "rate_limit_per_min": _limit(),
            "max_upload_bytes": MAX_UPLOAD_BYTES,
        },
        "jobs": {
            "store": "sqlite",
            **stats,
        },
        "storage": {
            "uploads": _count_files(UPLOADS),
            "outputs": _count_files(OUTPUTS),
            "workrooms": _count_files(WORKROOMS),
            "uploads_bytes": _dir_size(UPLOADS),
            "outputs_bytes": _dir_size(OUTPUTS),
            "audit_lines": _line_count(AUDIT_FILE),
        },
    }


def _count_files(d) -> int:
    try:
        return sum(1 for _ in d.iterdir())
    except OSError:
        return 0


@app.post("/api/process")
async def process(
    file: UploadFile = File(...),
    operation: str = Form("analyze"),
    target_format: str = Form("same"),
):
    job = uuid.uuid4().hex
    safe = sanitize_filename(file.filename)
    src = UPLOADS / f"{job}_{safe}"

    size = 0
    with src.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                src.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"file too large (limit {MAX_UPLOAD_BYTES} bytes)",
                )
            out.write(chunk)

    fmt = detect(src)
    # v4.1 — adaptive content gate: magic bytes must agree with the claimed
    # extension, binary junk can't ride the text fallback, zip bombs are cut.
    try:
        await asyncio.to_thread(content_verify, src, fmt, MAX_EXTRACT_BYTES)
    except ContentRejected as cr:
        src.unlink(missing_ok=True)
        audit("REJECTED", filename=safe, reason=str(cr))
        raise HTTPException(status_code=415, detail=f"content rejected: {cr}")
    # Extraction is CPU-bound — run it off the event loop so uploads stay snappy.
    text = await asyncio.to_thread(extract_text, src)
    # v4.1 — per-document intelligence: language, direction, category, stats.
    from app.intelligence import analyze  # local import keeps startup lean

    intel = await asyncio.to_thread(analyze, text) if text else {}
    result = {
        "job_id": job,
        "filename": safe,
        "detected_format": fmt,
        "operation": operation,
        "target_format": target_format,
        "size_bytes": size,
        "characters": len(text),
        "status": "ANALYZED",
        "preview": text[:PREVIEW_CHARS],
        "intelligence": intel,
    }
    (WORKROOMS / f"{job}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    audit("ANALYZE", job_id=job, filename=safe, format=fmt, operation=operation, size=size)

    # v4.2 — real conversion engine: any extracted text exports to txt/md,
    # markup sources render to styled HTML. Unknown targets fail cleanly.
    if operation in {"copy", "export_text", "convert"} and text:
        from app.converter import ConversionError, can_convert, convert

        if target_format not in {"same", ""} and not can_convert(fmt, target_format):
            src.unlink(missing_ok=True)
            audit("CONVERT_REJECTED", job_id=job, format=fmt, target=target_format)
            raise HTTPException(
                status_code=400,
                detail=f"conversion {fmt.lower()}->{target_format} not supported "
                       "(targets: txt, md, html)",
            )
        if target_format in {"txt", "md", "html"}:
            try:
                rendered = await asyncio.to_thread(convert, text, to=target_format)
            except ConversionError as ce:
                raise HTTPException(status_code=501, detail=str(ce))
            outp = OUTPUTS / f"{job}.{target_format}"
            outp.write_text(rendered, encoding="utf-8")
            result["download"] = f"/api/download/{outp.name}"
            result["status"] = "READY"

    # Register terminal state in the live job store for polling clients.
    # create() first so the record exists even when finish() races a restart.
    JOBS.create(job, filename=safe, format=fmt)
    JOBS.finish(job, result["status"], result)
    return JSONResponse(result)


@app.get("/api/job/{job_id}")
async def job_status(job_id: str):
    """Poll a processing job (v3.3).

    Reads the in-memory store first; falls back to the persisted workroom
    record on disk so polling survives process reloads and multi-worker
    deployments. Returns 404 for unknown/expired jobs.
    """
    rec = JOBS.get(job_id)
    if rec is None:
        rec = _workroom_record(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="job not found or expired")
    return rec


def _workroom_record(job_id: str) -> dict | None:
    """Load a persisted workroom file as a job record (disk fallback)."""
    path = resolve_within(WORKROOMS, f"{job_id}.json")
    if path is None:  # unknown id or traversal attempt — treat as missing
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {
        "job_id": job_id,
        "state": data.get("status", "ANALYZED"),
        "created_at": path.stat().st_mtime,
        "finished_at": path.stat().st_mtime,
        "result": data,
    }


@app.get("/api/jobs")
async def jobs_list():
    """v3.6 — lightweight index of live workrooms on disk (newest first)."""
    items = []
    for f in sorted(WORKROOMS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            items.append(
                {
                    "job_id": data.get("job_id", f.stem),
                    "filename": data.get("filename"),
                    "format": data.get("detected_format"),
                    "status": data.get("status"),
                    "size_bytes": data.get("size_bytes"),
                    "mtime": f.stat().st_mtime,
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return {"count": len(items), "jobs": items}


@app.get("/api/download/{name}")
async def download(name: str):
    p = resolve_within(OUTPUTS, sanitize_filename(name))
    if p is None:
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(p, filename=p.name)


# --- v4.3: real PWA surface (manifest + generated icons + service worker) ---
_MANIFEST = {
    "name": "Universal Document OS",
    "short_name": "UDO",
    "description": "Local-first document processing: extract text from PDF, DOCX, XLSX, PPTX, ODT and text formats.",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#0b1020",
    "theme_color": "#0f172a",
    "lang": "fa",
    "dir": "rtl",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
}

_SW_JS = b'''// Universal Document OS service worker
const CACHE = "udo-v1";
const ASSETS = ["/", "/app", "/static/site.css", "/static/vscode.css", "/manifest.webmanifest"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;          // never touch non-GET
  const path = new URL(e.request.url).pathname;
  if (path.startsWith("/api/")) return;            // API data stays fresh
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request))         // offline fallback
  );
});
'''


@app.get("/manifest.webmanifest")
async def webmanifest():
    return JSONResponse(_MANIFEST, media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return Response(_SW_JS, media_type="application/javascript")


@app.get("/icon-{size}.png")
async def icon(size: int):
    """Real PNG icons generated with Pillow (no 404 placeholders)."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    if size not in (192, 512):
        raise HTTPException(status_code=404, detail="not found")
    img = Image.new("RGB", (size, size), (11, 16, 32))
    draw = ImageDraw.Draw(img)
    m = size // 5
    draw.rounded_rectangle([m, m // 2, size - m, size - m // 2], radius=size // 16, fill=(35, 56, 110))
    for i, w in enumerate((int(size * 0.42), int(size * 0.34), int(size * 0.26))):
        y = int(size * (0.40 + i * 0.14))
        h = max(4, size // 90)
        draw.rounded_rectangle([int(size * 0.33), y, int(size * 0.33) + w, y + h], radius=h // 2, fill=(159, 182, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/api/status")
async def status():
    """Workspace counters + runtime facts. Safe when directories are absent."""

    def _count(d) -> int:
        try:
            return sum(1 for _ in d.iterdir())
        except OSError:
            return 0

    from app.auth import auth_enabled
    from app.ratelimit import _limit

    return {
        "uploads": _count(UPLOADS),
        "outputs": _count(OUTPUTS),
        "workrooms": _count(WORKROOMS),
        "uptime_seconds": round(time.time() - _START_TS, 1),
        "features": {
            "auth": auth_enabled(),
            "rate_limit_per_min": _limit(),
            "max_upload_bytes": MAX_UPLOAD_BYTES,
        },
    }
