from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from transformers import AutoTokenizer, TextClassificationPipeline, pipeline

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    torch = None  # type: ignore

try:
    from optimum.onnxruntime import ORTModelForSequenceClassification  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ORTModelForSequenceClassification = None  # type: ignore

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
        # Fast path: avoid locking if already loaded
        pl = self._pipelines.get(model_name)
        if pl is not None:
            return pl
        # Slow path: load under lock (double-checked)
        async with self._lock:
            existing = self._pipelines.get(model_name)
            if existing is not None:
                return existing

            def _load_pipeline() -> Any:
                # Prefer ONNX Runtime if enabled and available; otherwise use standard HF pipeline.
                if settings.USE_ONNX_RUNTIME and ORTModelForSequenceClassification is not None:
                    try:
                        tokenizer = AutoTokenizer.from_pretrained(model_name)
                        # Try to load an existing ONNX model repo; if not, convert from transformers weights.
                        try:
                            ort_model = ORTModelForSequenceClassification.from_pretrained(model_name)  # type: ignore[arg-type]
                        except Exception:
                            ort_model = ORTModelForSequenceClassification.from_pretrained(  # type: ignore[arg-type]
                                model_name,
                                from_transformers=True,
                            )
                        return TextClassificationPipeline(
                            model=ort_model,
                            tokenizer=tokenizer,
                            top_k=None,
                            truncation=True,
                            return_all_scores=True,
                        )
                    except Exception:
                        # Fall back to transformers pipeline below
                        pass

                # Standard transformers pipeline
                # Resolve device according to settings.TORCH_DEVICE
                def _resolve_device() -> object:
                    dev = settings.TORCH_DEVICE.lower()
                    if torch is None:
                        return -1  # CPU
                    if dev == "auto":
                        try:
                            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                                return torch.device("mps")
                        except Exception:
                            pass
                        if torch.cuda.is_available():
                            return 0  # first CUDA device index
                        return -1
                    if dev == "mps":
                        # use MPS if available else CPU
                        try:
                            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                                return torch.device("mps")
                        except Exception:
                            pass
                        return -1
                    if dev == "cuda":
                        return 0 if torch.cuda.is_available() else -1
                    return -1

                device_arg = _resolve_device()
                return pipeline(
                    task="text-classification",
                    model=model_name,
                    top_k=None,
                    truncation=True,
                    device=device_arg,
                )

            # Loading can be blocking; offload to thread to avoid blocking event loop
            pl = await asyncio.to_thread(_load_pipeline)
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
