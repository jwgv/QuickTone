from __future__ import annotations

import time
from typing import Optional

from fastapi import HTTPException, Request, status

from ..core.config import get_settings


def get_api_key(request: Request) -> Optional[str]:
    # Header: X-API-Key or Authorization: Api-Key <key>
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("api-key "):
            api_key = auth.split(" ", 1)[1].strip()
    return api_key or None


def api_key_auth(request: Request) -> None:
    settings = get_settings()
    if settings.AUTH_MODE != "api_key":
        return
    key = get_api_key(request)
    if not key or key not in settings.api_key_set:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key"
        )


class RateLimiter:
    def __init__(self, rps: int) -> None:
        self.rps = rps
        self.allowance: dict[str, tuple[float, float]] = {}

    def _bucket_id(self, request: Request) -> str:
        key = get_api_key(request) or request.client.host if request.client else "anon"
        return key

    def check(self, request: Request) -> None:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED:
            return
        now = time.time()
        bucket = self._bucket_id(request)
        tokens, last = self.allowance.get(bucket, (self.rps, now))
        # Refill tokens
        tokens = min(self.rps, tokens + (now - last) * self.rps)
        if tokens < 1.0:
            retry_after = max(1, int(1.0 - tokens))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        tokens -= 1.0
        self.allowance[bucket] = (tokens, now)


rate_limiter = RateLimiter(rps=get_settings().RATE_LIMIT_RPS)


def enforce_limits(request: Request) -> None:
    settings = get_settings()
    if request.method == "POST":
        # We'll do body size checks at schema level; basic header-based guard here is skipped.
        pass
    if settings.RATE_LIMIT_ENABLED:
        rate_limiter.check(request)
