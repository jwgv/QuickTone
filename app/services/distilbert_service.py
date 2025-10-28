from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Tuple

from ..core import config as config
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
        self._pipeline: Any | None = None

    async def _ensure_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        settings = config.get_settings()
        model_id = self._model_id or settings.DISTILBERT_MODEL
        self._pipeline = await self._loader.get_emotion_pipeline(model_id)
        return self._pipeline

    def _postprocess(self, results: List[dict], task_type: TaskType) -> tuple[str, float]:
        # results is list of {label: emotion, score: prob}
        if task_type == "emotion":
            top = max(results, key=lambda x: x.get("score", 0.0))
            return str(top.get("label", "neutral")).lower(), float(top.get("score", 0.0))
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
        settings = config.get_settings()
        thr = settings.EMO_SENT_THRESHOLD
        eps = settings.EMO_SENT_EPSILON
        if max(pos, neg) < thr or abs(pos - neg) <= eps:
            return SentimentLabel.neutral.value, max(0.0, thr - abs(pos - neg))
        if pos > neg:
            return SentimentLabel.positive.value, float(min(1.0, pos))
        return SentimentLabel.negative.value, float(min(1.0, neg))

    async def analyze(self, text: str, task_type: TaskType = "sentiment") -> Tuple[str, float, int]:
        settings = config.get_settings()
        start = time.perf_counter()
        pipe = await self._ensure_pipeline()

        async def _run() -> List[dict] | List[List[dict]]:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: pipe(text, truncation=True, top_k=None))

        # Guard extremely small timeouts to avoid hanging event loops in some environments
        if settings.RESPONSE_TIMEOUT_MS < 20:
            raise asyncio.TimeoutError
        try:
            res = await asyncio.wait_for(_run(), timeout=settings.RESPONSE_TIMEOUT_MS / 1000.0)
        except asyncio.TimeoutError:
            raise

        # Normalize results to List[dict]
        if isinstance(res, dict):
            results: List[dict] = [res]
        elif isinstance(res, list):
            if res and isinstance(res[0], list):
                results = res[0]  # type: ignore[assignment]
            elif res and isinstance(res[0], dict):
                results = res  # type: ignore[assignment]
            else:
                results = []
        else:
            results = []

        label, conf = self._postprocess(results, task_type)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return label, conf, elapsed_ms

    async def analyze_batch(
        self, texts: List[str], task_type: TaskType = "sentiment"
    ) -> Tuple[List[Tuple[str, float]], int]:
        """Run the HF pipeline once over the whole list to leverage internal batching.

        Returns a tuple of ([(label, confidence) per item], total_elapsed_ms).
        """
        if not texts:
            return [], 0
        settings = config.get_settings()
        start = time.perf_counter()
        pipe = await self._ensure_pipeline()

        async def _run_batch() -> List[List[dict]]:
            # HF pipelines accept a list of strings and return a list per input
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: pipe(texts, truncation=True, top_k=None)
            )
            # Normalize to List[List[dict]]
            if isinstance(result, list) and result and isinstance(result[0], dict):
                # Some pipelines may return list[dict] for single input; ensure nested
                return [result]  # type: ignore[list-item]
            return result  # type: ignore[return-value]

        if settings.RESPONSE_TIMEOUT_MS < 20:
            raise asyncio.TimeoutError
        res = await asyncio.wait_for(_run_batch(), timeout=settings.RESPONSE_TIMEOUT_MS / 1000.0)
        labels_confs: List[Tuple[str, float]] = []
        for item in res:
            label, conf = self._postprocess(item, task_type)
            labels_confs.append((label, conf))
        total_ms = int((time.perf_counter() - start) * 1000)
        return labels_confs, total_ms
