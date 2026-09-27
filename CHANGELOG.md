# Changelog

All notable changes to Universal Document OS are documented here.
Versions follow SemVer; the single source of truth for the running version is `app/config.py` (`APP_VERSION`).

## [v3.2.6] - 2026-09-27 — Real OCR Wiring & Documentation Unification

### Architecture
- **OCR pipeline is now real**: `app/ocr/tesseract_engine.py` wraps the local Tesseract binary (subprocess, no network) and is wired into `multi_engine.py` as the primary engine with graceful fallback when the binary is absent. Mock/fabricated engines removed from the active pipeline.
- New adapter-level format detection fixes; OpenDocument adapters rebuilt as thin, table-driven modules.

### Security
- RCE vector in template rendering closed (see SECURITY.md threat model).

### Documentation
- All 10 core docs (README, ARCHITECTURE, SECURITY, API, INSTALL, CONTRIBUTING, ROADMAP, AGENTS, USER_GUIDE_EN, SETUP-WIZARD-FA) rewritten line-by-line against actual source behavior: port 8000, `/api/health`, correct Swagger path (`/api/docs`), version sourced from `APP_VERSION`, no fabricated claims.

### Testing
- Suite grew to **40 tests** (new `tests/test_ocr_wiring.py` covers engine selection, fallback, and subprocess isolation). `ruff check app/` clean.

## [v3.2.4] - 2026-09-27 — Audit & Hardening (production-readiness)

### Security
- **Path traversal fixed** in `/api/download/{name}`: downloads now resolve through `app/security.resolve_within()` — symlinks and `../` sequences can no longer escape `data/outputs/`.
- **Filename sanitization** for uploads (`app/security.sanitize_filename`): directory components, traversal sequences, and hidden-file names (e.g. `.env`) are stripped; Persian characters preserved.
- **Upload size limit** enforced while streaming (`MAX_UPLOAD_BYTES`, default 25 MB) → clean `413` response instead of unbounded disk write.

### Fixes
- Notification inbox: first in-app message for a *new* user was silently lost (`inbox.get(uid, [])` throwaway list) — now uses `setdefault` and always persists.
- XLSX adapter: `data_only=True` so exported text contains cell values, not raw formulas.
- Removed import-time side-effect `print(...)` banners from `app/ocr/multi_engine.py` and `app/translation/service.py` (now logging).
- Version consistency: `1.0.0` vs `v3.2.3` vs `v0.9.3` mismatch resolved — one `APP_VERSION` in `app/config.py`, used by FastAPI app + `/api/health`.
- `pytest==8.3.4` pin conflicted with CI's `pip install pytest` (latest) — aligned to `8.4.1`.

### Architecture / hygiene
- New `app/config.py`: central, env-driven paths & limits (`DATA_DIR`, `MAX_UPLOAD_BYTES`, `PREVIEW_CHARS`).
- Dead legacy fallback extraction code removed from `main.extract_text` (adapters package is required, non-optional).
- Missing `__init__.py` files added (`app`, `app.lib`, `app.ocr`, `app.services`, `app.services.notification`, `app.translation`) — packages were only working via namespace-package luck.
- API docs served at `/api/docs` (was default `/docs`).

### Repo hygiene
- **Untracked runtime data**: 49 files under `data/` (uploads, outputs, workrooms, audit.jsonl) were committed to git — removed from index, added to `.gitignore`. Local copies kept on disk.
- Tests are now isolated: new `tests/conftest.py` redirects all data paths to a temp dir per test (previously every test run polluted the repo's real `data/`).

### Tests
- 19 → **29 tests** (new `tests/test_security.py`: traversal, sanitization, 413, workroom isolation, version consistency, notification persistence regression).

## [v3.2.3] - earlier
- PWA + logger + persist fixes (see git history).

## [v0.9.x] - initial local-install editions
- Auto install/update scripts, user guides (FA/EN).
