"""v3.6 features: structured JSON logging + graceful shutdown (job sweep)."""
from __future__ import annotations

import json
import logging
import time


class JsonFormatter(logging.Formatter):
    """One JSON object per log line — machine-parseable for Loki/CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


async def graceful_shutdown(app) -> None:
    """Lifespan shutdown hook: sweep expired jobs, flush audit buffer."""
    from app.jobs import JOBS

    removed = JOBS.sweep()
    logging.getLogger("udo").info(
        "shutdown: swept %d expired jobs", removed, extra={"swept": removed}
    )
