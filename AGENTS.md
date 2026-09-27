# AGENTS — Contributor & AI-Agent Handoff

**Purpose:** everything a developer *or* an autonomous coding agent needs to work in this repo safely and productively, in one page.
**Read first:** [README.md](README.md) → [ARCHITECTURE.md](ARCHITECTURE.md) → this file.

---

## 1. The system in one paragraph

A FastAPI service (`app/main.py`) accepts multipart uploads at `POST /api/process`, streams the bytes under `data/uploads/` (hard size cap), runs an adaptive content guard (magic bytes, zip-bomb budget, extension/content cross-check), detects the format by extension with a MIME fallback, extracts text through a decorator-based **adapter registry** (`app/adapters/__init__.py`, including real OCR for images), derives intelligence (language/direction/category), persists a JSON *workroom* record + a SQLite job row + one append-only audit line, optionally writes a `.txt/.md/.html` export served by a traversal-safe download route, and answers health/status/dashboard/metrics probes. A **smart dashboard** (`GET /api/dashboard` + a panel tab) renders live measured facts. All paths, limits, and the version come from `app/config.py`; path-safety lives in `app/security.py`; opt-in auth/rate-limit live in `app/auth.py` / `app/ratelimit.py`.

## 2. Module map (what to touch for what)

| You want to… | Open | Contract you must preserve |
|---|---|---|
| Add/change an endpoint | `app/main.py` | Never let extraction errors raise 5xx; always write workroom + audit; responses stay JSON with existing field names |
| Support a new document format | `app/adapters/__init__.py` | Register via `@register("FMT")`; missing optional libs → raise `UnsupportedFormat` with install hint; corrupt input → raise `RuntimeError` (caught upstream as `[EXTRACTION_ERROR]`); bound output by `MAX_TEXT_CHARS` |
| Change limits/paths/version | `app/config.py` | Env-driven with defaults; do not duplicate constants elsewhere — tests monkey-patch these attributes |
| Touch anything path-related | `app/security.py` | `sanitize_filename` and `resolve_within` are the only sanctioned ways to build filesystem paths from user input; keep them total functions |
| Work on OCR | `app/ocr/tesseract_engine.py`, `app/ocr/multi_engine.py` | Engines return `{text, confidence, engine, skipped?}`; availability via `engine_available()` (real probes); missing deps ⇒ `skipped=True`, never fabricate text |
| Change the smart dashboard | `app/main.py::dashboard` + panel tab in `app/templates/panel_vscode.html` | Every value must be **measured at request time** — no hard-coded facts |
| Work on translation | `app/translation/service.py` | Provider interface `translate(text, source, target)`; mock results carry `"mock": true`; the benchmark must refuse to report metrics without a ground-truth dataset (no invented numbers) |
| SMS providers | `app/services/sms/` | Adapters return dicts with `success`; failures log + fall back to mock; no exceptions escape `SmsService.send` |
| Notifications | `app/services/notification/service.py` | In-app inbox persisted JSON capped at `MAX_INBOX=50`; use `setdefault` (regression guard); external sends have timeouts |
| Landing/panel UI | `app/templates/*.html`, `app/static/` | Panel calls only documented endpoints (see [docs/API.md](docs/API.md)) |
| Runtime scripts | `install.sh`, `status.sh`, `update.sh`, … | Port 8000; health URL `http://localhost:8000/api/health`; keep `.sh`/`.bat` pairs behaviorally identical; **no env vars outside the set actually read by `app/`** |
| Tests | `tests/` | Use fixtures from `conftest.py`; never write to repo `data/` |

## 3. Invariants (CI enforces most of these)

1. `APP_VERSION` in `app/config.py` == FastAPI app version == `/api/health.version` (test asserts); docker-compose must not override it.
2. Docs URLs/port = 8000 everywhere; no Node.js/npm references.
3. No secrets committed; `.env` git-ignored; `.env.example` placeholders only; **`.env.example` only documents variables that are actually read by `app/` code**.
4. `ruff check .` clean (rule set F, line-length 120; tool version pinned in requirements.txt).
5. `pytest -q` green, order-independent, temp-dir isolated (89 tests as of v4.2.0-follow-up).
6. Docker image builds, its HEALTHCHECK passes, and the image includes tesseract + `fas`/`eng` traineddata.
7. Every user-supplied string used in a path goes through `sanitize_filename`/`resolve_within`.
8. `data/`, `backups/`, `runtime/` are fully git-ignored and excluded from the Docker build context (`.dockerignore`).
9. No fabricated outputs anywhere: OCR without engines ⇒ honest error; benchmark without dataset ⇒ refuses; dashboard without measurement ⇒ forbidden.

## 4. Dev loop

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # dev server
pytest -q                                    # full suite (isolated)
ruff check .                                 # lint gate
```

Manual probe:

```bash
echo "hello" > /tmp/note.txt
curl -X POST http://localhost:8000/api/process -F "file=@/tmp/note.txt" -F "operation=export_text" -F "target_format=txt"
curl -s http://localhost:8000/api/dashboard | python3 -m json.tool
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
    _guard_size(path)
    book = epub.read_epub(str(path))
    return _cap("\n".join(item.get_content().decode("utf-8", "replace")
                     for item in book.get_items_of_type(9)))  # ITEM_DOCUMENT
```

Then: add `.epub → EPUB` to `_EXT_FORMATS` in `app/adapters/__init__.py`, add one test, update the formats table in README + docs/API, and the dashboard's `formats_detected` list.

## 6. Rules for AI agents

- **Verify before claiming.** Run `pytest`/`ruff`/`curl` and paste real output; never report hypothetical results.
- **Minimal diffs.** No drive-by reformatting; match existing style.
- **Never commit runtime state**: `data/`, `backups/`, `runtime/`, `.env`, `__pycache__` stay out of git.
- **Don't invent endpoints** in docs/code — mirror `app/main.py` exactly; unimplemented features belong in ROADMAP as planned.
- **Update docs in the same change** when routes, env vars, versions, or ports change (docs are contract-grade).
- When bumping a release: edit `app/config.py` once, then CHANGELOG + README badges; a consistency test catches drift.

## 7. Known landmines

- `notification_service` loads its inbox at import time — in tests, patch `NOTIF_INBOX_FILE` env before import (see conftest pattern).
- Some tests re-import `app.config`/`app.main` to isolate `DATA_DIR`; don't add import-time singletons that can't survive that.
- The OCR engines are optional at runtime: never import `pytesseract`/PIL at module import time in the request path — use the lazy imports in `tesseract_engine.py`.
- Jinja templates dir is resolved relative to repo root (`BASE`) — moving files breaks both prod and tests.
- Windows `.bat` scripts assume Git Bash tooling for some checks; keep parity notes in PR descriptions.

---

*Maintained alongside the code. If this file contradicts the source, the source wins — fix the doc in your PR.*
