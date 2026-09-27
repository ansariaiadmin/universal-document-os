"""Universal Document OS — FastAPI application entry point."""
from __future__ import annotations

import json
import logging
import time
import uuid

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
from app.security import resolve_within, sanitize_filename

logger = logging.getLogger("udo")

ensure_dirs()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=BASE / "app/static"), name="static")
templates = Jinja2Templates(directory=BASE / "app/templates")


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
    text = extract_text(src)
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
    return JSONResponse(result)


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
