"""Prometheus metrics endpoint (v3.5).

Uses prometheus_client when installed; otherwise falls back to a tiny
in-process counter implementation that still renders valid exposition format,
so /metrics never 500s regardless of optional dependencies.
"""
from __future__ import annotations

import threading

try:  # pragma: no cover - depends on optional dep availability
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        generate_latest,
    )

    request_counter = Counter(
        "udo_http_requests_total",
        "Total HTTP requests processed",
        ["method"],
    )

    def metrics_response():
        from fastapi import Response

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

except ImportError:  # minimal fallback

    class _SimpleCounter:
        def __init__(self, name: str, doc: str) -> None:
            self.name = name
            self.doc = doc
            self._values: dict[str, int] = {}
            self._lock = threading.Lock()

        def labels(self, label: str) -> "_Labeled":
            return _Labeled(self, label)

        def inc_label(self, label: str) -> None:
            with self._lock:
                self._values[label] = self._values.get(label, 0) + 1

        def render(self) -> str:
            lines = [f"# HELP {self.name} {self.doc}", f"# TYPE {self.name} counter"]
            for label, value in sorted(self._values.items()):
                lines.append(f'{self.name}{{method="{label}"}} {value}')
            return "\n".join(lines) + "\n"

    class _Labeled:
        def __init__(self, parent: _SimpleCounter, label: str) -> None:
            self._parent = parent
            self._label = label

        def inc(self) -> None:
            self._parent.inc_label(self._label)

    request_counter = _SimpleCounter("udo_http_requests_total", "Total HTTP requests")

    def metrics_response():
        from fastapi import Response

        body = request_counter.render()
        return Response(content=body, media_type="text/plain; version=0.0.4")
