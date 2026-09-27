# AGENTS — Contributor & AI-Agent Handoff

**Purpose:** everything a developer *or* an autonomous coding agent needs to work in this repo safely and productively, in one page.
**Read first:** [README.md](README.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → this file.

---

## 1. The system in one paragraph

A FastAPI service (`app/main.py`) accepts multipart uploads at `POST /api/process`, sanitizes the filename and streams the bytes under `data/uploads/` (hard size cap), detects the format by extension, extracts text through a decorator-based **adapter registry** (`app/adapters/__init__.py`), persists a JSON *workroom* record plus one append-only audit line, optionally writes a `.txt/.md` export served by a traversal-safe download route, and answers health/status probes. All paths, limits, and the version come from `app/config.py`; all path-safety logic lives in `app/security.py`.

## 2. Module map (what to touch for what)

| You want to… | Open | Contract you must preserve |
|---|---|---|
| Add/change an endpoint | `app/main.py` | Never let extraction errors raise 5xx; always write workroom + audit; responses stay JSON with existing field names |
| Support a new document format | `app/adapters/__init__.py` | Register via `@register("FMT")`; missing optional libs → raise `UnsupportedFormat` with install hint; corrupt input → raise `RuntimeError` (caught upstream as `[EXTRACTION_ERROR]`) |
| Change limits/paths/version | `app/config.py` | Env-driven with defaults; do not duplicate constants elsewhere — tests monkey-patch these attributes |
| Touch anything path-related | `app/security.py` | `sanitize_filename` and `resolve_within` are the only sanctioned ways to build filesystem paths from user input; keep them total functions (never raise on bad input) |
| Work on OCR | `app/ocr/tesseract_engine.py` (real) · `app/ocr/multi_engine.py` (scaffold) | Engines return `{text, confidence, engine, skipped?}`; missing deps ⇒ `skipped=True`, never fabricate text |
| Work on translation | `app/translation/service.py` | Provider interface `translate(text, source, target)`; mock results must carry `"mock": true` |
| SMS providers | `app/services/sms/` | Adapters return dicts with `success`; failures log + fall back to mock; no exceptions escape `SmsService.send` |
| Notifications | `app/services/notification/service.py` | in-app inbox is persisted JSON capped at `MAX_INBOX=50` per user; use `setdefault` (regression guard); external sends have timeouts |
| Landing/panel UI | `app/templates/*.html`, `app/static/` | Panel calls only documented endpoints (see [docs/API.md](docs/API.md)) |
| Runtime scripts | `install.sh`, `status.sh`, `update.sh`, … | Port is **8000**; health URL is `http://localhost:8000/api/health`; keep `.sh`/`.bat` pairs behaviorally identical |
| Tests | `tests/` | Use fixtures from `conftest.py`; never write to repo `data/` |

## 3. Invariants (CI enforces most of these)

1. `APP_VERSION` in `app/config.py` == FastAPI app version == `/api/health.version` (test_security asserts).
2. Docs URLs/port = 8000 everywhere; no Node.js/`localhost:3000` references remain.
3. No secrets committed; `.env` git-ignored; `.env.example` placeholders only.
4. `ruff check app/` clean (rule set F, line-length 120).
5. `pytest -q` → 29 passed, order-independent, temp-dir isolated.
6. Docker image builds and its HEALTHCHECK passes against `/api/health`.
7. Every user-supplied string used in a path goes through `sanitize_filename`/`resolve_within`.

## 4. Dev loop

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # dev server
pytest -q                                    # full suite (isolated)
ruff check app/                              # lint gate
```

Manual probe:

```bash
echo "hello" > /tmp/note.txt
curl -X POST http://localhost:8000/api/process -F "file=@/tmp/note.txt" -F "operation=export_text" -F "target_format=txt"
```

## 5. How to extend — worked example (new format: EPUB)

```python
# app/adapters/__init__.py
@register("EPUB")
def extract_epub(path: pathlib.Path) -> str:
    try:
        from ebooklib import epub          # add to requirements.txt as optional
    except ImportError as e:
        raise UnsupportedFormat("EPUB", f"ebooklib missing: {e}. pip install ebooklib")
    book = epub.read_epub(str(path))
    return "\n".join(item.get_content().decode("utf-8", "replace")
                     for item in book.get_items_of_type(9))  # ITEM_DOCUMENT
```

Then: add `.epub → EPUB` to `detect()` mapping in `app/main.py`, add one test that a fake `.epub` produces either text or `[UNSUPPORTED_FORMAT]`, update the formats table in README + docs/API. PR checklist in [CONTRIBUTING.md](CONTRIBUTING.md).

## 6. Rules for AI agents

- **Verify before claiming.** Run `pytest`/`ruff`/`curl` and paste real output; never report hypothetical results.
- **Minimal diffs.** No drive-by reformatting; match existing style.
- **Never commit runtime state**: `data/`, `backups/`, `.env`, `__pycache__` stay out of git.
- **Don't invent endpoints** in docs/code — mirror `app/main.py` exactly; unimplemented features belong in ROADMAP as planned.
- **Update docs in the same change** when routes, env vars, versions, or ports change (this repo's docs are contract-grade).
- When bumping a release: edit `app/config.py` once, then CHANGELOG + README badges; a consistency test catches drift.

## 7. Known landmines

- Import cycles: adapters lazily imports `main.detect` inside a function — keep it lazy.
- `UploadFile` must be read in chunks (memory); don't switch to `await file.read()` without size guard.
- Jinja templates dir is resolved relative to repo root (`BASE`) — moving files breaks both prod and tests.
- `notification_service` loads its inbox at import time — in tests, patch `NOTIF_INBOX_FILE` env before import (see conftest pattern).
- Windows `.bat` scripts assume Git Bash tooling for some checks; keep parity notes in PR descriptions.

---

*Maintained alongside the code. If this file contradicts the source, the source wins — fix the doc in your PR.*
