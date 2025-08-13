from __future__ import annotations
import asyncio, logging, json
from dataclasses import asdict
from pathlib import Path
from tqdm.asyncio import tqdm_asyncio
from rich.table import Table
from rich.console import Console

from .config import AppConfig
from .models import PersonQuery, SourceResult, ReportData
from .cache import CacheStore
from .http import HttpClient
from .ranking import score_result
from .graph import build_graph, export_graph
from .report import render_report
from ..providers.brave import BraveProvider
from ..social_extractors import classify_url, enrich_profile
from ..providers.common import extract_metadata

console = Console()

class QueryPlanner:
    """Формирует разнообразный пул запросов под ограничение бюджета."""
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def build(self) -> list[dict]:
        terms = []
        q = PersonQuery(
            name=self.cfg.name,
            phone=self.cfg.phone,
            email=self.cfg.email,
            username=self.cfg.username,
            birth_year=self.cfg.birth_year,
            city=self.cfg.city,
            country=self.cfg.country,
        )
        base_terms = []
        if q.name:
            base_terms += [q.name, f"{q.name} {q.city or ''}".strip(), f"{q.name} {q.country or ''}".strip()]
        if q.username:
            base_terms += [q.username, f"\"{q.username}\" site:github.com", f"\"{q.username}\" site:vk.com"]
        if q.email:
            base_terms += [q.email, f"\"{q.email}\""]
        if q.phone:
            base_terms += [q.phone, f"\"{q.phone}\""]
        # Уникализируем
        seen = set()
        for t in base_terms:
            if t and t not in seen:
                terms.append(t); seen.add(t)

        # Тематическое разнообразие (социальные/форумы/медиа/ПБД)
        themed = [
            f"site:github.com {q.username or q.name or ''}",
            f"site:vk.com {q.username or q.name or ''}",
            f"site:instagram.com {q.username or q.name or ''}",
            f"site:linkedin.com/in {q.name or ''}",
            f"site:stackoverflow.com/users {q.username or q.name or ''}",
            f"site:medium.com {q.username or q.name or ''}",
            f"site:reddit.com {q.username or q.name or ''}",
            f"site:t.me {q.username or q.name or ''}",
        ]
        for t in themed:
            if t.strip() and t not in seen:
                terms.append(t); seen.add(t)

        # Ограничение по бюджету
        budget = self.cfg.max_requests_budget
        return [{"q": t} for t in terms][:budget]

