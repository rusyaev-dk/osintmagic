from __future__ import annotations
import re
import json
import asyncio
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any, List, Set, Union
from dataclasses import dataclass
from .core.http import HttpClient
from .core.models import ProfileData

# Расширенные паттерны для различных платформ и их вариантов
PROFILE_PATTERNS = {
    "github": [
        re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9\-_]{1,39})(?:/.*)?$"),
        re.compile(r"^https?://gist\.github\.com/([A-Za-z0-9\-_]{1,39})(?:/.*)?$"),
    ],
    "linkedin": [
        re.compile(r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([A-Za-z0-9\-_%]+)/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/pub/([A-Za-z0-9\-_%]+)/?(?:\?.*)?$"),
    ],
    "twitter": [
        re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:/.*)?$"),
        re.compile(r"^https?://(?:mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:/.*)?$"),
    ],
    "instagram": [
        re.compile(r"^https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:www\.)?instagr\.am/([A-Za-z0-9_.]+)/?(?:\?.*)?$"),
    ],
    "vk": [
        re.compile(r"^https?://(?:www\.)?vk\.com/([A-Za-z0-9_.]+)/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:m\.)?vk\.com/([A-Za-z0-9_.]+)/?(?:\?.*)?$"),
    ],
    "telegram": [
        re.compile(r"^https?://t\.me/([A-Za-z0-9_]{3,})/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:www\.)?telegram\.me/([A-Za-z0-9_]{3,})/?(?:\?.*)?$"),
    ],
    "facebook": [
        re.compile(r"^https?://(?:www\.)?facebook\.com/([A-Za-z0-9.\-]+)/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:m\.)?facebook\.com/([A-Za-z0-9.\-]+)/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:www\.)?fb\.com/([A-Za-z0-9.\-]+)/?(?:\?.*)?$"),
    ],
    "tiktok": [
        re.compile(r"^https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9._]+)/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:vm\.)?tiktok\.com/([A-Za-z0-9]+)/?(?:\?.*)?$"),
    ],
    "youtube": [
        re.compile(r"^https?://(?:www\.)?youtube\.com/(?:c|channel|user)/([A-Za-z0-9\-_]+)/?(?:\?.*)?$"),
        re.compile(r"^https?://(?:www\.)?youtube\.com/@([A-Za-z0-9\-_]+)/?(?:\?.*)?$"),
    ],
    "reddit": [
        re.compile(r"^https?://(?:www\.)?reddit\.com/(?:u|user)/([A-Za-z0-9\-_]+)/?(?:\?.*)?$"),
    ],
    "discord": [
        re.compile(r"^https?://(?:www\.)?discord\.(?:com|gg)/(?:users?/)?([0-9]{17,19})/?(?:\?.*)?$"),
    ],
    # CIS-specific platforms
    "ok": [
        re.compile(r"^https?://(?:www\.)?ok\.ru/profile/([0-9]+)/?(?:\?.*)?$"),
    ],
    "rutube": [
        re.compile(r"^https?://(?:www\.)?rutube\.ru/video/person/([0-9]+)/?(?:\?.*)?$"),
    ],
    "yandex_zen": [
        re.compile(r"^https?://zen\.yandex\.ru/([A-Za-z0-9\-_]+)/?(?:\?.*)?$"),
    ],
    "habr": [
        re.compile(r"^https?://(?:www\.)?habr\.com/(?:ru/)?users/([A-Za-z0-9\-_]+)/?(?:\?.*)?$"),
    ],
    "pikabu": [
        re.compile(r"^https?://(?:www\.)?pikabu\.ru/@([A-Za-z0-9\-_]+)/?(?:\?.*)?$"),
    ],
}


def classify_url(url: str) -> tuple[str | None, str | None]:
    """Enhanced URL classification with multiple patterns per platform"""
    for platform, patterns in PROFILE_PATTERNS.items():
        for pattern in patterns:
            match = pattern.match(url)
            if match:
                return platform, match.group(1)
    return None, None


def _text(el) -> str:
    """Extract clean text from BeautifulSoup element"""
    if not el:
        return ""
    return el.get_text(" ", strip=True).strip()


