from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.model_loader import ModelLoader


class DummySettings:
    def __init__(self, **kwargs):
        # sane defaults
        self.USE_ONNX_RUNTIME = False
        self.TORCH_DEVICE = "auto"
        self.DISTILBERT_MODEL = "dummy-model"
        self.MODEL_WARM_ON_STARTUP = True
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.asyncio
async def test_model_loader_transformers_cpu(monkeypatch):
    # capture args passed to transformers.pipeline
    calls = {}

    def fake_pipeline(**kwargs):
        # record device argument
        calls["device"] = kwargs.get("device")

        def _runner(text, **_):
            return [{"label": "joy", "score": 0.9}]

        return _runner

    # torch None branch
    monkeypatch.setattr("app.services.model_loader.torch", None)

    # inject settings and transformers.pipeline
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: DummySettings(USE_ONNX_RUNTIME=False, TORCH_DEVICE="auto"),
    )
    monkeypatch.setattr("app.services.model_loader.pipeline", fake_pipeline)

    loader = ModelLoader.instance()
    await loader.clear()
    pipe = await loader.get_emotion_pipeline()
    out = await asyncio.to_thread(pipe, "hello")
    assert out[0]["label"] == "joy" or out[0].get("label") == "joy"
    # device should default to -1 (CPU) when torch is None
    assert calls["device"] == -1


@pytest.mark.asyncio
async def test_model_loader_device_resolution_cuda(monkeypatch):
    # Simulate torch with cuda available
    class TorchMock:
        class cuda:
            @staticmethod
            def is_available():
                return True

    monkeypatch.setattr("app.services.model_loader.torch", TorchMock)

    captured = {}

    def fake_pipeline(**kwargs):
        captured["device"] = kwargs.get("device")

        def _runner(text, **_):
            return [{"label": "joy", "score": 0.9}]

        return _runner

    monkeypatch.setattr("app.core.config.get_settings", lambda: DummySettings(TORCH_DEVICE="cuda"))
    monkeypatch.setattr("app.services.model_loader.pipeline", fake_pipeline)

    loader = ModelLoader.instance()
    await loader.clear()
    _ = await loader.get_emotion_pipeline()
    assert captured["device"] in (0,)  # cuda index


@pytest.mark.asyncio
async def test_model_loader_onnx_path_and_fallback(monkeypatch):
    # Prepare mocks for ONNX success
    class ORTMock:
        @staticmethod
        def from_pretrained(model_name, from_transformers=False):
            return SimpleNamespace(model=model_name, from_transformers=from_transformers)

    class DummyTCP:
        def __init__(self, model=None, tokenizer=None, **_):
            self.model = model
            self.tokenizer = tokenizer

        def __call__(self, text, **_):
            return [{"label": "joy", "score": 0.8}]

    # Success path
    monkeypatch.setattr(
        "app.core.config.get_settings", lambda: DummySettings(USE_ONNX_RUNTIME=True)
    )
    monkeypatch.setattr("app.services.model_loader.ORTModelForSequenceClassification", ORTMock)
    monkeypatch.setattr(
        "app.services.model_loader.AutoTokenizer",
        SimpleNamespace(from_pretrained=lambda m: object()),
    )
    monkeypatch.setattr("app.services.model_loader.TextClassificationPipeline", DummyTCP)

    loader = ModelLoader.instance()
    await loader.clear()
    p1 = await loader.get_emotion_pipeline("onnx-model")
    out1 = await asyncio.to_thread(p1, "hi")
    assert isinstance(out1, list)

    # Fallback path when ONNX raises
    class ORTFail:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            raise RuntimeError("fail")

    captured = {}

    def fake_pipeline(**kwargs):
        captured["device"] = kwargs.get("device")

        def _runner(text, **_):
            return [{"label": "joy", "score": 0.7}]

        return _runner

    monkeypatch.setattr(
        "app.core.config.get_settings", lambda: DummySettings(USE_ONNX_RUNTIME=True)
    )
    monkeypatch.setattr("app.services.model_loader.ORTModelForSequenceClassification", ORTFail)
    monkeypatch.setattr("app.services.model_loader.pipeline", fake_pipeline)

    await loader.clear()
    p2 = await loader.get_emotion_pipeline("transformers-model")
    out2 = await asyncio.to_thread(p2, "hello")
    assert out2[0]["label"] == "joy"


@pytest.mark.asyncio
async def test_model_loader_warmup_and_singleton(monkeypatch):
    # Ensure singleton returns same instance
    assert ModelLoader.instance() is ModelLoader.instance()

    def fake_pipeline(**kwargs):
        def _runner(text, **_):
            return [{"label": "joy", "score": 0.9}]

        return _runner

    monkeypatch.setattr(
        "app.core.config.get_settings", lambda: DummySettings(MODEL_WARM_ON_STARTUP=True)
    )
    monkeypatch.setattr("app.services.model_loader.pipeline", fake_pipeline)

    loader = ModelLoader.instance()
    await loader.clear()
    times = await loader.warm_up(model_ids=["m1", "m2"])
    # Two models warmed
    assert set(times.keys()) == {"m1", "m2"}
    # Subsequent warm up should skip already loaded
    times2 = await loader.warm_up(model_ids=["m1", "m3"])
    assert set(times2.keys()) == {"m3"}
