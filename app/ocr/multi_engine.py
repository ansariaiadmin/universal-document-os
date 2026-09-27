"""OCR multi-engine orchestrator.

Every engine here performs REAL extraction — there are no mock/stub outputs.
Engines that lack their binary or Python dependency report ``skipped=True``
so the orchestrator can fall back cleanly instead of fabricating text.

Available engines
-----------------
- ``tesseract``  : pytesseract (+ tesseract binary). Set ``TESSERACT_CMD`` and
                   ``OCR_LANGS`` (default ``eng+fas``) to configure.
- ``rapidocr``   : rapidocr-onnxruntime — pure-Python ONNX models, no system
                   binary needed; good zero-install fallback.

Env: ``OCR_ENGINES`` — comma-separated priority list
     (default ``tesseract,rapidocr``).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from app.ocr.tesseract_engine import extract_rapidocr, extract_tesseract

logger = logging.getLogger("udo.ocr")


class OCREngine:
    """Named wrapper around a callable extractor."""

    def __init__(self, name: str, fn: Callable[[str], Dict[str, Any]]):
        self.name = name
        self._fn = fn

    def extract(self, file_path: str) -> Dict[str, Any]:
        return self._fn(file_path)


def _available_engines() -> List[OCREngine]:
    registry = {
        "tesseract": OCREngine("tesseract", extract_tesseract),
        "rapidocr": OCREngine("rapidocr", extract_rapidocr),
    }
    order = [e.strip().lower() for e in os.getenv("OCR_ENGINES", "tesseract,rapidocr").split(",") if e.strip()]
    engines: List[OCREngine] = []
    for name in order:
        if name in registry:
            engines.append(registry[name])
        else:
            logger.warning("unknown OCR engine in OCR_ENGINES: %s", name)
    return engines


class MultiEngineOCR:
    """Try each configured engine in priority order; keep the best result.

    Selection rule: highest non-zero confidence wins. On equal confidence the
    earlier (higher-priority) engine wins. An empty-but-successful result is
    still returned (it means the image genuinely had no detectable text),
    while skipped/failed engines are transparently bypassed.
    """

    def __init__(self, engines: Optional[List[OCREngine]] = None):
        self.engines: List[OCREngine] = engines if engines is not None else _available_engines()

    def extract(self, file_path: str, preferred: Optional[str] = None) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for engine in self.engines:
            if preferred and engine.name != preferred:
                continue
            try:
                result = engine.extract(file_path)
            except Exception as e:
                logger.warning("[ocr:%s] failed: %s", engine.name, e)
                continue
            if not result.get("skipped"):
                results.append(result)

        if not results:
            return {"text": "", "confidence": 0.0, "engine": "none",
                    "error": "no OCR engine available (install pytesseract+tesseract binary, or rapidocr-onnxruntime)"}

        best = max(results, key=lambda r: r["confidence"])
        logger.info("[multi-ocr] chose %s (confidence %.3f) from %d result(s)",
                    best["engine"], best["confidence"], len(results))
        return {
            "text": best["text"],
            "confidence": best["confidence"],
            "engine": best["engine"],
            "all_results": results,
        }

    def health(self) -> Dict[str, bool]:
        """Report which engines are actually usable right now (real probes)."""
        from app.ocr.tesseract_engine import engine_available

        return {engine.name: engine_available(engine.name) for engine in self.engines}


# Singleton used across the app
ocr = MultiEngineOCR()
