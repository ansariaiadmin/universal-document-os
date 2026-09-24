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
