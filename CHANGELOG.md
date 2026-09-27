# Changelog

All notable changes to Universal Document OS are documented here.
Versions follow SemVer; the single source of truth for the running version is `app/config.py` (`APP_VERSION`).

## [v4.0.0] - 2026-09-27 � Enterprise Milestone: Jobs, Auth, Metrics, Legacy Formats, Lifecycle

### Job Orchestration (v3.3)
- New `app/jobs.py`: thread-safe in-memory `JobStore` with TTL expiry and state stats.
- `POST /api/process` registers every job; new endpoints `GET /api/job/{id}` (polling, with a disk-backed workroom fallback so polling survives process reloads and multi-worker deployments) and `GET /api/jobs` (newest-first index, capped at 50).

### API Authentication (v3.5)
- New `app/auth.py`: opt-in `X-API-Key` middleware. Set `UDO_API_KEYS=key1,key2` to protect all `/api/*` routes except health/docs probes; unset keeps dev mode open. Constant-shape comparison over configured keys.
- The VS Code panel now prompts once on `401`, stores the key in `sessionStorage`, and replays it automatically.

### Observability (v3.5)
- New `app/metrics.py`: Prometheus exposition at `GET /metrics`. Uses `prometheus_client` when installed, otherwise a dependency-free counter that still renders valid text format � the endpoint never 500s.

### Legacy Office Formats (v3.4)
- New `app/adapters/legacy.py`: real `.doc` text extraction via `antiword` (fixed argv, no shell, 60s timeout). When the binary is missing, users get an actionable error naming the exact install command instead of silent failure.

### Lifecycle & Logging (v3.6)
- New `app/lifecycle.py`: structured JSON log formatter (one object per line � Loki/CloudWatch-ready) and graceful startup/shutdown hooks wired through FastAPI `lifespan`; expired jobs swept on boot.

### Reliability fixes found during integration testing
- `DATA_DIR` now honors absolute paths (previously silently joined under `BASE_DIR`).
- Job polling falls back to persisted workroom records when the in-memory store is cold.
- Unknown/traversal job IDs return a clean 404 instead of crashing.

### Testing
- Suite grew to **49 tests** (new `tests/test_enterprise.py`: job store lifecycle/TTL, API polling, auth allow/deny, metrics format, legacy error messaging, JSON log validity). `ruff check app/ tests/` clean.

## [v3.2.7] - 2026-09-27 — VS Code Panel & Ownership

### UI/UX
- **New control panel** (`app/templates/panel_vscode.html` + `app/static/vscode.css`): full VS Code Dark+ chrome — title bar, activity bar, document explorer sidebar, tabs, line-numbered editor with JSON syntax highlighting, drop-zone upload, live status bar (job state, detected format, workspace counters). `/app` now serves it; legacy `panel.html` kept as fallback.

### Governance
- Author and copyright formally set: **Mohammad Ansari** (https://github.com/ansariaiadmin) in LICENSE and README; MIT terms unchanged — free to use, modify and redistribute with attribution kept intact.
- Version bump `APP_VERSION=3.2.7`; README synced to the single source of truth.

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

## [4.1.1] - 2026-09-27
### Security
- **Content guard bypass closed (found by live audit):** files with executable magic bytes (`MZ`/PE, ELF) renamed to `.pdf`/`.docx` were passing the gate because unknown media types were treated as "no evidence". Executives and shebang scripts are now hard-rejected with HTTP 415 before any extraction runs.
- 3 new regression tests (dosexec-as-pdf, elf-as-docx, script-as-doc); suite: 64/64 green.
