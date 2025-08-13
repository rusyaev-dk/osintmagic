from __future__ import annotations
from dataclasses import dataclass
from diskcache import Cache
from pathlib import Path
import hashlib
import json
from typing import Any

@dataclass
class CacheStore:
    path: Path
    ttl: int = 86400

    def __post_init__(self):
        self._cache = Cache(str(self.path))

    def make_key(self, name: str, params: dict) -> str:
        raw = name + "::" + json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None):
        self._cache.set(key, value, expire=ttl or self.ttl)

    def close(self):
        self._cache.close()
