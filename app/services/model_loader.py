from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from transformers import pipeline

from ..core.config import get_settings


class ModelLoader:
    """Singleton-like loader for ML pipelines to avoid repeated downloads/initialization."""

    _instance: Optional["ModelLoader"] = None

    def __init__(self) -> None:
        self._pipelines: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "ModelLoader":
        if cls._instance is None:
            cls._instance = ModelLoader()
        return cls._instance

    async def get_emotion_pipeline(self, model_id: Optional[str] = None) -> Any:
        settings = get_settings()
        model_name = model_id or settings.DISTILBERT_MODEL
        async with self._lock:
            if model_name in self._pipelines:
                return self._pipelines[model_name]
            # Loading can be blocking; offload to thread
            pl = await asyncio.to_thread(
                pipeline,
                task="text-classification",
                model=model_name,
                top_k=None,
                truncation=True,
            )
            self._pipelines[model_name] = pl
            return pl

    async def warm_up(self, model_ids: Optional[list[str]] = None) -> Dict[str, float]:
        """Warm up configured models if enabled, returning load times in seconds.

        If model_ids is provided, warm exactly those HF model IDs; otherwise warm the default.
        """
        settings = get_settings()
        times: Dict[str, float] = {}
        if settings.MODEL_WARM_ON_STARTUP:
            ids = model_ids or [settings.DISTILBERT_MODEL]
            for mid in ids:
                if mid in self._pipelines:
                    continue
                start = time.perf_counter()
                _ = await self.get_emotion_pipeline(mid)
                times[mid] = time.perf_counter() - start
        return times

    async def clear(self) -> None:
        async with self._lock:
            self._pipelines.clear()
