# Roadmap — universal-document-os

## Done (v0.9.0)

- [x] Adapters architecture with Registry pattern
- [x] PDF/DOCX/XLSX/PPTX/ODT/TXT/MD/CSV/JSON/HTML/RTF support with clean UnsupportedFormat
- [x] Landing + panel pages, upload + extract_text dispatch
- [x] 19 tests passing
- [x] Docker compose healthy with healthcheck
- [x] CI: ruff + pytest
- [x] Docs: README badge+mermaid+quickstart

## v2 (Explicit, Honest — No Hidden Gaps)

### Why v2?
- **OCR**: Currently text extraction only (pypdf, docx, openpyxl). v2 will add OCR multi-engine: tesseract, paddle-ocr, easyocr for scanned PDFs/images. Reason: needs heavy ML models + GPU, currently text-only for MVP.
- **Translation**: Currently no translation. v2: translation adapter (MarianMT, NLLB, Google Translate API) for multilingual docs. Reason: needs model + API key, currently not in scope.
- **Layout Rebuild**: Currently extracts raw text. v2: layout rebuild with bounding boxes, tables, figures preservation via layout-parser + unstructured. Reason: needs ML models + complex heuristics.
- **Golden Benchmarks**: Need golden dataset per Society: evaluator independent, Society evaluation protocol. Reason: requires curated dataset + human eval.
- **Evaluator Independent**: Currently no independent evaluator. v2: evaluator service with LLM-as-judge + human review.
- **Release Manager**: Currently no release manager. v2: release manager agent for versioning + changelog.

### Next Steps
1. OCR multi-engine integration (tesseract + paddle)
2. Translation adapter
3. Layout rebuild with tables/figures
4. Golden benchmarks dataset
5. Independent evaluator
6. Release manager agent

## Static Files Prod + Jinja2 Cache Docker Clean

- Static files: app.mount("/static", StaticFiles(directory=BASE/app/static)) — prod ready, cached
- Jinja2 cache: templates = Jinja2Templates(directory=BASE/app/templates) — in prod, cache enabled, in dev reload
- Docker clean: docker compose up --build works on clean env, healthcheck curl /api/health, no cache leak
