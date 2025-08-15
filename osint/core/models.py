from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from datetime import datetime

@dataclass
class PersonQuery:
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    username: str | None = None
    birth_year: int | None = None
    city: str | None = None
    country: str | None = None

@dataclass
class SourceResult:
    provider: str
    url: str
    title: str | None = None
    snippet: str | None = None
    username: str | None = None
    full_name: str | None = None
    followers: int | None = None
    registered_at: datetime | None = None
    last_active_at: datetime | None = None
    verified: bool | None = None
    media_preview: str | None = None
    score: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

@dataclass
class ReportData:
    query: dict
    profiles: list[SourceResult] = field(default_factory=list)
    mentions: list[SourceResult] = field(default_factory=list)
    leaks: list[dict] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    activity: list[dict] = field(default_factory=list)  # timestamps for heatmap
    graph: dict = field(default_factory=lambda: {"nodes": [], "edges": []})


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    provider: str
    score: float = 0.0
    category: Optional[str] = None
    saved_path: Optional[str] = None
    content_excerpt: Optional[str] = None
    og_image: Optional[str] = None
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)

@dataclass
class Entities:
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    usernames: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)

@dataclass
class Dossier:
    subject: str
    city: Optional[str]
    country: Optional[str]
    birth_year: Optional[int]
    phone: Optional[str]
    username: Optional[str]
    generated_iso: str
    groups: Dict[str, List[SearchHit]]
    entities: Entities
    confidence: Dict[str, str] = field(default_factory=dict)  # url -> "High"/"Medium"/"Low"
    providers_used: List[str] = field(default_factory=list)



@dataclass
class ProfileData:
    """Structured profile data container"""
    platform: str
    username: str
    url: str
    title: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    posts_count: Optional[int] = None
    joined_at: Optional[str] = None
    last_active_at: Optional[str] = None
    location: Optional[str] = None
    verified: bool = False
    bio: Optional[str] = None
    website: Optional[str] = None
    extra: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}