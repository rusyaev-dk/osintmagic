
from __future__ import annotations
import yaml, os, random
from typing import Dict, List

CATEGORIES = ["Social", "Forums", "Blogs", "PublicDB", "Darknet", "Gov", "Dev", "Paste", "Media", "Whois"]

def load_sources(path: str = "sources/sources_db.yaml") -> Dict[str, List[str]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data

def sample_health_check(sources: dict, limit: int = 10) -> List[str]:
    # Возвращает случайные домены для проверки доступности (проверка делается движком)
    all_doms = [d for lst in sources.values() for d in lst]
    random.shuffle(all_doms)
    return all_doms[:limit]


from urllib.parse import urlparse

def categorize_url(url: str, db: dict | None = None) -> str | None:
    """Возвращает категорию на основе домена из базы sources_db.yaml"""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if not db:
        try:
            db = load_sources()
        except Exception:
            db = {}
    for cat, doms in (db or {}).items():
        for d in doms or []:
            d = (d or "").lower().strip()
            if not d: 
                continue
            # exact host or subdomain match
            if host == d or host.endswith("." + d):
                return cat
    return None
