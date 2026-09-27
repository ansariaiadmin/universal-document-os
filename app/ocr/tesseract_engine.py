"""Tesseract OCR engine — REAL implementation via pytesseract.

Returns empty text (confidence 0.0, skipped=True) when the binary/library is
unavailable, so MultiEngineOCR can fall back cleanly instead of fabricating
output. Configure with env vars: TESSERACT_CMD, OCR_LANGS (default eng+fas).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger("udo.ocr")


def _mean_confidence(pixels) -> float:
    """Average per-pixel confidence from a RapidOCR result (0..1)."""
    confs = [float(r[1]) for r in pixels if isinstance(r[1], (int, float)) or str(r[1]).replace(".", "").isdigit()]
    return round(sum(confs) / len(confs), 3) if confs else 0.0


def extract_rapidocr(file_path: str) -> Dict[str, Any]:
    """Real local OCR via rapidocr-onnxruntime (ONNX models, no external binary).

    Good fallback where tesseract isn't installed; supports Latin + Chinese
    out of the box. Returns skipped=True when the package is not installed.
    """
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        logger.info("rapidocr not installed (pip install rapidocr-onnxruntime): %s", e)
        return {"text": "", "confidence": 0.0, "engine": "rapidocr", "skipped": True,
                "reason": f"deps missing: {e}"}
    try:
        engine = RapidOCR()
        result, _elapse = engine(file_path)
        if not result:
            return {"text": "", "confidence": 0.0, "engine": "rapidocr"}
        lines = [str(item[1]) for item in result]
        conf = _mean_confidence([item for item in result])
        return {"text": "\n".join(lines).strip(), "confidence": conf, "engine": "rapidocr"}
    except FileNotFoundError:
        return {"text": "", "confidence": 0.0, "engine": "rapidocr", "skipped": True,
                "reason": "image file not found"}
    except Exception as e:
        raise RuntimeError(f"rapidocr OCR failed: {e}")


def extract_tesseract(file_path: str) -> Dict[str, Any]:
    """Run real OCR on an image path. Never raises for missing deps."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        logger.info("tesseract deps missing (pip install pytesseract pillow): %s", e)
        return {"text": "", "confidence": 0.0, "engine": "tesseract", "skipped": True,
                "reason": f"deps missing: {e}"}

    cmd = os.getenv("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    langs = os.getenv("OCR_LANGS", "eng+fas")
    try:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img, lang=langs)
        try:
            data = pytesseract.image_to_data(img, lang=langs, output_type=pytesseract.Output.DICT)
            confs = [float(c) for c in data.get("conf", []) if str(c).replace(".", "").replace("-", "").isdigit()]
            # tesseract confidences are 0..100 per word; average over recognized words
            positive = [c for c in confs if c > 0]
            confidence = round(sum(positive) / len(positive) / 100.0, 3) if positive else 0.0
        except Exception:  # confidence estimation must never break extraction
            confidence = 0.0 if not text.strip() else 0.8
        return {"text": text.strip(), "confidence": confidence, "engine": "tesseract"}
    except FileNotFoundError:
        logger.info("tesseract binary not found — install it or set TESSERACT_CMD")
        return {"text": "", "confidence": 0.0, "engine": "tesseract", "skipped": True,
                "reason": "tesseract binary not found"}
    except Exception as e:
        # pytesseract raises TesseractNotFoundError (subclass of EnvironmentError)
        # when the binary is missing; treat that as a clean skip so the next
        # engine can take over instead of failing the whole request.
        if isinstance(e, OSError) or "not installed" in str(e).lower():
            logger.info("tesseract unavailable: %s", e)
            return {"text": "", "confidence": 0.0, "engine": "tesseract", "skipped": True,
                    "reason": str(e)}
        raise RuntimeError(f"tesseract OCR failed: {e}")
