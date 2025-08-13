from __future__ import annotations
from abc import ABC, abstractmethod
from ..core.models import SourceResult
from ..core.cache import CacheStore
from ..core.http import HttpClient
from typing import Sequence

class Provider(ABC):
    name = "base"

    @abstractmethod
    async def search(self, query: str, http: HttpClient, cache: CacheStore, fresh: bool=False) -> Sequence[SourceResult]:
        ...
