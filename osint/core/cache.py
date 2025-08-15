# cache.py
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    # предположим, вы используете diskcache или аналогичный интерфейс
    from diskcache import Cache  # noqa: F401
except ImportError:
    # простой in-memory fallback на случай отсутствия библиотеки (для тестов)
    class Cache(dict):
        def __init__(self, _path: str):  # path игнорируем
            super().__init__()
        def get(self, key):  # type: ignore[override]
            return super().get(key)
        def set(self, key, value, expire=None):
            super().__setitem__(key, value)
        def close(self): pass

@dataclass
class CacheStore:
    path: Path
    ttl: int = 86400

    def __post_init__(self):
        self._cache = Cache(str(self.path))
        self._hits: int = 0
        self._misses: int = 0

    def make_key(self, name: str, params: dict) -> str:
        raw = name + "::" + json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        val = self._cache.get(key)
        if val is None:
            self._misses += 1
        else:
            self._hits += 1
        return val

    def set(self, key: str, value: Any, ttl: int | None = None):
        self._cache.set(key, value, expire=ttl or self.ttl)

    def stats(self) -> dict[str, int]:
        # позволит пайплайну безопасно читать метрики
        return {"hits": self._hits, "misses": self._misses}

    def close(self):
        self._cache.close()
