# API Reference — Universal Document OS

**Applies to:** v3.2.5 · **Base URL:** `http://localhost:8000`
**Interactive documentation (Swagger UI):** [`/api/docs`](http://localhost:8000/api/docs) · OpenAPI schema: `/api/openapi.json`

This document describes every HTTP endpoint the service actually exposes today, with runnable examples and exact response shapes taken from the source (`app/main.py`). Anything marked *planned* is not implemented yet — we do not document endpoints that don't exist.

---

## Table of contents

- [Authentication](#authentication)
- [Common conventions](#common-conventions)
- [Pages](#pages)
- [`POST /api/process` — upload, extract, export](#post-apiprocess--upload-extract-export)
- [`GET /api/health` — liveness](#get-apihealth--liveness)
- [`GET /api/status` — workload counters](#get-apistatus--workload-counters)
- [`GET /api/download/{name}` — fetch an exported file](#get-apidownloadname--fetch-an-exported-file)
- [Error model](#error-model)
- [Limits & security behavior](#limits--security-behavior)
- [Optional services (code present, not exposed as endpoints yet)](#optional-services-code-present-not-exposed-as-endpoints-yet)

---

## Authentication

There is **no authentication layer** in this version. The service trusts whoever can reach the port — run it on localhost or behind your own reverse proxy / VPN. Public exposure before auth ships is explicitly discouraged (see [SECURITY.md](../SECURITY.md)).

---

## Common conventions

- All responses are JSON unless stated otherwise; UTF-8, Persian-safe (`ensure_ascii=False`).
- A **job id** is a 32-character hex string (`uuid4().hex`) generated per upload and used to name the workroom record and any exported output.
- Timestamps in the audit log are Unix epoch seconds (float).
- File uploads are `multipart/form-data`; everything else uses query/path parameters only.

---

## Pages

| Method | Path | Response | Description |
|---|---|---|---|
| `GET` | `/` | `text/html` | Landing page — what the app is and a link into the panel. |
| `GET` | `/app` | `text/html` | Upload panel — pick a file, choose an operation, see the result inline. Works fully client-side against the API below. |

```bash
curl -s http://localhost:8000/       # landing HTML
curl -s http://localhost:8000/app    # panel HTML
```

---

## `POST /api/process` — upload, extract, export

The core endpoint. It stores the file, detects its format, extracts text through the adapter registry, writes a workroom record + audit line, and optionally produces a downloadable export.

### Form fields

| Field | Type | Required | Default | Values / meaning |
|---|---|---|---|---|
| `file` | file | ✅ | — | The document. Max size `MAX_UPLOAD_BYTES` (default 25 MB). The filename is sanitized server-side; never rely on the stored name matching what you sent byte-for-byte. |
| `operation` | string | ❌ | `analyze` | `analyze` — extract + record only.<br>`export_text` or `copy` — additionally write a downloadable output when `target_format` is `txt`/`md`. |
| `target_format` | string | ❌ | `same` | `same` — no export file.<br>`txt` / `md` — write `data/outputs/{job_id}.txt|.md`. Other values are recorded but produce no file. |

### Example — analyze only

```bash
curl -X POST http://localhost:8000/api/process \
     -F "file=@sample.pdf" \
     -F "operation=analyze"
```

```json
{
  "job_id": "3b7e4787b12f4fb5bbef46325fb71c6a",
  "filename": "sample.pdf",
  "detected_format": "PDF",
  "operation": "analyze",
  "target_format": "same",
  "size_bytes": 48213,
  "characters": 1234,
  "status": "ANALYZED",
  "preview": "First up-to-5000 characters of extracted text…"
}
```

### Example — extract and export as Markdown

```bash
curl -X POST http://localhost:8000/api/process \
     -F "file=@notes.docx" \
     -F "operation=export_text" \
     -F "target_format=md"
```

Same shape as above, plus `"download": "/api/download/<job_id>.md"` and `"status": "READY"`.

### Response fields

| Field | Meaning |
|---|---|
| `job_id` | Unique id of this processing job (= workroom file name). |
| `filename` | Sanitized basename of the upload. |
| `detected_format` | Uppercase format key (`PDF`, `DOCX`, `XLSX`, `PPTX`, `ODT`, `TXT`, `MARKDOWN`, `CSV`, `JSON`, `HTML`, `RTF`, legacy names like `DOC`, or a MIME guess / `UNKNOWN`). |
| `operation`, `target_format` | Echo of the requested options. |
| `size_bytes` | Bytes actually received. |
| `characters` | Length of the extracted text. |
| `status` | `ANALYZED` (recorded) or `READY` (an export file exists). |
| `preview` | First `PREVIEW_CHARS` (default 5000) characters of extracted text. |
| `download` | Present only for successful exports; feed it to [`/api/download`](#get-apidownloadname--fetch-an-exported-file). |

### What extraction failures look like

The pipeline **never returns 5xx for a bad document**. Problems surface inside `preview`/extraction text as tagged strings:

- `[UNSUPPORTED_FORMAT] Unsupported format DOC: … convert to DOCX` — detected but no adapter (legacy Office formats).
- `[EXTRACTION_ERROR] …(supported: CSV,DOCX,…)` — the adapter raised (corrupt file, missing optional library).

`characters` still reflects what came back, and the workroom record is always written, so nothing is silently lost.

---

## `GET /api/health` — liveness

```bash
curl -s http://localhost:8000/api/health
```

```json
{"status": "ok", "service": "Universal Document OS", "version": "3.2.4"}
```

The `version` field is guaranteed to equal `APP_VERSION` in `app/config.py` and the FastAPI app version (a regression test enforces this three-way consistency). Used by Docker `HEALTHCHECK`, `status.sh`, `install.sh`, and CI smoke checks.

---

## `GET /api/status` — workload counters

```bash
curl -s http://localhost:8000/api/status
```

```json
{"uploads": 12, "outputs": 4, "workrooms": 12}
```

Counts of files currently in `data/uploads/`, `data/outputs/`, and `data/workrooms/`. Useful for capacity spot-checks and for tests to confirm isolation.

---

## `GET /api/download/{name}` — fetch an exported file

Returns one file from `data/outputs/` as an attachment.

```bash
curl -O -J http://localhost:8000/api/download/3b7e4787b12f4fb5bbef46325fb71c6a.md
```

Security behavior (implemented in `app/security.resolve_within`):

- `{name}` is sanitized first (directory parts, `..`, leading dots/dashes removed).
- The final path is resolved **after symlink expansion** and must remain strictly inside `data/outputs/`.
- Anything else — traversal attempts, symlinks pointing outside, missing files, subdirectories — returns plain `404 Not Found`. There is no way to probe which of those it was.

---

## Error model

| Situation | HTTP | Body |
|---|---|---|
| Missing `file` field | `422` | FastAPI validation detail |
| Upload exceeds `MAX_UPLOAD_BYTES` | `413` | `{"detail": "file too large (limit 26214400 bytes)"}` — partial file is deleted automatically |
| Download name escapes outputs dir / not found | `404` | `{"detail": "not found"}` |
| Unprocessable document | `200` | Tagged string inside the result (`[UNSUPPORTED_FORMAT]`, `[EXTRACTION_ERROR]`) |

---

## Limits & security behavior (summary)

| Concern | Behavior | Where |
|---|---|---|
| Upload size | Streamed in 1 MB chunks; hard stop at `MAX_UPLOAD_BYTES` → `413` | `app/main.py` |
| Filename injection | `sanitize_filename()` — basename only, `..` collapsed, hidden names blocked, ≤180 chars, Persian preserved | `app/security.py` |
| Path traversal on download | Full resolve + containment check incl. symlinks | `app/security.py` |
| Data location | Everything under `DATA_DIR` (default `./data`), git-ignored | `app/config.py` |
| Auditability | Append-only `data/audit.jsonl`; audit failure can never break a request | `app/main.py` |

---

## Optional services (code present, not exposed as endpoints yet)

These modules are importable and tested-ish but have **no HTTP surface** in v3.2.5. We list them so integrators aren't misled:

- **OCR engines** — `app/ocr/tesseract_engine.py` provides real Tesseract (`pytesseract`) and RapidOCR extraction functions returning `{text, confidence, engine, skipped?}`, configured via `TESSERACT_CMD` and `OCR_LANGS` (default `eng+fas`). Wiring into `/api/process` is next on the roadmap.
- **Translation** — `app/translation/service.py` ships a provider interface with a mock provider (`TRANSLATION_ENABLED`, `TRANSLATION_API_KEY`). Mock output is clearly flagged `"mock": true`.
- **SMS** — `app/services/sms/` implements real Ghasedak and Kavenegar adapters (`SMS_PROVIDER`, `SMS_API_KEY`, `SMS_SENDER`; ~120 Toman/SMS; balance check via `test_connection()`), with a `mock` fallback when unconfigured.
- **Notifications** — `app/services/notification/service.py` supports `in_app` (persisted to a JSON inbox, capped at 50 entries/user) and `telegram` (real Bot API call when `NOTIF_TELEGRAM=true` + token/chat id set). Email/SMS channels are stubbed results, not real sends.

If you build against these, import them directly until the REST layer lands.

---

*Docs match source as of commit for v3.2.5. When you change `app/main.py`, update this file in the same PR — it's part of the [contribution checklist](../CONTRIBUTING.md).*
