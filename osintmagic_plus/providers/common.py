# osintmagic_plus/providers/common.py
from __future__ import annotations
from bs4 import BeautifulSoup
from ..core.http import HttpClient

async def extract_metadata(url: str, http: HttpClient) -> dict | None:
    try:
        html = await http.get_text(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property":"og:description"})
        meta_desc = (desc.get("content") or "").strip() if desc else None
        og_title = soup.find("meta", attrs={"property":"og:title"})
        meta_title = (og_title.get("content") or "").strip() if og_title else None
        return {"title": meta_title or title, "description": meta_desc}
    except Exception:
        return None
