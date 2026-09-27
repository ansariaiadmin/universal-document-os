"""Document intelligence — adaptive language detection & content classification.

Pure-stdlib heuristics (no model downloads, deterministic, unit-testable):

- ``detect_language``: script-aware first (Arabic/Persian/Hebrew/CJK/Cyrillic
  blocks are unambiguous), then diacritic-free Latin text is scored against
  compact high-frequency word lists for English vs. a few European languages.
  Returns ISO-639-1 codes: ``fa``, ``ar``, ``en``, ``de``, ``fr``, ``es``,
  ``ru``, ``zh`` … or ``und`` when there is not enough signal to be honest.

- ``classify_document``: maps extracted text to a coarse document type using
  weighted keyword hits per category — the same idea behind classic Naive
  Bayes zero-shot routing, kept dependency-free and explainable.

Both feed the pipeline so downstream operations (translation target choice,
OCR language hint, panel badges) can adapt per-document instead of per-deploy.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

# --- Unicode block ranges (script-first detection) -------------------------
_RANGES = {
    "ar": ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF)),  # Arabic + Persian ligatures
    "he": ((0x0590, 0x05FF),),
    "zh": ((0x4E00, 0x9FFF), (0x3400, 0x4DBF)),
    "ru": ((0x0400, 0x04FF),),
}
_FA_EXTRA = set("پچژگکیه")  # letters unique to Persian among Arabic-script chars


def _in_ranges(ch: str, ranges) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in ranges)


# Compact stopword profiles — only words that discriminate quickly.
_PROFILES = {
    "en": "the of and to in is that it for with as was on are be this have from or by an at not you can will each more their them there here",
    "de": "der die und in den von zu das mit sich des auf für ist im dem nicht ein eine als auch es an werden aus er hat",
    "fr": "le des de la et les pour dans qu est au ne pas ce qui ou bien avec tous sur sous tres cette vous nous pouvez",
    "es": "de la que el en y a los del se las por un para con no una su al lo como mas pero sus le ya o este si porque",
}
_PROFILE_SETS = {k: set(v.split()) for k, v in _PROFILES.items()}

_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ]+")


def detect_language(text: str) -> dict:
    """Return ``{language, confidence, method}`` for a chunk of text.

    Script evidence wins; Latin text falls back to stopword scoring.
    Confidence is deliberately conservative: short inputs stay low.
    """
    sample = (text or "")[:2000]
    letters = [c for c in sample if c.isalpha()]
    if len(letters) < 8:
        return {"language": "und", "confidence": 0.0, "method": "insufficient-text"}

    counts: Counter[str] = Counter()
    for ch in letters:
        for lang, ranges in _RANGES.items():
            if _in_ranges(ch, ranges):
                counts[lang] += 1
                break

    total = len(letters)
    # Persian vs Arabic disambiguation inside the Arabic script block.
    if counts["ar"]:
        ar_letters = counts["ar"]
        fa_marks = sum(1 for c in letters if c in _FA_EXTRA)
        if fa_marks >= max(2, 0.05 * ar_letters):
            return {
                "language": "fa",
                "confidence": round(min(0.99, 0.5 + fa_marks / ar_letters), 2),
                "method": "script+persian-chars",
            }
        return {
            "language": "ar",
            "confidence": round(min(0.99, counts["ar"] / total), 2),
            "method": "script",
        }
    for lang in ("he", "zh", "ru"):
        if counts[lang] / total > 0.5:
            return {
                "language": lang,
                "confidence": round(min(0.99, counts[lang] / total), 2),
                "method": "script",
            }

    # Latin path: stopword profile scoring over normalized tokens.
    words = [
        unicodedata.normalize("NFKD", w.lower()).encode("ascii", "ignore").decode()
        for w in _WORD_RE.findall(sample)
    ]
    if len(words) < 6:
        return {"language": "und", "confidence": 0.0, "method": "insufficient-text"}
    tokens = set(words)
    scores = {lg: len(tokens & prof) / len(prof) for lg, prof in _PROFILE_SETS.items()}
    best, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score < 0.04:
        return {"language": "und", "confidence": 0.0, "method": "no-profile-match"}
    ranked = sorted(scores.values(), reverse=True)
    margin = ranked[0] - (ranked[1] if len(ranked) > 1 else 0.0)
    conf = min(0.95, best_score * 2 + margin)
    return {"language": best, "confidence": round(conf, 2), "method": "stopwords"}


# --- Document classification ------------------------------------------------
_CATEGORIES = {
    "invoice": ["invoice", "facture", "rechnung", "total due", "bill to", "vat", "tax id",
                "amount", "qty", "price", "iban", "po number", "فاکتور", "صورتحساب", "بهای"],
    "contract": ["agreement", "contract", "party", "parties", "clause", "shall", "terms and conditions",
                 "termination", "liability", "warranty", "قانون", "ماده", "طرفین", "قرارداد", "شرایط"],
    "resume": ["curriculum vitae", "resume", "experience", "education", "skills", "employment history",
               "résumé", "lebenslauf", "سوابق", "تحصیلات", "رزومه", "مهارت"],
    "report": ["summary", "findings", "analysis", "conclusion", "recommendations", "quarterly",
               "annual report", "executive summary", "methodology", "گزارش", "نتایج", "تحلیل"],
    "manual": ["instructions", "installation", "troubleshooting", "warning", "caution",
               "user guide", "reference manual", "saftey", "safety", "راه‌اندازی", "راهنما", "نصب"],
    "letter": ["dear", "sincerely", "regards", "attention", "est.", "sehr geehrte",
               "chère", "با سلام", "احتراماً", "ارادتمند"],
}


def classify_document(text: str) -> dict:
    """Weighted keyword scoring → ``{category, scores}``. Default: ``general``."""
    hay = (text or "").lower()[:20000]
    scores = {}
    for cat, kws in _CATEGORIES.items():
        s = sum(1 for kw in kws if kw in hay)
        if s:
            scores[cat] = s
    if not scores:
        return {"category": "general", "scores": {}}
    best = max(scores.items(), key=lambda kv: kv[1])
    return {"category": best[0], "scores": scores}


def analyze(text: str) -> dict:
    """One-shot intelligence bundle used by the pipeline."""
    words = len(_WORD_RE.findall(text or ""))
    rtl_langs = {"ar", "fa", "he"}
    lang = detect_language(text or "")
    return {
        "language": lang["language"],
        "language_confidence": lang["confidence"],
        "detection_method": lang["method"],
        "direction": "rtl" if lang["language"] in rtl_langs else "ltr",
        **classify_document(text or ""),
        "word_count": words,
        "line_count": len((text or "").splitlines()),
    }
