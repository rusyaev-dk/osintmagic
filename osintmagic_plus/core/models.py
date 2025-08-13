from dataclasses import dataclass, field
from typing import Any
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
