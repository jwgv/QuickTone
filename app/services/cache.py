from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import blake2b
from typing import Generic, Iterable, MutableMapping, Optional, Tuple, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0


class MemoryCache(Generic[K, V]):
    def __init__(self, max_size: int = 1024, ttl_seconds: Optional[int] = None) -> None:
        self.max_size = max_size
        self.ttl = ttl_seconds if ttl_seconds and ttl_seconds > 0 else None
        self._store: MutableMapping[K, Tuple[float, V]] = OrderedDict()
        self.stats = CacheStats()

    def _evict_if_needed(self) -> None:
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)

    def get(self, key: K) -> Optional[V]:
        now = time.time()
        item = self._store.get(key)
        if not item:
            self.stats.misses += 1
            return None
        ts, value = item
        if self.ttl and now - ts > self.ttl:
            # expired
            self._store.pop(key, None)
            self.stats.misses += 1
            return None
        # refresh LRU
        self._store.pop(key)
        self._store[key] = (ts, value)
        self.stats.hits += 1
        return value

    def set(self, key: K, value: V) -> None:
        ts = time.time()
        if key in self._store:
            self._store.pop(key)
        self._store[key] = (ts, value)
        self._evict_if_needed()

    @staticmethod
    def hash_text(model: str, task_type: str, text: str, threshold: Optional[float] = None) -> str:
        h = blake2b(digest_size=16)
        h.update(model.encode())
        h.update(b"|")
        h.update(task_type.encode())
        h.update(b"|")
        # include threshold to differentiate cache entries when overridden by user
        thr_str = "none" if threshold is None else f"{threshold:.10g}"
        h.update(f"thr={thr_str}".encode())
        h.update(b"|")
        h.update(text.encode())
        return h.hexdigest()

    @staticmethod
    def hash_texts(
        model: str, task_type: str, texts: Iterable[str], threshold: Optional[float] = None
    ) -> str:
        """Stable hash for an ordered list of texts for a given model and task_type.

        Includes threshold so cache entries vary when user adjusts it.
        """
        h = blake2b(digest_size=16)
        h.update(model.encode())
        h.update(b"|")
        h.update(task_type.encode())
        h.update(b"|")
        thr_str = "none" if threshold is None else f"{threshold:.10g}"
        h.update(f"thr={thr_str}".encode())
        h.update(b"|")
        # include length to avoid ambiguity and iterate deterministically
        count = 0
        for t in texts:
            count += 1
            h.update(str(len(t)).encode())
            h.update(b":")
            h.update(t.encode())
            h.update(b"|")
        h.update(f"n={count}".encode())
        return h.hexdigest()
