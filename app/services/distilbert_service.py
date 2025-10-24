from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Tuple

from ..core.config import get_settings
from ..models.types import SentimentBackend, SentimentLabel, TaskType
from .model_loader import ModelLoader

EMOTION_TO_SENTIMENT: Dict[str, str] = {
    # Positive bucket
    "joy": SentimentLabel.positive.value,
    "optimism": SentimentLabel.positive.value,
    "amusement": SentimentLabel.positive.value,
    "admiration": SentimentLabel.positive.value,
    "love": SentimentLabel.positive.value,
    # Negative bucket
    "anger": SentimentLabel.negative.value,
    "disgust": SentimentLabel.negative.value,
    "fear": SentimentLabel.negative.value,
    "sadness": SentimentLabel.negative.value,
    "disappointment": SentimentLabel.negative.value,
}


class DistilBertService(SentimentBackend):
    name = "distilbert"

    def __init__(self, model_id: str | None = None) -> None:
        self._loader = ModelLoader.instance()
        self._model_id = model_id  # if None, falls back to settings.DISTILBERT_MODEL

    async def analyze(self, text: str, task_type: TaskType = "sentiment") -> Tuple[str, float, int]:
        settings = get_settings()
        start = time.perf_counter()
        model_id = self._model_id or settings.DISTILBERT_MODEL
        pipe = await self._loader.get_emotion_pipeline(model_id)

        async def _run() -> List[dict]:
            res = await asyncio.to_thread(pipe, text, truncation=True, top_k=None)
            # transformers pipeline returns List[dict] or List[List[dict]] depending on config
            if isinstance(res, list) and res and isinstance(res[0], list):
                return res[0]  # unwrap top_k
            return res  # type: ignore[return-value]

        try:
            # enforce timeout on model inference
            results = await asyncio.wait_for(_run(), timeout=settings.RESPONSE_TIMEOUT_MS / 1000.0)
        except asyncio.TimeoutError:
            raise

        # results is list of {label: emotion, score: prob}
        label: str
        conf: float
        if task_type == "emotion":
            top = max(results, key=lambda x: x.get("score", 0.0))
            label = str(top.get("label", "neutral")).lower()
            conf = float(top.get("score", 0.0))
        else:
            # map emotions → sentiment
            pos = sum(
                r["score"]
                for r in results
                if EMOTION_TO_SENTIMENT.get(str(r["label"]).lower()) == "positive"
            )
            neg = sum(
                r["score"]
                for r in results
                if EMOTION_TO_SENTIMENT.get(str(r["label"]).lower()) == "negative"
            )
            thr = settings.EMO_SENT_THRESHOLD
            eps = settings.EMO_SENT_EPSILON
            if max(pos, neg) < thr or abs(pos - neg) <= eps:
                label = SentimentLabel.neutral.value
                conf = max(0.0, thr - abs(pos - neg))
            else:
                if pos > neg:
                    label = SentimentLabel.positive.value
                    conf = float(min(1.0, pos))
                else:
                    label = SentimentLabel.negative.value
                    conf = float(min(1.0, neg))
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return label, conf, elapsed_ms
