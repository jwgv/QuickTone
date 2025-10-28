from __future__ import annotations

import time as _time

import pytest

from app.services.cache import MemoryCache


def test_cache_set_get_and_hashes():
    c: MemoryCache[str, int] = MemoryCache(max_size=3, ttl_seconds=None)
    c.set("a", 1)
    c.set("b", 2)
    assert c.get("a") == 1
    assert c.get("missing") is None
    # LRU refresh on get
    c.get("a")
    # Hash helpers should be stable and different for different inputs
    h1 = MemoryCache.hash_text("model", "task", "text")
    h2 = MemoryCache.hash_text("model", "task", "text!")
    assert h1 != h2
    h3 = MemoryCache.hash_texts("model", "task", ["a", "bb"])  # length included
    h4 = MemoryCache.hash_texts("model", "task", ["aa", "b"])  # different order/lengths
    assert h3 != h4


def test_cache_lru_evict():
    c: MemoryCache[str, int] = MemoryCache(max_size=2, ttl_seconds=None)
    c.set("a", 1)
    c.set("b", 2)
    # Access "a" to make it most-recent
    assert c.get("a") == 1
    # Add new item, should evict least recent ("b")
    c.set("c", 3)
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("c") == 3


@pytest.mark.parametrize("ttl,advance,expected", [(1, 0.5, True), (1, 2.0, False)])
def test_cache_ttl_expiry(monkeypatch, ttl, advance, expected):
    base = _time.time()
    current = {"t": base}

    def fake_time():
        return current["t"]

    monkeypatch.setattr("time.time", fake_time)
    c: MemoryCache[str, int] = MemoryCache(max_size=2, ttl_seconds=ttl)
    c.set("a", 1)
    # advance time
    current["t"] = base + advance
    val = c.get("a")
    if expected:
        assert val == 1
    else:
        assert val is None
    # stats should reflect one hit or miss
    if expected:
        assert c.stats.hits == 1
    else:
        assert c.stats.misses == 1
