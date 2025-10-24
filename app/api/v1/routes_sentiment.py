from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.config import get_settings
from ...models.schema import (
    BatchSentimentRequest,
    BatchSentimentResponse,
    SentimentRequest,
    SentimentResponse,
)
from ...services.sentiment_manager import SentimentManager
from ..deps import api_key_auth, enforce_limits

router = APIRouter(prefix="/api/v1", tags=["sentiment"])

_manager = SentimentManager()


@router.post("/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(
    req: SentimentRequest,
    _auth: None = Depends(api_key_auth),
    _limits: None = Depends(enforce_limits),
) -> SentimentResponse:
    settings = get_settings()
    if len(req.text) > settings.TEXT_LENGTH_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Text too long"
        )
    return await _manager.analyze(req)


@router.post("/sentiment/batch", response_model=BatchSentimentResponse)
async def analyze_sentiment_batch(
    req: BatchSentimentRequest,
    _auth: None = Depends(api_key_auth),
    _limits: None = Depends(enforce_limits),
) -> BatchSentimentResponse:
    settings = get_settings()
    if len(req.texts) > settings.BATCH_SIZE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Batch too large"
        )
    for t in req.texts:
        if len(t) > settings.TEXT_LENGTH_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Text too long"
            )
    try:
        return await _manager.analyze_batch(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
