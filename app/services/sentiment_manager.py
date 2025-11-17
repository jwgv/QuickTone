from __future__ import annotations

import asyncio
import time
from typing import List, Optional

from ..core.config import get_settings
from ..models.schema import (
    BatchSentimentRequest,
    BatchSentimentResponse,
    SentimentRequest,
    SentimentResponse,
)
from ..models.types import ModelName, TaskType
from .cache import MemoryCache
from .distilbert_service import DistilBertService
from .vader_service import VaderService


class SentimentManager:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._vader = VaderService()
        self._distilbert = DistilBertService()
        # DistilBERT SST-2 variant
        self._distilbert_sst2 = DistilBertService(model_id=self._settings.DISTILBERT_SST_2_MODEL)
        self._cache = (
            MemoryCache[str, SentimentResponse](
                max_size=2048, ttl_seconds=self._settings.CACHE_TTL_SECONDS
            )
            if self._settings.CACHE_BACKEND == "memory"
            else None
        )
        self._batch_cache = (
            MemoryCache[str, BatchSentimentResponse](
                max_size=256, ttl_seconds=self._settings.CACHE_TTL_SECONDS
            )
            if self._settings.CACHE_BACKEND == "memory"
            else None
        )

    def _select_backend(self, model: Optional[ModelName]) -> str:
        return (model or self._settings.MODEL_DEFAULT).lower()

    async def analyze(self, req: SentimentRequest) -> SentimentResponse:
        model_choice = self._select_backend(req.model)
        text = req.text
        task_type: TaskType = req.task_type

        if self._cache:
            key = self._cache.hash_text(model_choice, task_type, text, req.threshold)
            hit = self._cache.get(key)
            if hit:
                return hit

        try:
            resp = await self._analyze_with_model(model_choice, text, task_type)
        except Exception:
            if self._settings.GRACEFUL_DEGRADATION and model_choice != "vader":
                # fallback to vader
                label, conf, elapsed = await self._vader.analyze(text, task_type="sentiment")
                resp = SentimentResponse(
                    model="vader",
                    sentiment=label,
                    confidence=conf,
                    processing_time_ms=elapsed,
                    task_type="sentiment",
                )
            else:
                raise

        if self._cache:
            self._cache.set(key, resp)  # type: ignore[arg-type]
        return resp

    async def _analyze_with_model(
        self, model_choice: str, text: str, task_type: TaskType
    ) -> SentimentResponse:
        # start_total = time.perf_counter()
        if model_choice == "vader":
            label, conf, elapsed = await self._vader.analyze(text, task_type="sentiment")
            return SentimentResponse(
                model="vader",
                sentiment=label,
                confidence=conf,
                processing_time_ms=elapsed,
                task_type="sentiment",
            )
        elif model_choice == "distilbert":
            label, conf, elapsed = await self._distilbert.analyze(text, task_type=task_type)
            return SentimentResponse(
                model="distilbert",
                sentiment=label,
                confidence=conf,
                processing_time_ms=elapsed,
                task_type=task_type,
            )
        elif model_choice == "distilbert-sst-2":
            label, conf, elapsed = await self._distilbert_sst2.analyze(text, task_type=task_type)
            return SentimentResponse(
                model="distilbert-sst-2",
                sentiment=label,
                confidence=conf,
                processing_time_ms=elapsed,
                task_type=task_type,
            )
        else:
            raise ValueError(f"Unknown model: {model_choice}")

    async def analyze_batch(self, req: BatchSentimentRequest) -> BatchSentimentResponse:
        texts = req.texts
        if len(texts) > self._settings.BATCH_SIZE_LIMIT:
            raise ValueError(
                f"Batch size {len(texts)} exceeds limit {self._settings.BATCH_SIZE_LIMIT}."
            )
        # Enforce text size limit on each item
        for t in texts:
            if len(t) > self._settings.TEXT_LENGTH_LIMIT:
                raise ValueError("Text too long")

        # Batch-level cache check (captures total_processing_time_ms as well)
        model_choice = self._select_backend(req.model)
        task_type: TaskType = req.task_type
        cache_key: Optional[str] = None
        if self._batch_cache:
            cache_key = self._batch_cache.hash_texts(model_choice, task_type, texts, req.threshold)
            cached = self._batch_cache.get(cache_key)
            if cached:
                return cached

        model_choice = model_choice.lower()
        # Use optimized HF batch pipeline for DistilBERT variants; VADER remains per-item.
        if model_choice in {"distilbert", "distilbert-sst-2"}:
            # Route to the appropriate DistilBERT service once for all texts
            svc = self._distilbert if model_choice == "distilbert" else self._distilbert_sst2
            labels_confs, total_ms = await svc.analyze_batch(texts, task_type=task_type)
            # Build responses; assign per-item processing time as total batch time divided equally
            per_item_ms = max(1, int(total_ms / max(1, len(labels_confs))))
            results: List[SentimentResponse] = [
                SentimentResponse(
                    model=model_choice,
                    sentiment=label,
                    confidence=conf,
                    processing_time_ms=per_item_ms,
                    task_type=task_type,
                )
                for (label, conf) in labels_confs
            ]
            resp = BatchSentimentResponse(
                results=results, total_processing_time_ms=total_ms, items_processed=len(results)
            )
            if self._batch_cache and cache_key is not None:
                self._batch_cache.set(cache_key, resp)
            return resp
        # Fallback: per-item async analysis (e.g., VADER)
        start = time.perf_counter()
        sem = asyncio.Semaphore(8)

        async def _one(t: str) -> SentimentResponse:
            async with sem:
                return await self.analyze(
                    SentimentRequest(
                        text=t, model=req.model, task_type=req.task_type, threshold=req.threshold
                    )
                )

        results: List[SentimentResponse] = await asyncio.gather(*[_one(t) for t in texts])
        total_ms = int((time.perf_counter() - start) * 1000)
        resp = BatchSentimentResponse(
            results=results, total_processing_time_ms=total_ms, items_processed=len(results)
        )
        if self._batch_cache and cache_key is not None:
            self._batch_cache.set(cache_key, resp)
        return resp
