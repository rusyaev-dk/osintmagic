
from __future__ import annotations
import re, json
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Tuple, Optional, Dict, Any, Iterable
from .core.http import HttpClient

PROFILE_PATTERNS = {
    "github": re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})(?:/|$)"),
    "linkedin": re.compile(r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([A-Za-z0-9\-_%]+)"),
    "twitter": re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:/|$)"),
    "instagram": re.compile(r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?"),
    "vk": re.compile(r"^https?://(?:www\.)?vk\.com/([A-Za-z0-9_.]+)$"),
    "telegram": re.compile(r"^https?://t\.me/([A-Za-z0-9_]{3,})"),
    "facebook": re.compile(r"^https?://(?:www\.)?facebook\.com/([A-Za-z0-9.\-]+)/?"),
    "tiktok": re.compile(r"^https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9._]+)/?"),
}

def classify_url(url: str) -> tuple[str|None, str|None]:
    for platform, rx in PROFILE_PATTERNS.items():
        m = rx.match(url)
        if m:
            return platform, m.group(1)
    return None, None

def _text(el) -> str:
    return (el.get_text(" ", strip=True) if el else "").strip()

def _int(s: str) -> Optional[int]:
    s = (s or "").replace(",", "").replace(" ", "")
    m = re.search(r"(\d[\d,\.]*)", s)
    if not m:
        return None
    try:
        val = m.group(1).replace(",", "").replace(".", "")
        return int(val)
    except Exception:
        return None

def parse_emails_and_phones(html: str) -> tuple[set[str], set[str]]:
    emails = set(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", html or ""))
    phones = set(re.findall(r"(?:\+?\d[\s\-()]*){7,}\d", html or ""))
    return emails, phones

def parse_timestamps(html: str, limit: int = 50) -> list[str]:
    out = []
    for m in re.finditer(r'datetime=["\\\']([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z?)["\\\']', html or ""):
        out.append(m.group(1))
        if len(out) >= limit:
            break
    # OpenGraph article published time
    m = re.search(r'property=["\\\']article:published_time["\\\']\\s+content=["\\\']([^"\\\']+)["\\\']', html or "", re.I)
    if m:
        out.append(m.group(1))
    return out

async def enrich_profile(platform: str, url: str, username: str, http: HttpClient) -> dict:
    """Return fields to update SourceResult: title, full_name, username, avatar_url, followers, joined_at, last_active_at, location, skills, repos."""
    html = await http.get_text(url)
    if not html:
        return {}
    soup = BeautifulSoup(html, "lxml")
    data: Dict[str, Any] = {}

    # Common
    og_title = soup.find("meta", attrs={"property":"og:title"})
    og_image = soup.find("meta", attrs={"property":"og:image"})
    og_desc  = soup.find("meta", attrs={"property":"og:description"}) or soup.find("meta", attrs={"name":"description"})
    if og_title and not data.get("title"):
        data["title"] = og_title.get("content")
    if og_image:
        data["avatar_url"] = og_image.get("content")
    if og_desc:
        data.setdefault("extra", {})["description"] = og_desc.get("content")

    # Platform-specific
    if platform == "github":
        data["provider"] = "github"
        data["username"] = username
        # full name
        nm = soup.find(attrs={"itemprop":"name"})
        if nm:
            data["full_name"] = _text(nm)
        # followers
        fol = soup.find("a", href=re.compile(rf"/{re.escape(username)}/followers"))
        if fol:
            data["followers"] = _int(_text(fol))
        # location
        loc = soup.find(attrs={"itemprop":"homeLocation"})
        if loc:
            data.setdefault("extra", {})["location"] = _text(loc)
        # joined
        join = soup.find("svg", attrs={"aria-label": re.compile("Join")})
        if join and join.parent:
            txt = _text(join.parent.parent) if join.parent.parent else ""
            m = re.search(r"Joined\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", txt)
            if m:
                try:
                    data["joined_at"] = datetime.strptime(m.group(1), "%B %d, %Y").isoformat()
                except Exception:
                    pass
        # repos
        repo_links = soup.select('a[itemprop="name codeRepository"]')
        if repo_links:
            repos = []
            for a in repo_links[:10]:
                repos.append({"name": _text(a), "url": "https://github.com" + a.get("href", "")})
            data.setdefault("extra", {})["repos"] = repos

    elif platform == "linkedin":
        data["provider"] = "linkedin"
        data["username"] = username
        # headline/skills from description
        desc = soup.find("meta", attrs={"name":"description"}) or soup.find("meta", attrs={"property":"og:description"})
        if desc:
            data.setdefault("extra", {})["headline"] = desc.get("content")
        # location often in og:title like "Name | LinkedIn"
        ttl = data.get("title") or ""
        # not much else available without login

    elif platform == "twitter":
        data["provider"] = "twitter"
        data["username"] = username
        # name from og:title like "Name (@handle) / X"
        # followers in meta description sometimes like "X followers"
        d = soup.find("meta", attrs={"name":"description"})
        if d:
            data.setdefault("extra", {})["bio"] = d.get("content")
            m = re.search(r"([0-9.,]+)\s+Followers", d.get("content"), re.I)
            if m:
                data["followers"] = _int(m.group(1))

    elif platform == "instagram":
        data["provider"] = "instagram"
        data["username"] = username
        d = soup.find("meta", attrs={"name":"description"}) or soup.find("meta", attrs={"property":"og:description"})
        if d:
            txt = d.get("content") or ""
            m = re.search(r"([0-9.,]+)\s+Followers", txt, re.I)
            if m:
                data["followers"] = _int(m.group(1))

    elif platform == "vk":
        data["provider"] = "vk"
        data["username"] = username
        # try to parse followers/subscribers
        m = re.search(r'(?i)(подписчик(?:ов|а)?|участник(?:ов|а)?)\s*[:\-]?\s*([0-9\s]+)', html)
        if m:
            data["followers"] = _int(m.group(2))

    elif platform == "telegram":
        data["provider"] = "telegram"
        data["username"] = username
        extra = soup.select_one(".tgme_page_extra")
        if extra:
            # e.g. "12 345 subscribers"
            data["followers"] = _int(extra.get_text(" ", strip=True))
        title = soup.select_one(".tgme_page_title")
        if title and not data.get("title"):
            data["title"] = _text(title)

    elif platform == "facebook":
        data["provider"] = "facebook"
        data["username"] = username

    elif platform == "tiktok":
        data["provider"] = "tiktok"
        data["username"] = username

    # common: extract visible emails/phones for graph, and timestamps for activity
    emails, phones = parse_emails_and_phones(html)
    if emails:
        data.setdefault("extra", {})["emails"] = sorted(emails)
    if phones:
        data.setdefault("extra", {})["phones"] = sorted(phones)

    ts = parse_timestamps(html)
    if ts:
        data["last_active_at"] = sorted(ts)[-1]

    return data
