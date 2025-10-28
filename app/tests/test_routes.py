from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schema import (
    BatchSentimentRequest,
    BatchSentimentResponse,
    SentimentRequest,
    SentimentResponse,
)

client = TestClient(app)


class DummyResp:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch):
    # Disable rate limiting for route tests
    class DummySettings:
        RATE_LIMIT_ENABLED = False
        TEXT_LENGTH_LIMIT = 10
        BATCH_SIZE_LIMIT = 2
        MODEL_DEFAULT = "vader"
        API_KEYS = ""
        AUTH_MODE = "none"

        def __getattr__(self, item):
            # provide permissive defaults
            return getattr(self, item, None)

    monkeypatch.setattr("app.core.config.get_settings", lambda: DummySettings())


def test_sentiment_route_success(monkeypatch):
    # Patch SentimentManager.analyze to avoid heavy work
    class DummyMgr:
        async def analyze(self, req: SentimentRequest):
            return SentimentResponse(
                model=req.model or "vader",
                sentiment="positive",
                confidence=0.9,
                processing_time_ms=1,
                task_type=req.task_type,
            )

    monkeypatch.setattr("app.api.v1.routes_sentiment._manager", DummyMgr())

    r = client.post("/api/v1/sentiment", json={"text": "ok", "model": "vader"})
    assert r.status_code == 200
    data = r.json()
    assert data["sentiment"] == "positive"


def test_sentiment_route_413_text_too_long():
    r = client.post("/api/v1/sentiment", json={"text": "x" * 50, "model": "vader"})
    assert r.status_code == 413


def test_sentiment_route_batch_success(monkeypatch):
    class DummyMgr:
        async def analyze_batch(self, req: BatchSentimentRequest):
            return BatchSentimentResponse(
                results=[
                    SentimentResponse(
                        model="vader",
                        sentiment="positive",
                        confidence=0.9,
                        processing_time_ms=1,
                        task_type=req.task_type,
                    ),
                    SentimentResponse(
                        model="vader",
                        sentiment="negative",
                        confidence=0.8,
                        processing_time_ms=1,
                        task_type=req.task_type,
                    ),
                ],
                total_processing_time_ms=2,
                items_processed=2,
            )

    monkeypatch.setattr("app.api.v1.routes_sentiment._manager", DummyMgr())

    r = client.post("/api/v1/sentiment/batch", json={"texts": ["a", "b"], "model": "vader"})
    assert r.status_code == 200
    data = r.json()
    assert data["items_processed"] == 2


def test_sentiment_route_batch_413_text_too_long():
    r = client.post("/api/v1/sentiment/batch", json={"texts": ["a" * 11], "model": "vader"})
    assert r.status_code == 413


def test_sentiment_route_batch_413_too_many():
    r = client.post("/api/v1/sentiment/batch", json={"texts": ["a", "b", "c"], "model": "vader"})
    assert r.status_code == 413


def test_models_routes_status_and_clear(monkeypatch):
    # Patch loader instance methods
    class DummyLoader:
        def __init__(self):
            self._pipelines = {"m1": object()}

        async def clear(self):
            self._pipelines.clear()

        async def warm_up(self, model_ids=None):
            return {"id1": 0.01}

    monkeypatch.setattr("app.api.v1.routes_models._loader", DummyLoader())

    r = client.get("/api/v1/models/status")
    assert r.status_code == 200
    assert "loaded_models" in r.json()

    r2 = client.delete("/api/v1/models/clear")
    assert r2.status_code == 200
    assert r2.json()["status"] == "cleared"


def test_models_warm(monkeypatch):
    class DummyLoader:
        async def warm_up(self, model_ids=None):
            assert model_ids is None or isinstance(model_ids, list)
            return {"mX": 0.02}

    monkeypatch.setattr("app.api.v1.routes_models._loader", DummyLoader())
    r = client.post(
        "/api/v1/models/warm", json={"models": ["distilbert", "vader", "distilbert-sst-2"]}
    )
    assert r.status_code == 200
    assert "models_loaded" in r.json()
