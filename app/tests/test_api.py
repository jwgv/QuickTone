from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {"healthy", "degraded"}
    assert "models_available" in data


def test_sentiment_vader():
    payload = {"text": "I love this!", "model": "vader"}
    r = client.post("/api/v1/sentiment", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["model"] == "vader"
    assert data["sentiment"] in {"positive", "neutral", "negative"}
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["processing_time_ms"], int)
