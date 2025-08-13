
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    concurrency: int = 20
    rps: float = 2.0
    timeout: int = 20
    retries: int = 2
    jitter_ms: int = 250
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    proxy: Optional[str] = None  # например: "socks5://127.0.0.1:9050" для Tor
    cache_ttl_sec: int = 60 * 60 * 24  # 24h
    enable_nlp: bool = False