def _int(s: str) -> Optional[int]:
    """Enhanced number parsing with support for K, M suffixes"""
    if not s:
        return None

    # Remove common formatting
    s = str(s).replace(",", "").replace(" ", "").replace(".", "").upper()

    # Handle K, M, B suffixes
    multiplier = 1
    if s.endswith('K'):
        multiplier = 1000
        s = s[:-1]
    elif s.endswith('M'):
        multiplier = 1000000
        s = s[:-1]
    elif s.endswith('B'):
        multiplier = 1000000000
        s = s[:-1]

    # Extract number
    match = re.search(r"(\d+(?:\.\d+)?)", s)
    if not match:
        return None

    try:
        val = float(match.group(1)) * multiplier
        return int(val)
    except (ValueError, TypeError):
        return None


def parse_contacts(html: str) -> tuple[set[str], set[str]]:
    """Enhanced email and phone extraction"""
    if not html:
        return set(), set()

    # More comprehensive email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = set(re.findall(email_pattern, html, re.IGNORECASE))

    # Enhanced phone pattern for international formats
    phone_patterns = [
        r'\+?[1-9]\d{1,14}',  # International format
        r'\b(?:\+?7|8)[\s\-\(\)]?(?:\d[\s\-\(\)]?){10}\b',  # Russian format
        r'\b(?:\+?380)[\s\-\(\)]?(?:\d[\s\-\(\)]?){9}\b',  # Ukrainian format
        r'\b(?:\+?375)[\s\-\(\)]?(?:\d[\s\-\(\)]?){9}\b',  # Belarusian format
    ]

    phones = set()
    for pattern in phone_patterns:
        phones.update(re.findall(pattern, html))

    # Clean up phones - remove obviously invalid ones
    valid_phones = set()
    for phone in phones:
        clean_phone = re.sub(r'[^\d+]', '', phone)
        if len(clean_phone) >= 7 and len(clean_phone) <= 15:
            valid_phones.add(phone)

    return emails, valid_phones


