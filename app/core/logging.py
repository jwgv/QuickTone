from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict

from . import config as config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    settings = config.get_settings()
    root = logging.getLogger()
    root.handlers.clear()
    # Map LOG_LEVEL robustly
    level_name = (settings.LOG_LEVEL or "INFO").upper()
    level = logging._nameToLevel.get(level_name, logging.INFO)  # type: ignore[attr-defined]
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    if settings.ENV == "prod":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))

    root.addHandler(handler)

    # Quiet some noisy loggers in dev
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
