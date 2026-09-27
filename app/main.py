"""Universal Document OS — FastAPI application entry point."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import (
    APP_NAME,
    APP_VERSION,
    AUDIT_FILE,
    BASE,
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

ensure_dirs()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """v3.6 — graceful startup/shutdown hooks."""
    from app.lifecycle import configure_json_logging, graceful_shutdown

    configure_json_logging()
    logger.info("Universal Document OS %s started", APP_VERSION)
    yield
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
from app.metrics import metrics_response, request_counter  # noqa: E402

app.middleware("http")(api_key_guard)


@app.middleware("http")
async def count_requests(request: Request, call_next):
    request_counter.labels(request.method).inc()
    return await call_next(request)


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
    from app.adapters import SUPPORTED_FORMATS, UnsupportedFormat
    from app.adapters import extract as adapter_extract

    fmt = detect(path)
    try:
        return adapter_extract(path, fmt=fmt)
    except UnsupportedFormat as uf:
        return f"[UNSUPPORTED_FORMAT] {uf}"
    except Exception as e:
        return f"[EXTRACTION_ERROR] {e} (supported: {','.join(SUPPORTED_FORMATS)})"


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
    # Extraction is CPU-bound — run it off the event loop so uploads stay snappy.
    text = await asyncio.to_thread(extract_text, src)
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
    }
    (WORKROOMS / f"{job}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    audit("ANALYZE", job_id=job, filename=safe, format=fmt, operation=operation, size=size)

    # For text-like formats, produce a real downloadable output.
    if operation in {"copy", "export_text"} and text and target_format in {"txt", "md"}:
        outp = OUTPUTS / f"{job}.{target_format}"
        outp.write_text(text, encoding="utf-8")
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


@app.get("/api/status")
async def status():
    return {
        "uploads": sum(1 for _ in UPLOADS.iterdir()),
        "outputs": sum(1 for _ in OUTPUTS.iterdir()),
        "workrooms": sum(1 for _ in WORKROOMS.iterdir()),
    }
