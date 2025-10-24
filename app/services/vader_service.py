from __future__ import annotations

import time
from typing import Tuple

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..models.types import SentimentBackend, SentimentLabel, TaskType


class VaderService(SentimentBackend):
    name = "vader"

    def __init__(self) -> None:
        self._analyzer = SentimentIntensityAnalyzer()

    async def analyze(self, text: str, task_type: TaskType = "sentiment") -> Tuple[str, float, int]:
        start = time.perf_counter()
        scores = self._analyzer.polarity_scores(text)
        compound = scores["compound"]
        if compound >= 0.05:
            label = SentimentLabel.positive.value
            conf = compound
        elif compound <= -0.05:
            label = SentimentLabel.negative.value
            conf = -compound
        else:
            label = SentimentLabel.neutral.value
            conf = 1.0 - abs(compound)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return label, float(max(0.0, min(conf, 1.0))), elapsed_ms
