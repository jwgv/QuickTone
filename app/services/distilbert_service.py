from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Tuple

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    torch = None  # type: ignore

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

    def _is_sst2_model(self) -> bool:
        """Return True if the effective HF model is the SST-2 sentiment model."""
        settings = config.get_settings()
        effective_id = self._model_id or settings.DISTILBERT_MODEL
        return effective_id == settings.DISTILBERT_SST_2_MODEL

    async def _ensure_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        settings = config.get_settings()
        model_id = self._model_id or settings.DISTILBERT_MODEL
        self._pipeline = await self._loader.get_emotion_pipeline(model_id)
        return self._pipeline

    def _postprocess(self, results: List[dict], task_type: TaskType) -> tuple[str, float]:
        # Special handling for SST-2: it is a pure sentiment model (POSITIVE/NEGATIVE).
        if self._is_sst2_model():
            if not results:
                # Fallback to neutral if something is off
                return SentimentLabel.neutral.value, 0.0

            top = max(results, key=lambda x: x.get("score", 0.0))
            raw_label = str(top.get("label", "")).strip()
            score = float(top.get("score", 0.0))
            label_lower = raw_label.lower()

            # Map common SST-2 label variants to sentiment
            if label_lower in {"positive", "pos", "label_1"}:
                sentiment_label = SentimentLabel.positive.value
            elif label_lower in {"negative", "neg", "label_0"}:
                sentiment_label = SentimentLabel.negative.value
            else:
                sentiment_label = SentimentLabel.neutral.value

            if task_type == "sentiment":
                # Return raw sentiment for SST-2
                return sentiment_label, score

            # task_type == "emotion" → synthesize a crude "emotion" from sentiment
            if sentiment_label == SentimentLabel.positive.value:
                return "positivity", score
            if sentiment_label == SentimentLabel.negative.value:
                return "negativity", score
            return "neutrality", score

        # Eehavior for emotion models (GoEmotions, etc.)
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
            def _call_pipe() -> List[dict] | List[List[dict]]:
                if torch is not None:
                    with torch.inference_mode():
                        return pipe(text, truncation=True, top_k=None)
                return pipe(text, truncation=True, top_k=None)

            # offload blocking inference to a thread
            return await asyncio.to_thread(_call_pipe)

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
            def _call_pipe_batch() -> List[List[dict]] | List[dict]:
                if torch is not None:
                    with torch.inference_mode():
                        return pipe(texts, truncation=True, top_k=None)
                return pipe(texts, truncation=True, top_k=None)

            # HF pipelines accept a list of strings and return a list per input
            result = await asyncio.to_thread(_call_pipe_batch)
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
