from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv
from slugify import slugify

load_dotenv()

DEPTH_TO_MAX_REQUESTS = {1: 50, 2: 100, 3: 150, 4: 300}

@dataclass
class AppConfig:
    # Query
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    username: str | None = None
    birth_year: int | None = None
    city: str | None = None
    country: str | None = None

    # Runtime
    providers: list[str] = field(default_factory=lambda: ["brave"])
    output_format: str = "html"
    log_level: str = "info"
    timeout: int = 10
    max_concurrent: int = 50
    cache_ttl: int = 86400
    fresh: bool = False
    no_darkweb: bool = False
    tor: bool = False
    depth: int = 1

    # Paths
    base_dir: Path = Path.cwd()
    reports_dir: Path = field(default_factory=lambda: Path.cwd() / "reports")
    logs_dir: Path = field(default_factory=lambda: Path.cwd() / "logs")
    cache_dir: Path = field(default_factory=lambda: Path.cwd() / "cache")

    # Secrets
    brave_key: str | None = "BSAFvyFnGBcWt8IImCnXR_7tgwymtdr"
    hibp_key: str | None = os.getenv("HIBP_API_KEY")
    http_proxy: str | None = os.getenv("HTTP_PROXY")
    https_proxy: str | None = os.getenv("HTTPS_PROXY")
    tor_socks: str | None = os.getenv("TOR_SOCKS")

    @property
    def max_requests_budget(self) -> int:
        return DEPTH_TO_MAX_REQUESTS.get(self.depth, 50)

    @property
    def report_slug(self) -> str:
        q = self.name or self.username or self.email or "report"
        return slugify(q)

    @property
    def report_out_dir(self) -> Path:
        return self.reports_dir / self.report_slug

    @classmethod
    def from_cli_kwargs(cls, kw: dict) -> "AppConfig":
        providers = [p.strip() for p in (kw.get("providers") or "brave").split(",") if p.strip()]
        cfg = cls(
            name=kw.get("name"),
            phone=kw.get("phone"),
            email=kw.get("email"),
            username=kw.get("username"),
            birth_year=kw.get("birth_year"),
            city=kw.get("city"),
            country=kw.get("country"),
            providers=providers,
            output_format=kw.get("output_format", "html"),
            log_level=kw.get("log_level", "info"),
            timeout=int(kw.get("timeout", 10)),
            max_concurrent=int(kw.get("max_concurrent", 50)),
            cache_ttl=int(kw.get("cache_ttl", 86400)),
            fresh=bool(kw.get("fresh", False)),
            no_darkweb=bool(kw.get("no_darkweb", False)),
            tor=bool(kw.get("tor", False)),
            depth=int(kw.get("depth", 1)),
        )
        cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        cfg.logs_dir.mkdir(parents=True, exist_ok=True)
        cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        return cfg
