# Contributing to Universal Document OS

Thanks for being here. This project values **small, verifiable changes** and **documentation that matches the code**. The rules below are what CI actually enforces — not aspirational style notes.

---

## 1. Get set up (5 minutes)

```bash
git clone https://github.com/ansariaiadmin/universal-document-os.git
cd universal-document-os
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -q          # expect: 89 passed
ruff check .       # expect: All checks passed!
uvicorn app.main:app --reload --port 8000   # optional live server
```

Windows: use `.venv\Scripts\activate`. For container-based work see [INSTALL.md](INSTALL.md).

## 2. Branch & commit conventions

- Branch from `main`: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `chore/<short-name>`.
- Conventional Commits: `feat: add EPUB adapter`, `fix: enforce upload size cap`, `docs: align API examples with v3.2.4`.
- One logical change per PR. If you refactor *and* fix behavior, split it.

## 3. Definition of Done (PR checklist)

Code:
- [ ] `pytest -q` passes locally (add at least one test for any new behavior; bug fixes need a regression test)
- [ ] `ruff check .` clean
- [ ] No new required dependency without adding it to `requirements.txt` (optional deps must degrade gracefully via `UnsupportedFormat`)
- [ ] No fabricated outputs: unavailable engines/tools produce honest errors; the dashboard only shows measured values

Contracts (this repo treats these as hard rules):
- [ ] Any user-supplied filename/path goes through `app/security.py` helpers only
- [ ] Extraction failures return tagged strings, never 5xx
- [ ] Version changes happen in `app/config.py` alone; `/api/health`, app metadata, README badge stay consistent (a test asserts this)

Docs (updated **in the same PR**):
- [ ] New/changed endpoint → [docs/API.md](docs/API.md) example + response shape updated
- [ ] New env var → table in README §Configuration + `.env.example` comment
- [ ] New format → formats table in README + docs/API
- [ ] Architecture-level change → [ARCHITECTURE.md](ARCHITECTURE.md) module map / ADR list
- [ ] User-visible feature → CHANGELOG entry under an "Unreleased" heading
- [ ] Scripts changed → keep `.sh` and `.bat` pairs equivalent; port stays **8000** everywhere
- [ ] New env var → actually read it in `app/` code, and keep `.env.example` limited to real variables

## 4. Testing guidelines

- Put shared fixtures in `tests/conftest.py`; the session fixture already redirects `UPLOADS/OUTPUTS/WORKROOMS/AUDIT_FILE` to a temp dir — rely on it instead of touching repo `data/`.
- Test behavior through the HTTP surface (`TestClient`) when possible; unit-test pure helpers (`sanitize_filename`, `resolve_within`, adapters) directly.
- Async services (SMS/notification) can be tested by monkey-patching `httpx.AsyncClient` — no real outbound calls in CI.

## 5. Style

- Python 3.11+, type hints where they clarify, `from __future__ import annotations` in modules.
- Line length ≤ 120 (ruff config in `pyproject.toml`).
- Logging via `logging`/`app.lib.logger` — never `print()` at import time or in request paths.
- Docstrings: one-line summary + parameters/returns for public functions. Keep them truthful to current behavior.

## 6. Review process

1. Open a PR against `main`; fill the template (what/why/how-tested + checklist above).
2. CI must be green: ruff, pytest, docker build.
3. A maintainer reviews within a few days; expect direct, kind feedback focused on invariants.
4. Merge = squash with your commit subject as the message.

## 7. Good first issues

Look for the [`good-first-issue`](https://github.com/ansariaiadmin/universal-document-os/issues?q=is%3Aissue+is%3Aopen+label%3Agood-first-issue) label. Typical shapes: add a detector mapping for a missing extension alias, improve an error message, document an edge case discovered in tests.

## 8. What we won't merge

- Secrets, tokens, or real customer documents anywhere in the repo (including tests/fixtures)
- Features undocumented or untested
- Changes that break the security invariants (§3 Contracts)
- Cloud-service lock-in on the core path without a local-first fallback flag

Questions? Open a discussion or read [AGENTS.md](AGENTS.md) for the deep handoff map.
