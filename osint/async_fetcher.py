
from __future__ import annotations
import aiohttp, asyncio, hashlib, os, re, random, time, logging
from bs4 import BeautifulSoup
from typing import Dict, Optional
from .core.config import AppConfig

log = logging.getLogger("async_fetcher")

DATA_DIR = "data/pages"

UA_POOL = [
    # Popular modern UAs to reduce fingerprinting suspicion
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]

ACCEPT_LANG_POOL = [
    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7",
]

def _safe_name(url: str) -> str:
    h = hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]
    return f"{h}.html"

def _basic_meta(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {"title": None, "description": None, "og_image": None}
    title = (soup.title.string if soup.title else "") or ""
    meta_desc = soup.find("meta", attrs={"name":"description"}) or soup.find("meta", attrs={"property":"og:description"})
    desc = meta_desc.get("content") if meta_desc else ""
    og_img = soup.find("meta", attrs={"property":"og:image"})
    if og_img and og_img.has_attr("content"):
        out["og_image"] = og_img["content"]
    out["title"] = (title or "").strip()[:300]
    out["description"] = (desc or "").strip()[:600]
    return out

async def fetch_and_parse(url: str, cfg: Config, session: aiohttp.ClientSession) -> Dict[str, Optional[str]]:
    os.makedirs(DATA_DIR, exist_ok=True)
    out: Dict[str, Optional[str]] = {
        "saved_path": None, "title": None, "description": None, "text_excerpt": None,
        "og_image": None, "created_at": None, "last_activity": None, "error": None
    }
    try:
        timeout = aiohttp.ClientTimeout(total=cfg.timeout)
        headers = {
            "User-Agent": random.choice(UA_POOL) if not cfg.user_agent else cfg.user_agent,
            "Accept-Language": random.choice(ACCEPT_LANG_POOL),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
        }

        async with session.get(url, timeout=timeout, headers=headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                out["error"] = f"HTTP {resp.status}"
                return out
            content = await resp.read()
            fn = os.path.join(DATA_DIR, _safe_name(url))
            with open(fn, "wb") as f:
                f.write(content)
            out["saved_path"] = fn

            soup = BeautifulSoup(content, "lxml")
            meta = _basic_meta(soup)
            out.update(meta)

            for tag in soup(["script","style","noscript","header","footer","nav","svg"]):
                tag.extract()
            text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
            out["text_excerpt"] = text[:4000]

            # naive "activity" detection: look for datestamps
            # ISO-like patterns and Russian month names
            pat = re.compile(r"(20\d{2}[-/.](0?[1-9]|1[012])[-/.](0?[1-9]|[12][0-9]|3[01]))")
            m = pat.search(text)
            if m:
                out["last_activity"] = m.group(1)

    except asyncio.TimeoutError:
        out["error"] = "timeout"
    except Exception as e:
        log.debug("fetch error for %s: %s", url, e)
        out["error"] = f"{type(e).__name__}: {e}"
    return out

def build_session(cfg: Config) -> aiohttp.ClientSession:
    # Keep connector small enough, disable SSL verification in some OSINT contexts
    connector = aiohttp.TCPConnector(ssl=False, limit=cfg.concurrency)
    kwargs = {"connector": connector}
    if cfg.proxy:
        kwargs["trust_env"] = True  # aiohttp will use system proxy if set
    return aiohttp.ClientSession(**kwargs)
