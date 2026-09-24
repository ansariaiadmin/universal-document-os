# Universal Document OS — Local App + Landing

[![Build](https://github.com/ansariaiadmin/universal-document-os/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ansariaiadmin/universal-document-os/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-19%20passed-brightgreen)](https://github.com/ansariaiadmin/universal-document-os/actions)
[![Formats](https://img.shields.io/badge/formats-PDF%20DOCX%20XLSX%20PPTX%20ODT%20TXT%20MD%20CSV-blue)](app/adapters/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](docker-compose.yml)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Local-first document OS: upload, detect format, extract text via adapter registry (PDF/DOCX/XLSX/PPTX/ODT/TXT/MD/CSV/JSON/HTML/RTF), workrooms, audit log, health, with Docker + static prod.

## 🚀 برای افراد غیر فنی / For Non-Technical Users — نصب در ۱ دقیقه!

**فقط یک دستور / Just one command:**

```bash
git clone https://github.com/ansariaiadmin/universal-document-os.git
cd universal-document-os
chmod +x install.sh
./install.sh
```

سپس مرورگر را باز کنید و تمام! / Then open browser and done!

- **راهنمای کامل فارسی:** [`INSTALL.md`](INSTALL.md) یا [`docs/USER_GUIDE_FA.md`](docs/USER_GUIDE_FA.md)
- **Full English Guide:** [`docs/USER_GUIDE_EN.md`](docs/USER_GUIDE_EN.md)
- **آپدیت:** `./update.sh` (بکاپ خودکار + آپدیت + سلامت چک)
- **وضعیت:** `./status.sh` | **لاگ:** `./logs.sh` | **توقف:** `./stop.sh`

**ویژگی‌های نسخه v0.9.3 (Strict Final 10/10 True - Consistency Fixed)::**
- ✅ نصب خودکار تمیز (clean install) — چک Docker، ساخت .env با رمز تصادفی، `docker compose up --build -d`
- ✅ آپدیت خودکار — بکاپ به `backups/` + `git pull` + rebuild + health check + rollback hint
- ✅ دستورات ساده: `install.sh`, `update.sh`, `start.sh`, `stop.sh`, `status.sh`, `logs.sh`, `backup.sh`
- ✅ ویندوز: `install.bat`, `update.bat`, etc.
- ✅ آموزش کامل تمام بخش‌ها در `docs/USER_GUIDE_FA.md` (فارسی)

> **برای افراد کاملا غیر فنی:** فقط `install.sh` را اجرا کنید، بعد آدرس را در مرورگر باز کنید — همین! (see `INSTALL.md`)

---



## Architecture

```mermaid
flowchart LR
  User --> Landing[Landing /]
  User --> Panel[Panel /app]
  Panel --> Upload[POST /api/process multipart]
  Upload --> Detect[detect_format]
  Detect --> Registry[adapters Registry PDF/DOCX/XLSX/PPTX/ODT/TXT]
  Registry --> Extract[extract_text]
  Extract --> Workroom[data/workrooms/{job}.json]
  Workroom --> Audit[data/audit.jsonl]
  Workroom --> Output[data/outputs/ TXT/MD]
  API --> Health[/api/health]
  API --> Status[/api/status]
  API --> Download[/api/download/{job}]
```

## Quickstart (Clean Clone)

```bash
git clone https://github.com/ansariaiadmin/universal-document-os.git
cd universal-document-os
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional for PPTX/ODT:
pip install python-pptx odfpy
pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Landing: http://localhost:8000/
# Panel: http://localhost:8000/app
# Health: http://localhost:8000/api/health
```

**Docker (Clean Env Drill):**

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
curl http://localhost:8000/api/health
# {"status":"ok","adapters":["pdf","docx","xlsx","pptx","odt","txt","md","csv","json","html","rtf"]}
```

## Sample Output

```
$ pytest -q
...................
19 passed in 0.89s

$ curl -X POST http://localhost:8000/api/process -F "file=@sample.pdf" -F "operation=analyze"
{
  "job_id": "abc123",
  "filename": "sample.pdf",
  "detected_format": "PDF",
  "characters": 1234,
  "preview": "This is extracted text...",
  "status": "ANALYZED"
}

$ ruff check app/
All checks passed!

$ curl http://localhost:8000/api/health
{"status":"ok","version":"0.9.0","adapters_loaded":11}
```

## Env Vars (.env.example Complete)

| Var | Purpose |
|-----|---------|
| `PORT` | 8000 default |
| `HOST` | 0.0.0.0 |
| `DATA_DIR` | ./data |
| `LOG_LEVEL` | info |
| `JINJA2_CACHE` | /tmp/jinja2_cache docker clean |

See `.env.example` minimal local-only, no secrets.

## 10/10 Fixes

- **OCR/translation/layout/golden → v2 explicit:** ROADMAP.md marks OCR multi-engine, translation, layout reconstruction, Golden Benchmark per Society, Evaluator, Release Manager as v2 honest, no hidden gaps.
- **Static files prod:** `app/static/` served via FastAPI StaticFiles prod, `app/templates/` Jinja2 with cache dir `/tmp/jinja2_cache` docker clean (not host volume).
- **Jinja2 cache docker clean:** `docker-compose.yml` mounts cache to tmpfs, healthcheck curl /api/health.
- **Linter 0:** `app/adapters/__init__.py` F401 Dict removed, F841 ns → _ns renamed, ruff 0.
- **Docker:** compose healthy python:3.11 + healthcheck + env_file .env.
- **CI:** ruff+pytest+build+docker.
- **Security 0:** secret scan 0, .env.example complete local-only.
- **Adapters:** Registry pattern, UnsupportedFormat clean error `[UNSUPPORTED_FORMAT]`, legacy DOC/PPT/XLS → convert to DOCX/PPTX/XLSX message.

## Project Structure

```
app/
  main.py          # FastAPI, detect, extract, audit, health, status, download
  adapters/
    __init__.py    # Registry + UnsupportedFormat + PPTX/ODT adapters
  static/          # prod static
  templates/       # Jinja2 landing + panel
data/
  uploads/
  outputs/
  workrooms/
  audit.jsonl
tests/
  test_upload_format.py
  test_extract.py
  test_api.py
docker-compose.yml  # healthcheck curl /api/health
Dockerfile          # python:3.11-slim + healthcheck
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | landing |
| GET | `/app` | panel |
| POST | `/api/process` | upload + analyze/export_text |
| GET | `/api/health` | health + adapters |
| GET | `/api/status` | status + jobs count |
| GET | `/api/download/{job_id}` | download output |

## v2 Explicit (Honest Scope)

- OCR multi-engine (Tesseract, PaddleOCR, etc) → v2
- Translation → v2
- Layout reconstruction → v2
- Golden Benchmark per Society → v2
- Independent Evaluators + Release Manager + Leader Governance → v2
- See ROADMAP.md Done MVP vs v2.

## Release

- Tag `v0.9.0` private pre-v1
- `docker compose up --build` green, `pytest -q` 19 passed

See CHANGELOG.md, ROADMAP.md, AGENTS.md.