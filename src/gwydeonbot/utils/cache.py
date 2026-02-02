from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class _Entry(Generic[V]):
    expires_at: float
    value: V


class TTLCache(Generic[K, V]):
    """Tiny in-memory TTL cache.

    Good enough for a single-process bot. If you scale horizontally, swap this
    for Redis or similar.
    """

    def __init__(self, ttl_seconds: float):
        self._ttl = float(ttl_seconds)
        self._store: dict[K, _Entry[V]] = {}

    def get(self, key: K) -> V | None:
        now = time.time()
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.expires_at <= now:
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: K, value: V) -> None:
        self._store[key] = _Entry(expires_at=time.time() + self._ttl, value=value)

    def clear(self) -> None:
        self._store.clear()
