from __future__ import annotations

from typing import Optional, Tuple

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api import deps


def make_request(
    method: str = "GET",
    headers: Optional[list[tuple[bytes, bytes]]] = None,
    client: Optional[Tuple[str, int]] = ("127.0.0.1", 12345),
) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers or [],
        "client": client,
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


class DummySettings:
    # Defaults are permissive and can be overridden per-test by attribute set
    AUTH_MODE = "none"
    API_KEYS = ""
    ADMIN_API_KEY = ""
    RATE_LIMIT_ENABLED = False
    RATE_LIMIT_RPS = 1

    # Constraints used elsewhere in the app but harmless here
    TEXT_LENGTH_LIMIT = 100
    BATCH_SIZE_LIMIT = 10

    @property
    def api_key_set(self) -> set[str]:
        if not self.API_KEYS:
            return set()
        return {k.strip() for k in self.API_KEYS.split(",") if k.strip()}


def test_get_api_key_header_and_auth_variants():
    # Direct X-API-Key header
    r1 = make_request(headers=[(b"x-api-key", b"abc123")])
    assert deps.get_api_key(r1) == "abc123"

    # Authorization: Api-Key <key> (case-insensitive scheme)
    r2 = make_request(headers=[(b"authorization", b"Api-Key secret")])
    assert deps.get_api_key(r2) == "secret"

    # Missing
    r3 = make_request(headers=[])
    assert deps.get_api_key(r3) is None


@pytest.mark.asyncio
async def test_admin_key_auth_bypass_when_unconfigured(monkeypatch):
    s = DummySettings()
    s.ADMIN_API_KEY = ""  # not configured
    monkeypatch.setattr("app.api.deps.get_settings", lambda: s)

    # Should not raise even without any key
    await deps.admin_key_auth(api_key=None, request=make_request())


@pytest.mark.asyncio
async def test_admin_key_auth_requires_valid_key(monkeypatch):
    s = DummySettings()
    s.ADMIN_API_KEY = "MASTER"
    monkeypatch.setattr("app.api.deps.get_settings", lambda: s)

    # Wrong key -> 401
    with pytest.raises(HTTPException) as ei:
        await deps.admin_key_auth(api_key="WRONG", request=make_request())
    assert ei.value.status_code == 401

    # Correct via Security scheme arg
    await deps.admin_key_auth(api_key="MASTER", request=make_request())

    # Correct via header fallback
    req = make_request(headers=[(b"x-api-key", b"MASTER")])
    await deps.admin_key_auth(api_key=None, request=req)


@pytest.mark.asyncio
async def test_api_key_auth_modes_and_keys(monkeypatch):
    s = DummySettings()
    s.AUTH_MODE = "none"
    monkeypatch.setattr("app.api.deps.get_settings", lambda: s)

    # AUTH_MODE none -> always allowed
    await deps.api_key_auth(api_key=None, request=make_request())

    # Switch to api_key mode with configured keys
    s.AUTH_MODE = "api_key"
    s.API_KEYS = "k1,k2"
    s.ADMIN_API_KEY = "MASTER"

    # Anonymous allowed (returns None)
    await deps.api_key_auth(api_key=None, request=make_request())

    # Valid regular key
    await deps.api_key_auth(api_key="k1", request=make_request())

    # Admin key treated as valid here as well
    await deps.api_key_auth(api_key="MASTER", request=make_request())


def test_rate_limiter_basic_allow_then_block(monkeypatch):
    # Enable rate limiting, rps=1 to make behavior deterministic
    s = DummySettings()
    s.RATE_LIMIT_ENABLED = True
    s.RATE_LIMIT_RPS = 1
    monkeypatch.setattr("app.api.deps.get_settings", lambda: s)

    rl = deps.RateLimiter(rps=1)
    req = make_request(client=("1.2.3.4", 1111))

    # First should pass
    rl.check(req)

    # Second immediate should raise 429
    with pytest.raises(HTTPException) as ei:
        rl.check(req)
    assert ei.value.status_code == 429
    assert "Retry-After" in (ei.value.headers or {})


def test_enforce_limits_paths(monkeypatch):
    s = DummySettings()
    s.AUTH_MODE = "api_key"
    s.RATE_LIMIT_ENABLED = True
    s.API_KEYS = "k1,k2"
    s.ADMIN_API_KEY = "MASTER"
    monkeypatch.setattr("app.api.deps.get_settings", lambda: s)

    # Master key bypasses any rate limiting
    req_master = make_request(headers=[(b"x-api-key", b"MASTER")])
    deps.enforce_limits(req_master)  # should not raise

    # Regular valid API key bypasses limiter in enforce_limits
    req_k1 = make_request(headers=[(b"x-api-key", b"k1")])
    deps.enforce_limits(req_k1)

    # Anonymous or unknown key should call limiter.check; simulate 429 from limiter
    called = {"count": 0}

    def fake_check(request: Request):
        called["count"] += 1
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "1"}
        )

    monkeypatch.setattr("app.api.deps.rate_limiter", deps.RateLimiter(rps=1))
    monkeypatch.setattr(
        "app.api.deps.rate_limiter", type("RL", (), {"check": staticmethod(fake_check)})()
    )

    with pytest.raises(HTTPException) as ei:
        deps.enforce_limits(make_request())  # no key -> limited
    assert ei.value.status_code == 429
    assert called["count"] == 1
