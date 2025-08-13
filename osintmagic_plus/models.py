
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime

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
