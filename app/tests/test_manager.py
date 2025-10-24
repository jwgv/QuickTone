from __future__ import annotations

import pytest

from app.models.schema import BatchSentimentRequest, SentimentRequest
from app.services.sentiment_manager import SentimentManager


@pytest.mark.asyncio
async def test_manager_single_vader():
    mgr = SentimentManager()
    res = await mgr.analyze(SentimentRequest(text="Great work!", model="vader"))
    assert res.model == "vader"
    assert res.sentiment in {"positive", "neutral", "negative"}


@pytest.mark.asyncio
async def test_manager_batch_vader():
    mgr = SentimentManager()
    res = await mgr.analyze_batch(
        BatchSentimentRequest(texts=["I love it", "This is bad"], model="vader")
    )
    assert res.items_processed == 2
    assert len(res.results) == 2
