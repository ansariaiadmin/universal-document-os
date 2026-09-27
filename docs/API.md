# API Reference — Universal Document OS

**Applies to:** v4.2.0 · **Base URL:** `http://localhost:8000`
**Interactive documentation (Swagger UI):** [`/api/docs`](http://localhost:8000/api/docs) · OpenAPI schema: `/api/openapi.json`

This document describes every HTTP endpoint the service actually exposes, with runnable examples and response shapes taken from the source (`app/main.py`). Anything marked *planned* is not implemented yet — we do not document endpoints that don't exist.

---

## Table of contents

- [Authentication](#authentication)
- [Pages & PWA](#pages--pwa)
- [`POST /api/process` — upload, guard, extract, export](#post-apiprocess--upload-guard-extract-export)
- [`GET /api/dashboard` — smart dashboard feed](#get-apidashboard--smart-dashboard-feed)
- [`GET /api/health` — liveness](#get-apihealth--liveness)
- [`GET /api/status` — runtime facts](#get-apistatus--runtime-facts)
- [`GET /api/job/{id}` · `GET /api/jobs`](#get-apijobid--get-apijobs)
- [`GET /api/download/{name}` — fetch an exported file](#get-apidownloadname--fetch-an-exported-file)
- [`GET /metrics` — Prometheus](#get-metrics--prometheus)
- [Error model](#error-model)
- [Optional services (code present, not exposed as endpoints yet)](#optional-services)

---

## Authentication

Optional and opt-in. If the env var `UDO_API_KEYS` is set (comma-separated), every `/api/*` request except `/api/health`, `/api/docs` and `/api/openapi.json` must carry `X-API-Key: <key>`. Comparison is timing-safe (`hmac.compare_digest`). Unset → auth is off (dev mode).

`RATE_LIMIT_PER_MIN=<n>` enables a sliding-window limit (per client per minute) on `/api/process`, `/api/download`, `/api/job*`, `/api/status`; exceeding it returns `429` with `Retry-After`.

The panel asks for the key once on `401` and keeps it in `sessionStorage`.

---

## Pages & PWA

| Method | Path | Response | Description |
|---|---|---|---|
| `GET` | `/` | `text/html` | Landing page. |
| `GET` | `/app` | `text/html` | Upload panel **+ Smart Dashboard tab** (live facts from `/api/dashboard`). |
| `GET` | `/manifest.webmanifest` | `application/manifest+json` | PWA manifest (real, served). |
| `GET` | `/sw.js` | `application/javascript` | Service worker (network-first, offline fallback, API never cached). |
| `GET` | `/icon-192.png`, `/icon-512.png` | `image/png` | Generated icons (real PNG bytes; other sizes → 404). |

---

## `POST /api/process` — upload, guard, extract, export

The core endpoint. It stores the file, **verifies its content against the claimed type**, extracts text (through adapters or real OCR for images), derives intelligence, records everything, and optionally produces a downloadable export.

### Form fields

| Field | Type | Required | Default | Values / meaning |
|---|---|---|---|---|
| `file` | file | ✅ | — | Max `MAX_UPLOAD_BYTES` (default 25 MB). Filename is sanitized server-side. |
| `operation` | string | ❌ | `analyze` | `analyze` — extract + record.<br>`export_text` / `copy` / `convert` — additionally write a downloadable output when `target_format` is `txt`/`md`/`html`. |
| `target_format` | string | ❌ | `same` | `same` — no export file.<br>`txt` / `md` — write `data/outputs/{job_id}.txt\|.md` from any source.<br>`html` — real markdown rendering (tables, fenced code) for MD/TXT/HTML sources; other source formats get a clean `400`. |

### Example

```bash
curl -X POST http://localhost:8000/api/process \
     -F "file=@notes.docx" \
     -F "operation=export_text" \
     -F "target_format=md"
```

```json
{
  "job_id": "3b7e4787b12f4fb5bbef46325fb71c6a",
  "filename": "notes.docx",
  "detected_format": "DOCX",
  "operation": "export_text",
  "target_format": "md",
  "size_bytes": 48213,
  "characters": 1234,
  "status": "READY",
  "preview": "First up-to-5000 characters of extracted text…",
  "download": "/api/download/3b7e4787b12f4fb5bbef46325fb71c6a.md",
  "intelligence": {
    "language": "en",
    "language_confidence": 0.81,
    "detection_method": "stopwords",
    "direction": "ltr",
    "category": "report",
    "word_count": 210,
    "line_count": 18
  }
}
```

### `intelligence` field

Script-aware language detection (`fa`, `ar`, `he`, `zh`, `ru`, plus Latin stopword scoring for `en`/`de`/`fr`/`es`; `und` when there is not enough signal), text direction, coarse document category (`invoice`/`contract`/`resume`/`report`/`manual`/`letter`/`general`) and basic counts. Pure stdlib, deterministic.

### What failures look like

The pipeline **never returns 5xx for a bad document**:

- `415` — content guard: executable magic bytes as `.pdf`, shebang scripts, binary payloads claiming to be text, zip-bomb archives.
- `413` — upload above `MAX_UPLOAD_BYTES` (partial file deleted).
- `400` — conversion pair unsupported (e.g. `docx → html`).
- `501` — conversion dependency missing.
- `200` with tagged string in `preview` — `[UNSUPPORTED_FORMAT] …` (e.g. legacy XLS/PPT, or images when no OCR engine is installed), `[EXTRACTION_ERROR] …` (corrupt file).

The workroom record is always written; nothing is silently lost.

---

## `GET /api/dashboard` — smart dashboard feed

Live, measured facts — the same data the panel's Smart Dashboard tab renders. Nothing here is hard-coded.

```bash
curl -s http://localhost:8000/api/dashboard
```

```json
{
  "version": "4.2.0",
  "uptime_seconds": 634.2,
  "pipeline": {
    "formats_extractable": ["CSV", "DOCX", "HTML", "JSON", "MARKDOWN", "ODT", "ODS", "ODP", "PDF", "PPTX", "RTF", "TXT"],
    "max_upload_bytes": 26214400,
    "preview_chars": 5000
  },
  "capabilities": {
    "ocr_engines": {"tesseract": true, "rapidocr": false},
    "ocr_ready": true,
    "ocr_langs": "eng+fas",
    "conversions": [{"from": "pdf", "to": "txt", "supported": true}],
    "intelligence_categories": ["invoice", "contract", "letter", "manual", "report", "resume"],
    "translation_wired": false
  },
  "security": {"auth_enabled": false, "rate_limit_per_min": 0, "max_upload_bytes": 26214400},
  "jobs": {"store": "sqlite", "total": 12, "READY": 4, "ANALYZED": 8},
  "storage": {"uploads": 12, "outputs": 4, "workrooms": 12, "uploads_bytes": 482113, "outputs_bytes": 9021, "audit_lines": 12}
}
```

`ocr_engines` values are **real probes** (Python deps + tesseract binary availability), not guesses.

---

## `GET /api/health` — liveness

```json
{"status": "ok", "service": "Universal Document OS", "version": "4.2.0"}
```

The `version` field equals `APP_VERSION` in `app/config.py` and the FastAPI app version (a regression test enforces the three-way consistency). Used by the Docker `HEALTHCHECK`, `status.sh`, `install.sh`.

---

## `GET /api/status` — runtime facts

```json
{"uploads": 12, "outputs": 4, "workrooms": 12, "uptime_seconds": 634.2,
 "features": {"auth": false, "rate_limit_per_min": 0, "max_upload_bytes": 26214400}}
```

---

## `GET /api/job/{id}` · `GET /api/jobs`

- `/api/job/{id}` — poll one job. Reads the durable SQLite store first; falls back to the persisted workroom file (so polling survives reloads). Unknown/expired → `404`.
- `/api/jobs` — newest-first index from the workroom files, capped at 50:

```json
{"count": 2, "jobs": [{"job_id": "…", "filename": "a.md", "format": "MARKDOWN", "status": "ANALYZED", "size_bytes": 42, "mtime": 1750000000.0}]}
```

Finished jobs are swept after `JOB_TTL_SECONDS` (default 3600) by a background task every 5 minutes.

---

## `GET /api/download/{name}` — fetch an exported file

```bash
curl -O -J http://localhost:8000/api/download/3b7e4787b12f4fb5bbef46325fb71c6a.md
```

Security behavior (`app/security.resolve_within`): the name is sanitized, the path is resolved **after symlink expansion** and must stay strictly inside `data/outputs/`; anything else returns a uniform `404`.

---

## `GET /metrics` — Prometheus

Prometheus exposition via `prometheus_client` when installed, otherwise a dependency-free counter rendering valid exposition format — the endpoint never 500s. Counter: `udo_http_requests_total{method}`.

---

## Error model

| Situation | HTTP | Body |
|---|---|---|
| Missing `file` field | `422` | FastAPI validation detail |
| Upload exceeds `MAX_UPLOAD_BYTES` | `413` | `{"detail": "file too large (limit 26214400 bytes)"}` |
| Content-guard rejection (spoofed/binary/bomb) | `415` | `{"detail": "content rejected: …"}` |
| Unsupported conversion pair | `400` | `{"detail": "conversion x->y not supported (targets: txt, md, html)"}` |
| Conversion dependency missing | `501` | `{"detail": "markdown library not installed"}` |
| Missing/invalid API key (when auth on) | `401` | `{"detail": "missing or invalid X-API-Key header"}` |
| Rate limit exceeded (when enabled) | `429` | `{"detail": "rate limit exceeded (n/min)"}` + `Retry-After` |
| Download name escapes outputs dir / not found | `404` | `{"detail": "not found"}` |
| Unprocessable document | `200` | Tagged string inside the result |

---

## Optional services

These modules are importable and tested but have **no HTTP surface** yet:

- **Translation** — `app/translation/service.py`, mock provider flagged `"mock": true`. The old fabricated "benchmark scores" were removed; a real benchmark requires a ground-truth dataset (ROADMAP).
- **SMS** — `app/services/sms/`, real Ghasedak/Kavenegar adapters (HTTP, timeouts, structured results) with a mock fallback when unconfigured.
- **Notifications** — `app/services/notification/service.py`, in-app inbox persisted to JSON (capped at 50/user) and a real Telegram send when configured. Email/SMS channels are stubs.

---

*Docs match source as of v4.2.0. When you change `app/main.py`, update this file in the same PR — it's part of the [contribution checklist](../CONTRIBUTING.md).*
