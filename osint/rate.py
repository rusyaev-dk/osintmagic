
from __future__ import annotations
import asyncio, random, time
from typing import Optional, Dict
from urllib.parse import urlparse

class AsyncRateLimiter:
    """Асинхронный token-bucket с джиттером."""
    def __init__(self, rps: Optional[float] = None):
        self.rps = float(rps) if rps and rps > 0 else None
        self.capacity = self.rps or 1.0
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def wait(self, n: float = 1.0, jitter_ms: int = 0):
        if not self.rps:
            if jitter_ms:
                await asyncio.sleep(random.uniform(0, jitter_ms/1000))
            return
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rps)
            while self.tokens < n:
                need = (n - self.tokens) / self.rps
                await asyncio.sleep(min(need, 0.2))
                now = time.monotonic()
                gained = (now - self.last) * self.rps
                self.last = now
                self.tokens = min(self.capacity, self.tokens + gained)
            self.tokens -= n
        if jitter_ms:
            await asyncio.sleep(random.uniform(0, jitter_ms/1000))

class DomainRateLimiter:
    """Отдельный лимитер для каждого домена (чтобы избегать бурстов на один хост)."""
    def __init__(self, default_rps: float = 1.5):
        self.default_rps = default_rps
        self._buckets: Dict[str, AsyncRateLimiter] = {}
        self._lock = asyncio.Lock()

    async def wait(self, url: str, jitter_ms: int = 200):
        host = urlparse(url).netloc or "default"
        async with self._lock:
            if host not in self._buckets:
                self._buckets[host] = AsyncRateLimiter(self.default_rps)
        await self._buckets[host].wait(1.0, jitter_ms=jitter_ms)
