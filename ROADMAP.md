# Roadmap — Universal Document OS

**Last updated:** v3.2.4 · This file states honestly what is shipped, what is scaffolded, and what is planned. No hidden gaps, no vaporware claims.

---

## Status legend

- ✅ **Shipped** — working, tested, reachable through the API/UI today
- 🟡 **Scaffolded** — real code exists in the repo but is not wired into the request path
- ⬜ **Planned** — designed, not started

---

## Shipped (through v3.2.4)

### Core pipeline (v0.9 → v3.2.3)
- ✅ Adapter registry with PDF / DOCX / XLSX / PPTX / ODT / TXT / MD / CSV / JSON / HTML / RTF extraction
- ✅ Landing + upload panel (Jinja2), streaming multipart processing, workroom records, append-only audit log
- ✅ Export to `.txt`/`.md` + traversal-safe download endpoint
- ✅ Docker: multi-stage, non-root, healthcheck; docker-compose single service
- ✅ CI: ruff + pytest + docker build on every push/PR
- ✅ PWA assets + structured logging

### Hardening release (v3.2.4 — Audit & Hardening)
- ✅ Security: path-traversal-proof downloads, filename sanitization, enforced upload size limit (`413`)
- ✅ Fixes: notification inbox persistence, XLSX formula-vs-value export, three-way version consistency
- ✅ Architecture: central `app/config.py`, dedicated `app/security.py`, proper package `__init__.py`s, dead-code removal
- ✅ Test isolation via fixtures (repo `data/` never polluted); suite grew 19 → **29 tests**
- ✅ Repo hygiene: runtime data untracked and git-ignored
- ✅ Docs rewrite: README / API / ARCHITECTURE / SECURITY / guides aligned to actual source

### Real engines available as libraries (not yet in API)
- ✅ `app/ocr/tesseract_engine.py` — genuine Tesseract OCR (`pytesseract`) and RapidOCR (ONNX) implementations with graceful degradation when binaries/libs are missing; configurable via `TESSERACT_CMD`, `OCR_LANGS` (default `eng+fas`)
- ✅ SMS adapters for Ghasedak & Kavenegar with balance check (`test_connection`) and mock fallback

---

## Next up — v3.3 «Wire the intelligence in»

Priority order reflects user value ÷ effort:

1. ⬜ **OCR into `/api/process`** — when extraction yields empty text (scanned PDF/image), call `tesseract_engine.extract_tesseract()` / RapidOCR automatically; store `{engine, confidence}` in the workroom. *The engines exist; this is integration + tests.*
2. ⬜ **Retire mock engines in `multi_engine.py`** — replace fabricated paddle/easy outputs with real engine list or remove them; keep only honest fallbacks.
3. ⬜ **Translation endpoint** — `POST /api/translate {job_id, target}` using a real provider behind the existing `TranslationProvider` interface (DeepL/Google/local NLLB), keeping `"mock": true` semantics for offline dev.
4. ⬜ **Legacy format conversion** — optional LibreOffice-headless step so DOC/XLS/PPT/ODS/ODP become extractable; clean error if binary absent.
5. ⬜ **Notifications wiring** — emit in-app/Telegram notifications after job completion from the API path (channels already implemented).

## Then — v4.0 «Multi-user ready»

6. ⬜ **Authentication & tenancy** — API keys or session auth; per-user workroom visibility. **Blocking requirement before any public deployment.**
7. ⬜ **Database-backed store** — SQLite first (zero-ops), Postgres optional; migrate workrooms/audit out of loose files; keep filesystem blobs.
8. ⬜ **Rate limiting & quotas** — per-key upload limits, disk quota enforcement.
9. ⬜ **Job lifecycle** — list/get/delete jobs endpoints; retention policy with automatic purge.
10. ⬜ **Observability** — Prometheus `/metrics`, OpenTelemetry traces, graceful shutdown hooks (closes factor IX gap).

## Backlog / research

- Layout reconstruction (tables/figures with bounding boxes via layout-parser-class approaches)
- Golden benchmark dataset + quality scoring (`GoldenBenchmark` scaffold exists)
- Bulk folder import & watch directories
- Webhooks on job completion
- Plugin system for third-party adapters

## Explicit non-goals (for now)

- Cloud storage backends (S3/GCS) — contradicts local-first until there's demand
- Mobile apps — the panel is responsive + PWA-installable
- Paid/commercial features — MIT core stays MIT

---

*Change policy: moving an item between sections requires a PR that updates this file plus `CHANGELOG.md`; the docs are part of the definition of done ([CONTRIBUTING.md](CONTRIBUTING.md)).*
