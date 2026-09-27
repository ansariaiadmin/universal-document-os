"""
Universal Document OS — Translation Service (scaffold, honestly labeled)

Status: the provider interface and a mock provider exist; this service is NOT
wired into any HTTP endpoint yet. The old "GoldenBenchmark" returned
hard-coded fabricated scores (0.92 / 0.89 / …) — those were removed: without
a ground-truth dataset there is nothing honest to report, so evaluate()
raises until a dataset is configured.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TranslationProvider:
    def __init__(self, name: str):
        self.name = name

    def translate(self, text: str, source: str, target: str) -> Dict[str, Any]:
        raise NotImplementedError


class MockTranslationProvider(TranslationProvider):
    def __init__(self):
        super().__init__("mock")
        self.enabled = os.getenv("TRANSLATION_ENABLED", "false").lower() == "true"

    def translate(self, text: str, source: str, target: str) -> Dict[str, Any]:
        if not self.enabled:
            return {"translated": text, "provider": self.name, "mock": True}
        # Mock "translation": prefix-based, clearly marked as mock.
        return {
            "translated": f"[{target}] {text} (translated from {source} via {self.name})",
            "provider": self.name,
            "source": source,
            "target": target,
            "mock": True,
        }


class LayoutReconstructor:
    """Returns empty blocks until a real layout model is wired in.

    The previous version fabricated "Sample Heading" blocks with fake
    bounding boxes — that was dishonest output and was removed.
    """

    def reconstruct(self, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.debug("layout: %d page(s) received — no layout model wired yet", len(pages))
        return {"pages": len(pages), "blocks": [], "reconstructed": False,
                "note": "layout reconstruction is a planned feature (ROADMAP)"}


class GoldenBenchmark:
    """Quality benchmark — requires a ground-truth dataset.

    No dataset configured => metrics cannot be computed and this raises.
    It will never return invented numbers.
    """

    def __init__(self, datasets: List[str] | None = None):
        self.datasets = datasets or []  # configured via code when a real dataset lands

    def evaluate(self, extracted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
        if not self.datasets or not ground_truth:
            raise RuntimeError(
                "GoldenBenchmark has no ground-truth dataset configured; "
                "metrics would be fabricated. See ROADMAP.md (planned feature)."
            )
        # Real scoring logic lands together with the dataset (ROADMAP).
        raise NotImplementedError("benchmark scoring is a planned feature (ROADMAP)")


class TranslationService:
    """Translation + layout + benchmark scaffolding (mock provider; honest)."""

    def __init__(self):
        self.provider = MockTranslationProvider()
        self.layout = LayoutReconstructor()
        self.benchmark = GoldenBenchmark()
        self.enabled = self.provider.enabled

    def translate_document(self, doc: Dict[str, Any], target_lang: str = "en") -> Dict[str, Any]:
        source_lang = doc.get("lang", "fa")
        text = doc.get("text", "")
        translated = self.provider.translate(text, source_lang, target_lang)
        layout = self.layout.reconstruct(doc.get("pages", []))
        return {
            "original": doc,
            "translated": translated["translated"],
            "mock": translated.get("mock", False),
            "layout": layout,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

    def benchmark_quality(self, extracted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
        return self.benchmark.evaluate(extracted, ground_truth)


# Singleton
translation_service = TranslationService()
