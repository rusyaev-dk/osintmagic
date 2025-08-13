from __future__ import annotations
import asyncio, os
from typing import Sequence
from ..core.models import SourceResult
from ..core.cache import CacheStore
from ..core.http import HttpClient

class BraveProvider:
    name = "brave"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        self.endpoint = "https://api.search.brave.com/res/v1/web/search"

    async def search(
        self,
        query: str,
        http: HttpClient,
        cache: CacheStore,
        fresh: bool = False
    ) -> Sequence[SourceResult]:
        # кэш
        key = cache.make_key(self.name, {"q": query})
        if not fresh:
            cached = cache.get(key)
            if cached:
                return [SourceResult(**item) for item in cached]

        # нет ключа — возвращаем пусто (честно, без фолбэков)
        if not self.api_key:
            cache.set(key, [])
            return []

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params = {
            "q": query,
            "count": 10,      # можно варьировать
            # "country": "US", # опционально
        }

        results: list[SourceResult] = []

        # делаем запрос напрямую через общий aiohttp-сессионник, минуя robots.txt
        await http.rate.throttle(self.endpoint)
        try:
            assert http.session is not None, "HTTP session is not initialized"
            async with http.session.get(self.endpoint, params=params, headers=headers) as r:
                if r.status != 200:
                    # полезно оставить короткий текст ошибки в кэше, чтобы не спамить API
                    try:
                        txt = await r.text()
                    except Exception:
                        txt = ""
                    cache.set(key, [])
                    return []
                data = await r.json()
        except asyncio.TimeoutError:
            cache.set(key, [])
            return []
        except Exception:
            cache.set(key, [])
            return []

        web = (data or {}).get("web") or {}
        for item in (web.get("results") or []):
            url = item.get("url")
            if not url:
                continue
            results.append(
                SourceResult(
                    provider=self.name,
                    url=url,
                    title=item.get("title"),
                    snippet=item.get("description"),
                )
            )

        cache.set(key, [r.__dict__ for r in results])
        return results
