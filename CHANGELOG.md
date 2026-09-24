## [v0.9.1] - 2026-09-24 - Non-Technical Auto Install + Auto Update Edition

### Added - نصب خودکار برای افراد غیر فنی
- **install.sh**: نصب خودکار تمیز - چک Docker, ساخت .env با رمز تصادفی openssl, docker compose up --build -d, صبر 30s, سلامت چک, نمایش آدرس و رمز ورود
- **update.sh**: آپدیت خودکار - بکاپ به backups/YYYYMMDD-HHMMSS/, git pull origin main, docker compose pull + up --build -d, health check, rollback hint
- **start.sh, stop.sh, status.sh, logs.sh, backup.sh**: دستورات ساده روزانه
- **install.bat, start.bat, stop.bat, status.bat, logs.bat, update.bat, backup.bat**: نسخه ویندوز برای افراد غیر فنی
- **INSTALL.md**: راهنمای کامل فارسی نصب در 3 قدم (<5 دقیقه)
- **docs/USER_GUIDE_FA.md**: آموزش کامل تمام بخش‌ها - داشبورد, تنظیمات .env, Docker چیست, بکاپ, عیب‌یابی, امنیت, ورژن‌ها
- **docs/USER_GUIDE_EN.md**: Full English guide for non-technical
- **README**: بخش جدید "برای افراد غیر فنی / For Non-Technical Users — نصب در 1 دقیقه!" با one-liner

### Fixed
- Clean presentation: حذف cache artifacts, .env فقط .env.example
- Non-technical UX: پیام‌های فارسی + انگلیسی، رنگی، راهنمای قدم به قدم

### Docs
- README badge+mermaid+quickstart+sample output + non-technical section
- INSTALL.md + docs/USER_GUIDE_FA.md + docs/USER_GUIDE_EN.md

# Changelog — universal-document-os

## [0.9.0] - 2026-09-24

### Added
- 19 tests passing: upload/format/PDF/TXT/CSV/MD/audit, adapters registry, unsupported format clean
- Adapters architecture: app/adapters/__init__.py Registry pattern @register(FMT), SUPPORTED_FORMATS, get_extractor, extract, UnsupportedFormat with clean message
- PDF: pypdf, DOCX: python-docx, XLSX: openpyxl, PPTX: python-pptx if installed else UnsupportedFormat clean, ODT: odfpy + zipfile fallback content.xml, TXT/MD/CSV/JSON/HTML/RTF utf-8 reader, legacy DOC/PPT/XLS/ODS/ODP UnsupportedFormat with convert guidance
- Landing fix: TemplateResponse supports both old and new Starlette signatures (fixes httpx test client)
- Docker compose healthy: healthcheck curl /api/health
- CI: ruff + pytest + build + docker
- Docs: README badge+mermaid+quickstart+sample output, ROADMAP Done vs v2

### Fixed
- Jinja2 cache warning: templates cache disabled in dev, static files prod via StaticFiles mount
- Static files prod: app.mount("/static", StaticFiles) with directory BASE/app/static
- Landing page: supports both TemplateResponse signatures

### Security
- Secret scan 0, .env.example minimal (PORT only, local-first)
- No private key, local-first

## [0.8.0] - 2026-09-07
- Previous release with 19 tests
