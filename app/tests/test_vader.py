from __future__ import annotations

import pytest

from app.services.vader_service import VaderService


@pytest.mark.asyncio
async def test_vader_positive():
    svc = VaderService()
    label, conf, ms = await svc.analyze("This product is amazing and wonderful!")
    assert label in {"positive", "neutral", "negative"}
    assert conf >= 0.0
    assert isinstance(ms, int)


@pytest.mark.asyncio
async def test_vader_negative():
    svc = VaderService()
    label, conf, ms = await svc.analyze("This is terrible and awful.")
    assert label in {"positive", "neutral", "negative"}
    assert conf >= 0.0
