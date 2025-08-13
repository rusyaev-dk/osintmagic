
from __future__ import annotations
import asyncio, re
from typing import List, Dict, Tuple
from .async_fetcher import fetch_and_parse
from .core.models import SearchHit
from .username_filter import looks_bad

PROFILE_PATTERNS = {
    "twitter": r"https?://(x\.com|twitter\.com)/([A-Za-z0-9_]{3,15})/?$",
    "instagram": r"https?://(www\.)?instagram\.com/([A-Za-z0-9_.]{3,30})/?$",
    "tiktok": r"https?://(www\.)?tiktok\.com/@([A-Za-z0-9_.]{3,24})/?$"
}

def extract_username(url: str) -> str | None:
    for _, pat in PROFILE_PATTERNS.items():
        m = re.match(pat, url, flags=re.I)
        if m:
            return m.group(2)
    return None

async def verify_profiles(urls: List[str], ctx) -> List[SearchHit]:
    out: List[SearchHit] = []
    tasks = []
    for u in urls:
        tasks.append(asyncio.create_task(fetch_and_parse(u, ctx["cfg"], ctx["session"])))
    for u, t in zip(urls, tasks):
        meta = await t
        hit = SearchHit(title=meta.get("title") or u, url=u, snippet=meta.get("description") or "", provider="probe")
        hit.og_image = meta.get("og_image")
        user = extract_username(u)
        if user and not looks_bad(user):
            hit.username = user
        hit.category = "Social" if user else "Other"
        out.append(hit)
    return out
