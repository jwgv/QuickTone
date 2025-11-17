from __future__ import annotations

import time
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from ..core.config import get_settings

# Define the API key header for docs + OpenAPI
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


def get_api_key(request: Request) -> Optional[str]:
    # Header: X-API-Key or Authorization: Api-Key <key>
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("api-key "):
            api_key = auth.split(" ", 1)[1].strip()
    return api_key or None


async def admin_key_auth(
    # Hook into the same security scheme used for Swagger's Authorize button
    api_key: Optional[str] = Security(api_key_header),
    request: Request = None,
) -> None:
    """
    Require the special admin/master key for sensitive operations when configured.
    """
    settings = get_settings()
    master_key = getattr(settings, "ADMIN_API_KEY", "") or ""

    # If not configured, do NOT enforce admin auth (useful for tests/dev)
    if not master_key:
        return

    # Prefer the key from the security scheme (Swagger UI), but allow fallback
    key = api_key or get_api_key(request)

    if key != master_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin key",
        )


async def api_key_auth(
    # This creates a security scheme in OpenAPI and the “Authorize” box
    api_key: Optional[str] = Security(api_key_header),
    request: Request = None,
) -> None:
    settings = get_settings()
    if settings.AUTH_MODE != "api_key":
        # Auth disabled: allow everything
        return

    # Prefer the key from the security scheme (Swagger UI / client),
    # but fall back to header parsing for flexibility.
    key = api_key or get_api_key(request)

    # Allow anonymous access; rate limiting enforces “anonymous vs keyed”.
    if not key:
        return

    # Treat both regular API keys and the admin key as “valid” here.
    admin_key = getattr(settings, "ADMIN_API_KEY", "") or ""
    if key in settings.api_key_set or (admin_key and key == admin_key):
        return

    # Optional: for invalid explicit keys to error, uncomment:
    # raise HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Invalid API key",
    # )

    # For now, just allow; rate limiting will still apply for non-whitelisted keys.
    return


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

    if settings.RATE_LIMIT_ENABLED and settings.AUTH_MODE == "api_key":
        key = get_api_key(request)
        master_key = getattr(settings, "ADMIN_API_KEY", "") or ""

        # Master key: no rate limiting at all
        if master_key and key == master_key:
            return

        # Anonymous or non-master key that isn't in the normal key set gets rate limited
        if not key or key not in settings.api_key_set:
            rate_limiter.check(request)