def parse_timestamps(html: str, limit: int = 100) -> list[str]:
    """Enhanced timestamp extraction with multiple formats"""
    if not html:
        return []

    timestamps = []

    # Various timestamp patterns
    patterns = [
        r'datetime=["\']([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})?)["\']',
        r'data-time=["\']([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})?)["\']',
        r'timestamp=["\']([0-9]{10,13})["\']',  # Unix timestamps
        r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']',
        r'property=["\']article:modified_time["\'][^>]*content=["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, html, re.IGNORECASE)
        for match in matches:
            timestamp = match.group(1)
            # Convert Unix timestamp if needed
            if timestamp.isdigit():
                try:
                    if len(timestamp) == 13:  # milliseconds
                        timestamp = str(int(timestamp) // 1000)
                    dt = datetime.fromtimestamp(int(timestamp))
                    timestamp = dt.isoformat()
                except (ValueError, OSError):
                    continue
            timestamps.append(timestamp)
            if len(timestamps) >= limit:
                break
        if len(timestamps) >= limit:
            break

    return timestamps


def extract_json_data(html: str, patterns: List[str]) -> Dict[str, Any]:
    """Extract JSON data from script tags using multiple patterns"""
    if not html:
        return {}

    for pattern in patterns:
        matches = re.finditer(pattern, html, re.DOTALL)
        for match in matches:
            try:
                json_str = match.group(1)
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                continue
    return {}


async def enrich_profile(platform: str, url: str, username: str, http: HttpClient) -> ProfileData:
    """Enhanced profile enrichment with platform-specific optimizations"""

    # Initialize profile data
    profile = ProfileData(platform=platform, username=username, url=url)

    try:
        html = await http.get_text(url)
        if not html:
            return profile

        soup = BeautifulSoup(html, "lxml")

        # Extract common metadata first
        await _extract_common_metadata(profile, soup, html)

        # Platform-specific extraction
        extractors = {
            "github": _extract_github_data,
            "linkedin": _extract_linkedin_data,
            "twitter": _extract_twitter_data,
            "instagram": _extract_instagram_data,
            "vk": _extract_vk_data,
            "telegram": _extract_telegram_data,
            "facebook": _extract_facebook_data,
            "tiktok": _extract_tiktok_data,
            "youtube": _extract_youtube_data,
            "reddit": _extract_reddit_data,
            "ok": _extract_ok_data,
            "rutube": _extract_rutube_data,
            "yandex_zen": _extract_yandex_zen_data,
            "habr": _extract_habr_data,
            "pikabu": _extract_pikabu_data,
        }

        extractor = extractors.get(platform)
        if extractor:
            await extractor(profile, soup, html)

        # Extract contacts and activity data
        emails, phones = parse_contacts(html)
        if emails:
            profile.extra["emails"] = sorted(emails)
        if phones:
            profile.extra["phones"] = sorted(phones)

        timestamps = parse_timestamps(html)
        if timestamps:
            profile.last_active_at = sorted(timestamps)[-1]
            profile.extra["activity_timestamps"] = timestamps[-10:]  # Keep last 10

    except Exception as e:
        profile.extra["error"] = str(e)

    return profile


async def _extract_common_metadata(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract common Open Graph and meta data"""

    # Open Graph data
    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_image = soup.find("meta", attrs={"property": "og:image"})
    og_desc = soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta",
                                                                                   attrs={"name": "description"})
    og_url = soup.find("meta", attrs={"property": "og:url"})

    if og_title and not profile.title:
        profile.title = og_title.get("content", "").strip()
    if og_image:
        profile.avatar_url = og_image.get("content", "").strip()
    if og_desc:
        profile.extra["description"] = og_desc.get("content", "").strip()
    if og_url:
        profile.extra["canonical_url"] = og_url.get("content", "").strip()

    # Check for verification badges
    verification_indicators = [
        "verified", "badge", "checkmark", "✓", "verified-badge",
        "verification", "blue-tick", "check-circle"
    ]
    for indicator in verification_indicators:
        if indicator in html.lower():
            profile.verified = True
            break


# Platform-specific extractors
async def _extract_github_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract GitHub-specific data"""

    # Full name
    name_el = soup.find(attrs={"itemprop": "name"}) or soup.find("h1", class_="vcard-names")
    if name_el:
        profile.full_name = _text(name_el)

    # Bio
    bio_el = soup.find(attrs={"itemprop": "description"}) or soup.find("div", class_="user-profile-bio")
    if bio_el:
        profile.bio = _text(bio_el)

    # Location
    loc_el = soup.find(attrs={"itemprop": "homeLocation"}) or soup.find("li", attrs={"itemprop": "homeLocation"})
    if loc_el:
        profile.location = _text(loc_el)

    # Website
    website_el = soup.find("a", attrs={"itemprop": "url"})
    if website_el:
        profile.website = website_el.get("href")

    # Followers/Following
    stats_links = soup.find_all("a", href=re.compile(f"/{re.escape(profile.username)}/(followers|following)"))
    for link in stats_links:
        count_el = link.find("span", class_="text-bold")
        if count_el:
            count = _int(_text(count_el))
            if "followers" in link.get("href", ""):
                profile.followers = count
            elif "following" in link.get("href", ""):
                profile.following = count

    # Join date
    join_el = soup.find("relative-time")
    if join_el:
        datetime_attr = join_el.get("datetime")
        if datetime_attr:
            try:
                profile.joined_at = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00')).isoformat()
            except ValueError:
                pass

    # Repositories
    repo_links = soup.select('a[itemprop="name codeRepository"], [data-testid="repository-name-link"]')
    if repo_links:
        repos = []
        for link in repo_links[:15]:  # Top 15 repos
            repo_name = _text(link)
            repo_url = urljoin(profile.url, link.get("href", ""))
            if repo_name and repo_url:
                repos.append({"name": repo_name, "url": repo_url})
        if repos:
            profile.extra["repositories"] = repos

    # Languages (from repositories)
    lang_elements = soup.find_all("span", attrs={"itemprop": "programmingLanguage"})
    if lang_elements:
        languages = [_text(el) for el in lang_elements if _text(el)]
        if languages:
            profile.extra["languages"] = list(set(languages))


async def _extract_twitter_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Twitter/X-specific data"""

    # Try to extract from JSON-LD or other structured data
    json_patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
        r'"UserResult":\s*({.+?"legacy":\s*{[^}]+}})',
    ]

    json_data = extract_json_data(html, json_patterns)

    # Fallback to HTML parsing
    if not json_data:
        # Bio from meta description
        desc_el = soup.find("meta", attrs={"name": "description"})
        if desc_el:
            desc_content = desc_el.get("content", "")
            profile.extra["bio_description"] = desc_content

            # Try to extract follower count from description
            follower_match = re.search(r"([0-9,.]+)\s+followers", desc_content, re.IGNORECASE)
            if follower_match:
                profile.followers = _int(follower_match.group(1))


async def _extract_instagram_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Instagram-specific data"""

    # Try to extract from window._sharedData
    json_patterns = [
        r'window\._sharedData\s*=\s*({.+?});',
        r'"graphql":\s*({.+?"user":\s*{[^}]+}})',
    ]

    json_data = extract_json_data(html, json_patterns)
    if json_data:
        # Process Instagram JSON data
        try:
            user_data = json_data.get("entry_data", {}).get("ProfilePage", [{}])[0].get("graphql", {}).get("user", {})
            if user_data:
                profile.full_name = user_data.get("full_name")
                profile.bio = user_data.get("biography")
                profile.followers = user_data.get("edge_followed_by", {}).get("count")
                profile.following = user_data.get("edge_follow", {}).get("count")
                profile.posts_count = user_data.get("edge_owner_to_timeline_media", {}).get("count")
                profile.verified = user_data.get("is_verified", False)
                profile.website = user_data.get("external_url")
        except (KeyError, IndexError, TypeError):
            pass

    # Fallback to meta tag parsing
    if not profile.followers:
        desc_el = soup.find("meta", attrs={"name": "description"})
        if desc_el:
            desc = desc_el.get("content", "")
            # Pattern: "123 Followers, 456 Following, 789 Posts"
            follower_match = re.search(r"([0-9,.]+)\s+followers", desc, re.IGNORECASE)
            if follower_match:
                profile.followers = _int(follower_match.group(1))


async def _extract_vk_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract VK-specific data"""

    # Full name from title
    if profile.title and " | " in profile.title:
        name_part = profile.title.split(" | ")[0]
        profile.full_name = name_part

    # Followers/subscribers
    counter_patterns = [
        r'(?i)(подписчик(?:ов|а)?|участник(?:ов|а)?)\s*[:\-]?\s*([0-9\s,.]+)',
        r'class="counts_module"[^>]*>.*?([0-9\s,.]+)',
    ]

    for pattern in counter_patterns:
        match = re.search(pattern, html)
        if match:
            profile.followers = _int(match.group(-1))
            break

    # Status/bio
    status_el = soup.find("div", class_="page_status")
    if status_el:
        profile.bio = _text(status_el)


async def _extract_telegram_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Telegram-specific data"""

    # Channel/group info
    title_el = soup.find("div", class_="tgme_page_title")
    if title_el:
        profile.title = _text(title_el)

    # Subscribers
    extra_el = soup.find("div", class_="tgme_page_extra")
    if extra_el:
        extra_text = _text(extra_el)
        # Pattern: "12 345 subscribers" or "12 345 members"
        sub_match = re.search(r"([0-9\s,.]+)\s+(subscribers?|members?)", extra_text, re.IGNORECASE)
        if sub_match:
            profile.followers = _int(sub_match.group(1))

    # Description
    desc_el = soup.find("div", class_="tgme_page_description")
    if desc_el:
        profile.bio = _text(desc_el)


async def _extract_linkedin_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract LinkedIn-specific data (limited due to login requirements)"""

    # Extract what's available from meta tags
    desc_el = soup.find("meta", attrs={"name": "description"})
    if desc_el:
        desc = desc_el.get("content", "")
        profile.extra["professional_headline"] = desc

        # Try to extract company/title info
        lines = desc.split(" | ")
        if len(lines) >= 2:
            profile.extra["headline"] = lines[0]
            profile.extra["company"] = lines[1]


async def _extract_facebook_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Facebook-specific data (limited due to login requirements)"""

    # Basic info from meta tags
    desc_el = soup.find("meta", attrs={"name": "description"})
    if desc_el:
        profile.extra["page_description"] = desc_el.get("content", "")


async def _extract_tiktok_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract TikTok-specific data"""

    # Try to extract from SIGI_STATE or other embedded JSON
    json_patterns = [
        r'window\[.SIGI_STATE.\]\s*=\s*({.+?});',
        r'"UserModule":\s*({.+?"users":\s*{[^}]+}})',
    ]

    json_data = extract_json_data(html, json_patterns)
    # TikTok JSON parsing would go here

    # Fallback to HTML parsing
    pass


async def _extract_youtube_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract YouTube-specific data"""

    # Subscriber count
    sub_elements = soup.find_all(string=re.compile(r"subscriber", re.IGNORECASE))
    for el in sub_elements:
        parent = el.parent if hasattr(el, 'parent') else None
        if parent:
            text = _text(parent)
            sub_match = re.search(r"([0-9,.KMB]+)\s+subscriber", text, re.IGNORECASE)
            if sub_match:
                profile.followers = _int(sub_match.group(1))
                break


async def _extract_reddit_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Reddit-specific data"""

    # Karma
    karma_pattern = r'"totalKarma":\s*(\d+)'
    karma_match = re.search(karma_pattern, html)
    if karma_match:
        profile.extra["karma"] = int(karma_match.group(1))

    # Cake day (join date)
    cake_pattern = r'"createdAt":\s*"([^"]+)"'
    cake_match = re.search(cake_pattern, html)
    if cake_match:
        try:
            profile.joined_at = cake_match.group(1)
        except ValueError:
            pass


# CIS-specific platform extractors
async def _extract_ok_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Odnoklassniki-specific data"""

    # Friends count
    friends_pattern = r'(?i)(друзей?|friends?)\s*[:\-]?\s*([0-9\s,.]+)'
    friends_match = re.search(friends_pattern, html)
    if friends_match:
        profile.followers = _int(friends_match.group(2))


async def _extract_rutube_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract RuTube-specific data"""

    # Subscribers
    subs_pattern = r'(?i)(подписчик(?:ов|а)?)\s*[:\-]?\s*([0-9\s,.]+)'
    subs_match = re.search(subs_pattern, html)
    if subs_match:
        profile.followers = _int(subs_match.group(2))


async def _extract_yandex_zen_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Yandex Zen-specific data"""

    # Followers
    followers_pattern = r'(?i)(подписчик(?:ов|а)?)\s*[:\-]?\s*([0-9\s,.]+)'
    followers_match = re.search(followers_pattern, html)
    if followers_match:
        profile.followers = _int(followers_match.group(2))


async def _extract_habr_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Habr-specific data"""

    # Rating and other stats
    rating_el = soup.find("div", class_="user-info__rating")
    if rating_el:
        profile.extra["rating"] = _text(rating_el)

    # Followers
    followers_el = soup.find("div", class_="user-info__followers")
    if followers_el:
        profile.followers = _int(_text(followers_el))


async def _extract_pikabu_data(profile: ProfileData, soup: BeautifulSoup, html: str) -> None:
    """Extract Pikabu-specific data"""

    # Rating
    rating_pattern = r'(?i)(рейтинг)\s*[:\-]?\s*([0-9\s,.+-]+)'
    rating_match = re.search(rating_pattern, html)
    if rating_match:
        profile.extra["rating"] = rating_match.group(2).strip()


# Utility functions for batch processing
async def enrich_profiles_batch(urls: List[str], http: HttpClient,
                                max_concurrent: int = 5) -> List[ProfileData]:
    """Process multiple profiles concurrently"""

    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_url(url: str) -> ProfileData:
        async with semaphore:
            platform, username = classify_url(url)
            if platform and username:
                return await enrich_profile(platform, url, username, http)
            else:
                return ProfileData(platform="unknown", username="", url=url,
                                   extra={"error": "Could not classify URL"})

    tasks = [process_url(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=True)


def filter_profiles(profiles: List[ProfileData],
                    min_followers: Optional[int] = None,
                    verified_only: bool = False,
                    platforms: Optional[List[str]] = None) -> List[ProfileData]:
    """Filter profiles based on criteria"""

    filtered = []
    for profile in profiles:
        if isinstance(profile, Exception):
            continue

        # Check minimum followers
        if min_followers and (not profile.followers or profile.followers < min_followers):
            continue

        # Check verification status
        if verified_only and not profile.verified:
            continue

        # Check platform filter
        if platforms and profile.platform not in platforms:
            continue

        filtered.append(profile)

    return filtered