from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request

from .config import get_settings

logger = logging.getLogger("quicktone.performance")


async def performance_middleware(request: Request, call_next: Callable):  # type: ignore[type-arg]
    settings = get_settings()
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        try:
            response.headers["X-Process-Time-ms"] = str(elapsed_ms)
        except Exception:
            pass
        if settings.PERFORMANCE_LOGGING:
            logger.info(
                "request_completed",
                extra={
                    "extra": {
                        "path": request.url.path,
                        "method": request.method,
                        "elapsed_ms": elapsed_ms,
                    }
                },
            )
