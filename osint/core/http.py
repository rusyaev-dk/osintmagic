# osint/core/http.py
from __future__ import annotations
import asyncio, logging, random, time
import aiohttp
from aiohttp_socks import ProxyConnector
from aiohttp import ClientTimeout
from aiohttp import resolver as aioresolver
from urllib.parse import urlparse
from collections import defaultdict

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
]

class RateLimiter:
    def __init__(self, min_interval_per_host: tuple[float,float] = (1.0, 2.0)):
        self.min, self.max = min_interval_per_host
        self.last = defaultdict(float)
        self.lock = asyncio.Lock()

    async def throttle(self, url: str):
        host = urlparse(url).netloc
        async with self.lock:
            now = time.monotonic()
            wait_for = 0.0
            if self.last[host] != 0:
                wait_for = random.uniform(self.min, self.max)
                elapsed = now - self.last[host]
                if elapsed < wait_for:
                    await asyncio.sleep(wait_for - elapsed)
            self.last[host] = time.monotonic()

class HttpClient:
    def __init__(self, timeout: int, tor_socks: str | None = None,
                 http_proxy: str | None = None, https_proxy: str | None = None):
        self.timeout = timeout
        self.tor_socks = tor_socks
        self.http_proxy = http_proxy
        self.https_proxy = https_proxy
        self.rate = RateLimiter()
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        timeout = ClientTimeout(total=self.timeout)

        # Явно задаём резолвер, чтобы не было 'getaddrinfo' None
        if self.tor_socks:
            connector = ProxyConnector.from_url(self.tor_socks, rdns=True)
        else:
            connector = aiohttp.TCPConnector(resolver=aioresolver.AsyncResolver())

        self.session = aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_json(self, url: str, params: dict | None = None,
                       headers: dict | None = None) -> dict | None:
        if not self.session:
            return None
        await self.rate.throttle(url)
        try:
            async with self.session.get(url, params=params, headers=headers) as r:
                if r.status == 200:
                    return await r.json()
                return None
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def get_text(self, url: str, headers: dict | None = None) -> str | None:
        if not self.session:
            return None
        await self.rate.throttle(url)
        try:
            async with self.session.get(url, headers=headers) as r:
                if r.status == 200:
                    return await r.text(errors="ignore")
                return None
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None
