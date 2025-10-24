from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Dict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.v1.routes_models import router as models_router
from .api.v1.routes_sentiment import router as sentiment_router
from .core.config import get_settings
from .core.logging import configure_logging
from .core.performance import performance_middleware
from .services.model_loader import ModelLoader


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    # Optional warm-up
    if settings.MODEL_WARM_ON_STARTUP:
        try:
            loader = ModelLoader.instance()
            await loader.warm_up(model_ids=[settings.DISTILBERT_SST_2_MODEL])
        except Exception:
            # Warm-up failure should not crash app; graceful degradation will handle at runtime.
            pass
    yield


app = FastAPI(title="QuickTone", version=__version__, lifespan=lifespan)

# Middleware
app.middleware("http")(performance_middleware)

# Routers
app.include_router(sentiment_router)
app.include_router(models_router)

# Static UI
# Try Docker path first, then fall back to local development path
_ui_dist_docker = Path(__file__).resolve().parent.parent / "static" / "ui"
_ui_dist_local = Path(__file__).resolve().parent.parent / "ui" / "dist"

_ui_dist = None
if _ui_dist_docker.exists():
    _ui_dist = _ui_dist_docker
elif _ui_dist_local.exists():
    _ui_dist = _ui_dist_local

if _ui_dist:
    app.mount("/ui", StaticFiles(directory=str(_ui_dist), html=True), name="ui")


@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "QuickTone API — see /docs"}


@app.get("/health")
async def health() -> Dict[str, object]:
    settings = get_settings()
    return {
        "status": "healthy",
        "models_available": [
            "vader",
            "distilbert",
            "distilbert-sst-2",
        ],
        "version": __version__,
        "default_model": settings.MODEL_DEFAULT,
    }


# Convenience for local `python -m app.main`
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("FS_HOST", "0.0.0.0"),
        port=int(os.getenv("FS_PORT", "8080")),
        reload=True,
    )
