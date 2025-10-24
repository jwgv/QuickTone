from __future__ import annotations

from enum import Enum
from typing import Literal, Protocol, Tuple

ModelName = Literal["vader", "distilbert", "distilbert-sst-2"]
TaskType = Literal["sentiment", "emotion"]


class SentimentLabel(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class SentimentBackend(Protocol):
    name: ModelName

    async def analyze(self, text: str, task_type: TaskType = "sentiment") -> Tuple[str, float, int]:
        """Analyze text returning (label, score, processing_time_ms).

        For task_type="emotion", label should be an emotion label.
        For task_type="sentiment", label should an SentimentLabel.
        """
        ...
