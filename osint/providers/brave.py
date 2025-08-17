# osint/providers/brave.py
from __future__ import annotations
import asyncio, os, logging, json
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
        fresh: bool = False,
        count: int = 10,
        country: str | None = None,   # опционально, если понадобится
    ) -> Sequence[SourceResult]:
        # ключ кэша включает важные параметры запроса
        key_data = {"q": query, "count": count}
        if country:
            key_data["country"] = country
        key = cache.make_key(self.name, key_data)

        if not fresh:
            cached = cache.get(key)
            if cached is not None:
                return [SourceResult(**item) for item in cached]

        if not self.api_key:
            logging.warning("BraveProvider: отсутствует API ключ")
            return []

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params: dict[str, object] = {
            "q": query,
            "count": count,
        }
        if country:
            params["country"] = country

        await http.rate.throttle(self.endpoint)

        data: dict | None = None
        try:
            assert http.session is not None, "HTTP session is not initialized"
            async with http.session.get(self.endpoint, params=params, headers=headers) as r:
                if r.status != 200:
                    # логируем, но не кэшируем неуспех
                    body_preview = ""
                    try:
                        body_preview = (await r.text())[:500]
                    except Exception:
                        pass
                    logging.warning("Brave API non-200: %s; body=%r", r.status, body_preview)
                    return []
                # надёжный парс JSON
                try:
                    data = await r.json()
                except (json.JSONDecodeError, aiohttp.ContentTypeError):  # type: ignore[name-defined]
                    # aiohttp.ContentTypeError доступен только если импортирован; fallback:
                    try:
                        data = json.loads(await r.text())
                    except Exception as e:
                        logging.warning("Brave API bad JSON: %s", e)
                        return []
        except asyncio.TimeoutError:
            logging.warning("Brave API timeout for %r", query)
            return []
        except Exception as err:
            logging.exception("Brave API error: %s", err)
            return []

        # нормализация структуры ответа
        web = (data or {}).get("web") or {}
        raw_results = web.get("results") or []

        results: list[SourceResult] = []
        for item in raw_results:
            try:
                url = item.get("url")
                if not url:
                    continue
                results.append(
                    SourceResult(
                        provider=self.name,
                        url=url,
                        title=item.get("title") or "",
                        snippet=item.get("description") or "",
                    )
                )
            except Exception:
                # не валим весь список из-за одного странного айтема
                continue

        # кэшируем ТОЛЬКО успешный результат (даже если он пустой)
        cache.set(key, [r.__dict__ for r in results])
        print(results)
        return results
