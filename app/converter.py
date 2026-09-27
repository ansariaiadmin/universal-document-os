"""v4.2 conversion engine — real format-to-format output (no fabricated files).

Design rules:
- Every converter is honest: if a library is missing, raise ConversionError
  with the reason instead of writing a broken file.
- Output naming is deterministic and traversal-safe: {stem}__{to}.{ext}.
"""
from __future__ import annotations

import pathlib
import re


class ConversionError(Exception):
    """Raised when a conversion cannot be performed (unsupported pair or
    missing dependency). Carries a machine-readable code."""

    def __init__(self, message: str, code: str = "unsupported_pair"):
        self.code = code
        super().__init__(message)


_EXT_FOR = {"md": ".md", "txt": ".txt", "html": ".html"}

# Progressive enhancement: enable every extension the installed markdown lib
# supports — tables & fenced code on 3.6+, sane lists/toc wherever available.
_ALL_EXT = ["tables", "fenced_code", "toc", "sane_lists", "attr_list", "def_list"]


def _supported_extensions() -> list[str]:
    try:
        from markdown.extensions import build_extension
    except ImportError:  # very old markdown
        return ["tables", "fenced_code"]
    out = []
    for name in _ALL_EXT:
        try:
            if build_extension(name) is not None:
                out.append(name)
        except Exception:
            continue
    return out


_EXTENSIONS = _supported_extensions()


def _strip_front_matter(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)


def md_to_html(text: str) -> str:
    try:
        import markdown
    except ImportError as e:  # pragma: no cover
        raise ConversionError("markdown library not installed", "missing_dep") from e
    body = markdown.markdown(_strip_front_matter(text), extensions=_EXTENSIONS)
    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset='utf-8'>\n"
        "<title>Converted Document</title>\n"
        "<style>body{font-family:-apple-system,Segoe UI,sans-serif;max-width:52em;"
        "margin:2em auto;padding:0 1em;line-height:1.6}pre{background:#1e1e1e;"
        "color:#d4d4d4;padding:1em;overflow-x:auto;border-radius:6px}"
        "code{background:#f0f0f0;padding:.1em .3em;border-radius:3px}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.4em .8em}</style>\n"
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )


def convert(src_text: str, *, to: str, src_path: pathlib.Path | None = None) -> str:
    """Convert extracted document text into the target representation.

    Supported pairs (v4.2):
      any-extracted-text -> txt   (identity)
      any-extracted-text -> md    (plain markdown wrap)
      md / txt / html    -> html  (real markdown rendering w/ tables+code)
    Raises ConversionError for unknown targets.
    """
    to = to.lower().strip()
    if to in {"txt", "md"}:
        return src_text
    if to == "html":
        return md_to_html(src_text)
    raise ConversionError(f"conversion target '{to}' not supported", "unsupported_pair")


def can_convert(fmt: str, to: str) -> bool:
    """Adaptive gate used by the API: does this (format, target) pair work?"""
    to = to.lower().strip()
    fmt = fmt.upper()
    if to in {"same", ""}:
        return True
    if to not in {"txt", "md", "html"}:
        return False
    # Binary office formats currently yield extracted text only — that is a
    # legitimate TXT/MD export; HTML rendering is reserved for markup sources.
    if to == "html" and fmt not in {"MARKDOWN", "MD", "HTML", "TXT"}:
        return False
    return True
