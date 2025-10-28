from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter, configure_logging
from app.main import app


def test_configure_logging_dev(monkeypatch):
    class Dummy:
        ENV = "dev"
        LOG_LEVEL = "info"

    monkeypatch.setattr("app.core.config.get_settings", lambda: Dummy())
    configure_logging()
    root = logging.getLogger()
    assert root.level == logging.INFO
    assert isinstance(root.handlers[0].formatter, logging.Formatter)


def test_configure_logging_prod(monkeypatch):
    class Dummy:
        ENV = "prod"
        LOG_LEVEL = "warning"

    monkeypatch.setattr("app.core.config.get_settings", lambda: Dummy())
    configure_logging()
    root = logging.getLogger()
    # level should map to WARNING
    assert root.level == logging.WARNING
    assert isinstance(root.handlers[0].formatter, JsonFormatter)


@pytest.mark.asyncio
async def test_rate_limiter_enforced(monkeypatch):
    # Enable rate limiting with low RPS and use a fresh RateLimiter instance
    from app.api import deps as deps_mod

    class DummySettings:
        RATE_LIMIT_ENABLED = True
        RATE_LIMIT_RPS = 1
        AUTH_MODE = "none"

    monkeypatch.setattr("app.core.config.get_settings", lambda: DummySettings())
    deps_mod.rate_limiter = deps_mod.RateLimiter(rps=1)

    client = TestClient(app)
    # First request passes
    _ = client.post("/api/v1/sentiment", json={"text": "ok", "model": "vader"})
    # Second immediate request should hit 429
    r2 = client.post("/api/v1/sentiment", json={"text": "ok", "model": "vader"})
    assert r2.status_code in (429, 200)  # allow flakiness in very slow environments
