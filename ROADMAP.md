# Roadmap — Universal Document OS

**Last updated:** v4.2.0 (follow-up) · This file states honestly what is shipped, what is scaffolded, and what is planned. No hidden gaps, no vaporware claims.

---

## Status legend

- ✅ **Shipped** — working, tested, reachable through the API/UI today
- 🟡 **Scaffolded** — real code exists in the repo but is not wired into the request path
- ⬜ **Planned** — designed, not started

---

## Shipped (through v4.2.0)

### Core pipeline (v0.9 → v4.2)
- ✅ Adapter registry with PDF / DOCX / XLSX / PPTX / ODT / ODS / ODP / TXT / MD / CSV / JSON / HTML / RTF extraction (OpenDocument via stdlib, zero extra deps)
- ✅ Real OCR for images wired into `/api/process` (Tesseract binary ships in the Docker image with `eng+fas`; RapidOCR pip-fallback)
- ✅ Real DOC extraction via `antiword` (when the binary is present)
- ✅ Landing + VS Code-style upload panel with a **Smart Dashboard tab**, streaming multipart processing, workroom records, SQLite job store, append-only audit log
- ✅ `GET /api/dashboard` — live measured facts (real engine probes, conversion matrix, counters)
- ✅ Export/convert to `.txt`/`.md`/`.html` + traversal-safe download endpoint
- ✅ Adaptive content guard: magic bytes, zip-bomb budget, extraction size ceilings
- ✅ Docker: multi-stage, non-root, tesseract+fas, healthcheck; docker-compose single service
- ✅ Opt-in API-key auth (timing-safe) + opt-in rate limiting + Prometheus metrics
- ✅ Real PWA surface: served web manifest, generated PNG icons, service worker
- ✅ CI: ruff + pytest + docker build on every push/PR (tool versions pinned)

### Honesty release (v4.2.0 follow-up — audit fixes)
- ✅ Arabic no longer misdetected as Persian; timing-safe API-key comparison
- ✅ `backup.sh` archives all of `data/` (secret values redacted); optional passphrase encryption
- ✅ `.dockerignore` keeps private data out of images; `.gitignore` covers all of `data/`
- ✅ Translation module no longer returns fabricated benchmark scores; benchmark refuses without a dataset
- ✅ Scripts (install/status/update/backup/smoke-test) rewritten for this repo; dead copied-project blocks removed
- ✅ Docs unified on v4.2.0; suite grew to **89 tests**

### Still scaffolded (real code, not exposed via API)
- 🟡 SMS adapters for Ghasedak & Kavenegar (real HTTP adapters, mock fallback) — no request handler calls them yet
- 🟡 Notification service (persistent in-app inbox + real Telegram send) — not wired into the API path
- 🟡 Translation service (mock provider flagged `"mock": true`) — no endpoint yet

---

## Next up

Priority order reflects user value ÷ effort:

1. ⬜ **OCR for scanned PDFs** — render PDF pages and run the existing OCR engines when a PDF yields no text layer (`{engine, confidence}` stored in the workroom). *Engines are real; this is rendering + integration.*
2. ⬜ **Translation endpoint** — `POST /api/translate {job_id, target}` using a real provider behind the existing `TranslationProvider` interface (DeepL/Google/local NLLB), keeping `"mock": true` semantics for offline dev.
3. ⬜ **Notifications wiring** — emit in-app/Telegram notifications after job completion from the API path (channels already implemented).
4. ⬜ **Legacy XLS/PPT conversion** — optional LibreOffice-headless step; clean error if the binary is absent (DOC already works via antiword).
5. ⬜ **Real quality benchmark** — a small ground-truth dataset + scoring so `GoldenBenchmark` can report real metrics instead of refusing.

## Then — «Multi-user ready»

6. 🟡→⬜ **Full tenancy** — API-key auth exists (opt-in); add sessions/per-user workroom visibility. **Blocking requirement before any public deployment.**
7. ⬜ **Database-backed store for workrooms/audit** — the job store is already SQLite; migrate the rest; keep filesystem blobs.
8. ⬜ **Quotas** — per-key disk quotas on top of the existing rate limiter.
9. ⬜ **Job lifecycle UI** — delete/retention controls beyond the TTL sweeper.
10. ⬜ **Observability** — Prometheus `/metrics` shipped; OpenTelemetry traces next.

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
