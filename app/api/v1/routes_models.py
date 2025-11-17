from __future__ import annotations

import time
from typing import Dict

from fastapi import APIRouter, Depends

from ...core.config import get_settings
from ...models.schema import ModelWarmupRequest, ModelWarmupResponse
from ...services.model_loader import ModelLoader
from ..deps import admin_key_auth, api_key_auth, enforce_limits

router = APIRouter(prefix="/api/v1/models", tags=["models"])

_loader = ModelLoader.instance()


@router.post("/warm", response_model=ModelWarmupResponse)
async def warm_models(
    req: ModelWarmupRequest | None = None,
    _auth: None = Depends(api_key_auth),
    _limits: None = Depends(enforce_limits),
) -> ModelWarmupResponse:
    start = time.perf_counter()
    # Determine which HF model IDs to warm based on requested logical model names
    settings = get_settings()
    model_ids: list[str] = []
    if req and req.models:
        for m in req.models:
            m_l = m.lower()
            if m_l == "vader":
                continue  # nothing to warm for vader
            elif m_l == "distilbert":
                model_ids.append(settings.DISTILBERT_MODEL)
            elif m_l == "distilbert-sst-2":
                model_ids.append(settings.DISTILBERT_SST_2_MODEL)
    # If none specified, warm default distilbert
    times = await _loader.warm_up(model_ids if model_ids else None)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return ModelWarmupResponse(models_loaded=list(times.keys()), warm_up_time_ms=elapsed_ms)


@router.get("/status")
async def model_status(
    _auth: None = Depends(api_key_auth),
    _limits: None = Depends(enforce_limits),
) -> Dict[str, object]:
    settings = get_settings()
    # We don't track memory per model precisely without heavy deps; provide simple status
    loaded = list(getattr(_loader, "_pipelines", {}).keys())
    return {
        "loaded_models": loaded,
        "memory_usage_mb": None,
        "uptime_seconds": None,
        "default_model": settings.MODEL_DEFAULT,
    }


@router.delete("/clear")
async def clear_models(
    _admin: None = Depends(admin_key_auth),
) -> Dict[str, str]:
    await _loader.clear()
    return {"status": "cleared"}
