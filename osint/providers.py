from __future__ import annotations
from typing import List, Dict
import os, requests

class ProviderBase:
    NAME = "base"
    def available(self) -> bool:
        return True
    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        raise NotImplementedError

# --- Brave ---
class BraveProvider(ProviderBase):
    NAME = "brave"
    def __init__(self) -> None:
        # ключ берём из переменных окружения (CLI загрузит .env)
        self.key = os.getenv("BRAVE_API_KEY")
    def available(self) -> bool:
        return bool(self.key)
    def search(self, query: str, limit: int = 10):
        if not self.available():
            return []
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {"Accept": "application/json", "X-Subscription-Token": self.key}
        params = {"q": query, "count": max(1, min(20, limit))}
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = (data.get("web", {}) or {}).get("results", [])
        return [{"title": i.get("title",""), "link": i.get("url",""), "snippet": i.get("description","")}
                for i in items[:limit]]

# --- Bing (опционально) ---
class BingProvider(ProviderBase):
    NAME = "bing"
    def __init__(self) -> None:
        self.key = os.getenv("BING_API_KEY")
    def available(self) -> bool:
        return bool(self.key)
    def search(self, query: str, limit: int = 10):
        if not self.available():
            return []
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.key}
        params = {"q": query, "count": limit, "textDecorations": False}
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        items = r.json().get("webPages", {}).get("value", [])
        return [{"title": i.get("name",""), "link": i.get("url",""), "snippet": i.get("snippet","")}
                for i in items[:limit]]

# --- SerpAPI (опционально) ---
class SerpAPIProvider(ProviderBase):
    NAME = "serpapi"
    def __init__(self) -> None:
        self.key = os.getenv("SERPAPI_KEY")
    def available(self) -> bool:
        return bool(self.key)
    def search(self, query: str, limit: int = 10):
        if not self.available():
            return []
        url = "https://serpapi.com/search.json"
        params = {"q": query, "api_key": self.key, "num": limit, "engine": "google"}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        items = r.json().get("organic_results", [])
        return [{"title": i.get("title",""), "link": i.get("link",""), "snippet": i.get("snippet","")}
                for i in items[:limit]]

# Реестр и выбор
REGISTRY = {
    "brave": BraveProvider,
    "bing": BingProvider,
    "serpapi": SerpAPIProvider,
}

def pick_providers(selection: str = "all") -> List[ProviderBase]:
    """
    selection: 'all' | 'brave' | 'bing' | 'serpapi' | 'brave,bing' ...
    По умолчанию вернём все доступные по ключам среды.
    """
    wanted = None if selection.strip().lower() == "all" else {
        s.strip().lower() for s in selection.split(",") if s.strip()
    }
    providers: List[ProviderBase] = []
    for name, cls in REGISTRY.items():
        if wanted is not None and name not in wanted:
            continue
        p = cls()
        if p.available():
            providers.append(p)
    # Если явно просили конкретные и они недоступны — создадим их, но вернут пустые результаты
    if wanted and not providers:
        providers = [REGISTRY[n]() for n in wanted if n in REGISTRY]
    return providers