async def run_pipeline(cfg: AppConfig):
    cache = CacheStore(cfg.cache_dir, ttl=cfg.cache_ttl)
    data = ReportData(query={
        "name": cfg.name, "phone": cfg.phone, "email": cfg.email,
        "username": cfg.username, "birth_year": cfg.birth_year,
        "city": cfg.city, "country": cfg.country
    })

    provider_objs = []
    if "brave" in cfg.providers:
        provider_objs.append(BraveProvider(api_key=cfg.brave_key))

    async with HttpClient(cfg.timeout, tor_socks=cfg.tor_socks if cfg.tor else None,
                          http_proxy=cfg.http_proxy, https_proxy=cfg.https_proxy) as http:
        planner = QueryPlanner(cfg)
        tasks_plan = planner.build()

        sem = asyncio.Semaphore(cfg.max_concurrent)
        results: list[SourceResult] = []

        async def worker(task):
            async with sem:
                for prov in provider_objs:
                    res = await prov.search(task["q"], http=http, cache=cache, fresh=cfg.fresh)
                    if not res:
                        continue
                    for item in res:
                        # догружаем метаданные страницы по URL (title/last_modified) при возможности
                        meta = await extract_metadata(item.url, http=http)
                        if meta:
                            item.title = item.title or meta.get("title")
                            item.extra.update({k:v for k,v in meta.items() if k != "title"})
                        item.score = score_result(item, cfg.name, cfg.city, cfg.country)
                        results.append(item)

        await tqdm_asyncio.gather(*[worker(t) for t in tasks_plan], desc="Поиск")

    # Ранжирование и классфикация на профили/упоминания

    # Классификация и обогащение социальных профилей
    # 1) Выделяем кандидатов по URL-паттернам
    profile_candidates: list[tuple[SourceResult, str, str]] = []
    for r in results:
        platform, uname = classify_url(r.url)
        if platform:
            # Переназначаем провайдера на платформу
            r.provider = platform
            if uname and not r.username:
                r.username = uname
            profile_candidates.append((r, platform, uname or (r.username or "")))

    # 2) Обогащаем профили платформ-спецификой (аватар, подписчики, активность, навыки и т.п.)
    async def _enrich_one(r: SourceResult, platform: str, uname: str):
        try:
            fields = await enrich_profile(platform, r.url, uname, http)
            for k,v in (fields or {}).items():
                if k == "extra":
                    r.extra.update(v or {})
                else:
                    setattr(r, k, v)
            # Пересчитываем скор с учётом новых полей
            r.score = score_result(r, cfg.name, cfg.city, cfg.country)
        except Exception:
            pass
        return r

    if profile_candidates:
        await tqdm_asyncio.gather(*[_enrich_one(r, p, u) for (r,p,u) in profile_candidates],
                                  desc="Обогащение профилей")

    # 3) Классификация на профили / упоминания
    results.sort(key=lambda r: r.score, reverse=True)
    profiles = [r for r in results if any(classify_url(r.url))]  # URL похож на профиль
    mentions = [r for r in results if r not in profiles]

    # Немного ограничим объём, чтобы отчёт был компактным
    top_profiles = profiles[:200]
    data.profiles = top_profiles
    data.mentions = mentions[:400]

    # 4) Активность во времени для тепловой карты
    activity = []
    for r in results:
        ts = r.last_active_at or (r.extra.get("published_at") if isinstance(r.extra, dict) else None)
        if ts:
            activity.append({"ts": ts, "url": r.url, "source": r.provider})
    data.activity = activity

    # 5) Граф связей
    data.graph = build_graph(top_profiles, data.leaks)

    # Добавляем emails/phones как узлы и рёбра от профилей
    try:
        existing_ids = set(n.get("id") for n in data.graph.get("nodes", []))
        def add_node(nid, label):
            if nid not in existing_ids:
                data.graph.setdefault("nodes", []).append({"id": nid, "label": label})
                existing_ids.add(nid)
        def add_edge(a, b):
            data.graph.setdefault("edges", []).append({"from": a, "to": b})

        for r in top_profiles:
            pid = f"profile:{r.provider}:{r.username or r.url}"
            add_node("person", "Person")
            add_node(pid, r.username or r.title or r.url)
            add_edge("person", pid)
            extras = r.extra or {}
            for em in extras.get("emails", []):
                eid = f"email:{em}"
                add_node(eid, em)
                add_edge(pid, eid)
            for ph in extras.get("phones", []):
                phid = f"phone:{ph}"
                add_node(phid, ph)
                add_edge(pid, phid)
    except Exception:
        pass


    # Рендер отчёта
    out_dir = cfg.report_out_dir
    render_report(json.loads(json.dumps(asdict(data), default=str)),  # make JSON-serializable
                  templates_dir=Path(__file__).resolve().parent.parent / "templates",
                  static_dir=Path(__file__).resolve().parent.parent / "static",
                  out_dir=out_dir)

    export_graph(data.graph, out_dir)

    # Итоговая таблица в консоли
    table = Table(title="Топ профилей")
    table.add_column("Провайдер"); table.add_column("URL"); table.add_column("Счёт")
    for r in top_profiles[:10]:
        table.add_row(r.provider, r.url, f"{r.score:.1f}")
    console.print(table)

    console.log(f"Готово. Отчёт: {out_dir / 'index.html'}")