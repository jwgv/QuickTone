from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .types import ModelName, TaskType


class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1)
    model: Optional[ModelName] = Field(default=None, description="Override model for this request")
    task_type: TaskType = Field(default="sentiment")
    threshold: Optional[float] = Field(
        default=None, description="Optional threshold override for emotion→sentiment mapping"
    )


class SentimentResponse(BaseModel):
    model: ModelName
    sentiment: str
    confidence: float
    processing_time_ms: int
    task_type: TaskType = "sentiment"
    text: Optional[str] = None


class BatchSentimentRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1)
    model: Optional[ModelName] = None
    task_type: TaskType = "sentiment"
    threshold: Optional[float] = None


class BatchSentimentResponse(BaseModel):
    results: List[SentimentResponse]
    total_processing_time_ms: int
    items_processed: int


class ModelWarmupRequest(BaseModel):
    models: Optional[List[ModelName]] = None


class ModelWarmupResponse(BaseModel):
    models_loaded: List[str]
    warm_up_time_ms: int
