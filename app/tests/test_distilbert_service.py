from __future__ import annotations

import asyncio
import time
from typing import List

import pytest

from app.services.distilbert_service import DistilBertService


class DummySettings:
    def __init__(self, **kwargs):
        self.RESPONSE_TIMEOUT_MS = 200
        self.EMO_SENT_THRESHOLD = 0.35
        self.EMO_SENT_EPSILON = 0.05
        self.DISTILBERT_MODEL = "dummy-model"
        for k, v in kwargs.items():
            setattr(self, k, v)


def make_pipeline(responses: List[List[dict]]):
    # returns a callable that yields responses sequentially each call
    idx = {"i": 0}

    def _runner(inp, **_):
        i = idx["i"]
        idx["i"] += 1
        if isinstance(inp, list):
            # batch: return list per item
            return responses[min(i, len(responses) - 1)]
        return responses[min(i, len(responses) - 1)][0]

    return _runner


@pytest.mark.asyncio
async def test_distilbert_analyze_sentiment_positive_negative_neutral(monkeypatch):
    # Sequence of responses: positive, negative, neutral (pos ~ neg or below threshold)
    resp_pos = [[{"label": "joy", "score": 0.8}, {"label": "anger", "score": 0.2}]]
    resp_neg = [[{"label": "anger", "score": 0.7}, {"label": "joy", "score": 0.1}]]
    # For neutral: both low and close
    resp_neu = [[{"label": "joy", "score": 0.2}, {"label": "anger", "score": 0.21}]]

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: DummySettings(EMO_SENT_THRESHOLD=0.35, EMO_SENT_EPSILON=0.05),
    )

    # Patch ModelLoader.instance().get_emotion_pipeline to return our runner
    class DummyLoader:
        async def get_emotion_pipeline(self, *_args, **_kwargs):
            return make_pipeline([resp_pos, resp_neg, resp_neu])

    monkeypatch.setattr(
        "app.services.distilbert_service.ModelLoader",
        type("ML", (), {"instance": staticmethod(lambda: DummyLoader())}),
    )

    svc = DistilBertService()
    label1, conf1, ms1 = await svc.analyze("great", task_type="sentiment")
    assert label1 == "positive" and 0 <= conf1 <= 1 and isinstance(ms1, int)

    label2, conf2, _ = await svc.analyze("bad", task_type="sentiment")
    assert label2 == "negative" and 0 <= conf2 <= 1

    label3, conf3, _ = await svc.analyze("meh", task_type="sentiment")
    assert label3 == "neutral" and 0 <= conf3 <= 1


@pytest.mark.asyncio
async def test_distilbert_analyze_task_type_emotion(monkeypatch):
    resp = [[{"label": "Love", "score": 0.99}, {"label": "joy", "score": 0.5}]]

    monkeypatch.setattr("app.core.config.get_settings", lambda: DummySettings())

    class DummyLoader:
        async def get_emotion_pipeline(self, *_a, **_k):
            return make_pipeline([resp])

    monkeypatch.setattr(
        "app.services.distilbert_service.ModelLoader",
        type("ML", (), {"instance": staticmethod(lambda: DummyLoader())}),
    )

    svc = DistilBertService()
    label, conf, _ = await svc.analyze("x", task_type="emotion")
    assert label == "love" and abs(conf - 0.99) < 1e-6


@pytest.mark.asyncio
async def test_distilbert_analyze_batch(monkeypatch):
    # Two inputs -> two result lists
    resp_batch = [
        [{"label": "joy", "score": 0.8}],
        [{"label": "anger", "score": 0.7}],
    ]

    monkeypatch.setattr("app.core.config.get_settings", lambda: DummySettings())

    class DummyLoader:
        async def get_emotion_pipeline(self, *_a, **_k):
            def _runner(inp, **_):
                assert isinstance(inp, list)
                return resp_batch

            return _runner

    monkeypatch.setattr(
        "app.services.distilbert_service.ModelLoader",
        type("ML", (), {"instance": staticmethod(lambda: DummyLoader())}),
    )

    svc = DistilBertService()
    items, total_ms = await svc.analyze_batch(["a", "b"], task_type="sentiment")
    assert items == [("positive", 0.8), ("negative", 0.7)]
    assert isinstance(total_ms, int) and total_ms >= 0


@pytest.mark.asyncio
async def test_distilbert_timeout(monkeypatch):
    # Set very small timeout and make to_thread sleep beyond it
    monkeypatch.setattr(
        "app.core.config.get_settings", lambda: DummySettings(RESPONSE_TIMEOUT_MS=10)
    )

    async def slow_to_thread(func, *args, **kwargs):
        time.sleep(0.05)  # block longer than timeout
        return func(*args, **kwargs)

    monkeypatch.setattr("app.services.distilbert_service.asyncio.to_thread", slow_to_thread)

    class DummyLoader:
        async def get_emotion_pipeline(self, *_a, **_k):
            def _runner(text, **_):
                return [[{"label": "joy", "score": 0.9}]]

            return _runner

    monkeypatch.setattr(
        "app.services.distilbert_service.ModelLoader",
        type("ML", (), {"instance": staticmethod(lambda: DummyLoader())}),
    )

    svc = DistilBertService()
    with pytest.raises(asyncio.TimeoutError):
        await svc.analyze("x")
