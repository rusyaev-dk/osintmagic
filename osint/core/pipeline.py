# pipeline.py
from __future__ import annotations
import asyncio
import logging
import time
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict, Counter

from tqdm.asyncio import tqdm_asyncio
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .config import AppConfig
from .models import PersonQuery, SourceResult, ReportData, ProfileData  # используем ваши dataclass'ы
from .cache import CacheStore
from .http import HttpClient
from .ranking import score_result
from .graph import export_graph
from .report import render_report
from ..providers.brave import BraveProvider
from ..social_extractors import classify_url, enrich_profile
from ..providers.common import extract_metadata

console = Console()
logger = logging.getLogger(__name__)

@dataclass
class QueryStrategy:
    base_queries: List[str] = field(default_factory=list)
    platform_queries: List[str] = field(default_factory=list)
    leak_queries: List[str] = field(default_factory=list)
    deep_queries: List[str] = field(default_factory=list)
    priority_weight: float = 1.0

@dataclass
class PipelineMetrics:
    start_time: float = field(default_factory=time.time)
    queries_executed: int = 0
    profiles_found: int = 0
    mentions_found: int = 0
    enrichment_success_rate: float = 0.0
    cache_hit_rate: float = 0.0
    errors: List[str] = field(default_factory=list)

    def duration(self) -> float:
        return time.time() - self.start_time

class AdvancedQueryPlanner:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def build_strategies(self, query: PersonQuery) -> List[QueryStrategy]:
        strategies = []
        strategies.append(self._build_base_strategy(query))
        strategies.append(self._build_platform_strategy(query))
        strategies.append(self._build_leak_strategy(query))
        if getattr(self.cfg, "deep_search", False):
            strategies.append(self._build_deep_strategy(query))
        return strategies

    def _build_base_strategy(self, q: PersonQuery) -> QueryStrategy:
        queries: List[str] = []
        if q.name:
            queries.extend([
                q.name,
                f'"{q.name}"',
                f"{q.name} {q.city or ''}".strip(),
                f"{q.name} {q.country or ''}".strip(),
            ])
        if q.username:
            queries.extend([
                q.username,
                f'"{q.username}"',
                f"username:{q.username}",
                f"user:{q.username}",
            ])
        if q.email:
            queries.extend([
                q.email,
                f'"{q.email}"',
                q.email.split("@")[0],
            ])
        if q.phone:
            queries.extend([
                q.phone,
                f'"{q.phone}"',
                re.sub(r"[\s\-\(\)]", "", q.phone),
            ])
        return QueryStrategy(base_queries=self._deduplicate(queries), priority_weight=1.0)

    def _build_platform_strategy(self, q: PersonQuery) -> QueryStrategy:
        queries: List[str] = []
        platforms = [
            "github.com","linkedin.com","twitter.com","instagram.com","facebook.com",
            "vk.com","ok.ru","telegram.org","t.me","youtube.com","tiktok.com",
            "reddit.com","medium.com","habr.com","pikabu.ru","zen.yandex.ru","rutube.ru"
        ]
        terms = [t for t in [q.name, q.username, q.email] if t]
        for host in platforms:
            for term in terms:
                queries.extend([f"site:{host} {term}", f'site:{host} "{term}"'])
        if q.username:
            queries.extend([
                f"site:github.com/{q.username}",
                f"site:linkedin.com/in/{q.username}",
                f"site:twitter.com/{q.username}",
                f"site:instagram.com/{q.username}",
                f"site:vk.com/{q.username}",
                f"site:t.me/{q.username}",
            ])
        return QueryStrategy(platform_queries=self._deduplicate(queries), priority_weight=0.9)

    def _build_leak_strategy(self, q: PersonQuery) -> QueryStrategy:
        queries: List[str] = []
        leak_sites = [
            "haveibeenpwned.com","leakcheck.io","dehashed.com",
            "intelx.io","scylla.so","breachdirectory.org"
        ]
        terms = [t for t in [q.email, q.username, q.phone] if t]
        for site in leak_sites:
            for term in terms:
                queries.append(f"site:{site} {term}")
        for term in terms:
            queries.extend([
                f"{term} database leak",
                f"{term} data breach",
                f"{term} breach",
                f"{term} dump",
            ])
        return QueryStrategy(leak_queries=self._deduplicate(queries), priority_weight=0.8)

    def _build_deep_strategy(self, q: PersonQuery) -> QueryStrategy:
        queries: List[str] = []
        if q.name and q.city:
            queries.append(f'"{q.name}" "{q.city}"')
        if q.name and q.birth_year:
            queries.append(f'"{q.name}" {q.birth_year}')
        if q.username and q.city:
            queries.append(f'"{q.username}" "{q.city}"')
        if q.name and " " in q.name:
            parts = q.name.split()
            if len(parts) >= 2:
                queries.extend([
                    f'"{parts[-1]} {parts[0]}"',
                    f'"{parts[0][0]}. {parts[-1]}"',
                    f'"{parts[0]} {parts[-1][0]}."',
                ])
        if q.name:
            queries.extend([
                f'"{q.name}" -wikipedia -facebook',
                f'"{q.name}" -linkedin -instagram',
            ])
        return QueryStrategy(deep_queries=self._deduplicate(queries), priority_weight=0.6)

    def _deduplicate(self, items: List[str]) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []
        for it in items:
            s = it.strip()
            if s and s not in seen:
                out.append(s)
                seen.add(s)
        return out

    def build_prioritized_tasks(self, query: PersonQuery) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        for strat in self.build_strategies(query):
            all_q = strat.base_queries + strat.platform_queries + strat.leak_queries + strat.deep_queries
            for qtxt in all_q:
                tasks.append({
                    "query": qtxt,
                    "priority": strat.priority_weight,
                    "strategy_type": (
                        "base" if qtxt in strat.base_queries else
                        "platform" if qtxt in strat.platform_queries else
                        "leak" if qtxt in strat.leak_queries else
                        "deep" if qtxt in strat.deep_queries else "unknown"
                    )
                })
        tasks.sort(key=lambda x: x["priority"], reverse=True)
        return tasks[: getattr(self.cfg, "max_requests_budget", 100)]

class EnhancedResultProcessor:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def process_results(self, results: List[SourceResult]) -> Tuple[List[SourceResult], List[SourceResult]]:
        dedup_url = self._deduplicate_by_url(results)
        dedup_content = self._deduplicate_by_content(dedup_url)
        profiles, mentions = self._classify_results(dedup_content)
        profiles = self._cluster_similar_profiles(profiles)
        mentions = self._cluster_similar_mentions(mentions)
        profiles = [r for r in profiles if r.score >= 0.3]
        mentions = [r for r in mentions if r.score >= 0.2]
        return profiles, mentions

    def _normalize_url(self, url: str) -> str:
        import urllib.parse
        p = urllib.parse.urlparse(url.lower())
        q = urllib.parse.parse_qs(p.query)
        tracking = {"utm_source","utm_medium","utm_campaign","fbclid","gclid","ref"}
        q2 = {k:v for k,v in q.items() if k not in tracking}
        query = urllib.parse.urlencode(q2, doseq=True)
        path = p.path.rstrip("/")
        return urllib.parse.urlunparse((p.scheme,p.netloc,path,p.params,query,""))

    def _deduplicate_by_url(self, results: List[SourceResult]) -> List[SourceResult]:
        seen: set[str] = set()
        out: List[SourceResult] = []
        for r in results:
            key = self._normalize_url(r.url)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    def _deduplicate_by_content(self, results: List[SourceResult]) -> List[SourceResult]:
        def fp(r: SourceResult) -> str:
            content = " ".join(filter(None, [r.title or "", r.snippet or "", r.username or ""])).lower()
            content = re.sub(r"[^\w\s]", " ", content)
            words = content.split()
            sig = [w for w in words if len(w) > 3][:10]
            return " ".join(sorted(sig))

        fingerprints: Dict[str, SourceResult] = {}
        out: List[SourceResult] = []
        for r in results:
            key = fp(r)
            if key and key not in fingerprints:
                fingerprints[key] = r
                out.append(r)
            elif key in fingerprints:
                existing = fingerprints[key]
                existing.score = max(existing.score, r.score)
                (existing.extra).update(r.extra or {})
        return out

    def _classify_results(self, results: List[SourceResult]) -> Tuple[List[SourceResult], List[SourceResult]]:
        profiles: List[SourceResult] = []
        mentions: List[SourceResult] = []
        for r in results:
            platform, username = classify_url(r.url)
            if platform:
                r.provider = platform  # у вас provider: str обязателен — заполняем
                if username and not r.username:
                    r.username = username
                profiles.append(r)
            else:
                mentions.append(r)
        return profiles, mentions

    def _cluster_similar_profiles(self, profiles: List[SourceResult]) -> List[SourceResult]:
        clusters: Dict[Tuple[str,str], List[SourceResult]] = defaultdict(list)
        for p in profiles:
            key = (p.username or "unknown", p.provider or "unknown")
            clusters[key].append(p)
        out: List[SourceResult] = []
        for items in clusters.values():
            if len(items) == 1:
                out.extend(items)
            else:
                best = max(items, key=lambda x: x.score)
                for other in items:
                    if other is not best:
                        best.extra.update(other.extra or {})
                out.append(best)
        return out

    def _cluster_similar_mentions(self, mentions: List[SourceResult]) -> List[SourceResult]:
        import urllib.parse
        domains: Dict[str, List[SourceResult]] = defaultdict(list)
        for m in mentions:
            domains[urllib.parse.urlparse(m.url).netloc].append(m)
        out: List[SourceResult] = []
        for arr in domains.values():
            arr.sort(key=lambda x: x.score, reverse=True)
            out.extend(arr[:5])
        return out

class BatchEnrichmentProcessor:
    def __init__(self, cfg: AppConfig, http: HttpClient):
        self.cfg = cfg
        self.http = http

    async def enrich_profiles_batch(self, profiles: List[SourceResult]) -> List[SourceResult]:
        groups: Dict[str, List[SourceResult]] = defaultdict(list)
        for p in profiles:
            groups[p.provider].append(p)

        enriched: List[SourceResult] = []
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      BarColumn(), TaskProgressColumn()) as progress:
            for platform, chunk in groups.items():
                task = progress.add_task(f"Обогащение {platform}", total=len(chunk))
                batch_size = min(10, getattr(self.cfg, "max_concurrent", 5))
                for i in range(0, len(chunk), batch_size):
                    batch = chunk[i:i+batch_size]
                    results = await asyncio.gather(
                        *[self._enrich_single(p) for p in batch],
                        return_exceptions=True
                    )
                    for orig, res in zip(batch, results):
                        if isinstance(res, Exception):
                            logger.warning(f"Failed to enrich {orig.url}: {res}")
                            enriched.append(orig)
                        else:
                            enriched.append(res)
                        progress.advance(task)
        return enriched

    async def _enrich_single(self, profile: SourceResult) -> SourceResult:
        try:
            platform, username = classify_url(profile.url)
            if not platform or not username:
                return profile
            data = await enrich_profile(platform, profile.url, username, self.http)
            if isinstance(data, ProfileData):
                profile.title = data.title or profile.title
                profile.full_name = data.full_name or profile.full_name
                profile.username = data.username or profile.username
                profile.followers = data.followers or profile.followers
                profile.verified = data.verified or profile.verified
                if data.last_active_at:
                    profile.last_active_at = data.last_active_at  # строка ISO допустима в вашей модели
                profile.extra.update(data.extra or {})
            elif isinstance(data, dict):
                for k, v in data.items():
                    if k == "extra":
                        profile.extra.update(v or {})
                    elif hasattr(profile, k) and v is not None:
                        setattr(profile, k, v)
            profile.score = score_result(profile, self.cfg.name, self.cfg.city, self.cfg.country)
        except Exception as e:
            logger.warning(f"Enrichment failed for {profile.url}: {e}")
        return profile

class EnhancedGraphBuilder:
    @staticmethod
    def build_enhanced_graph(profiles: List[SourceResult], query: PersonQuery) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_ids: set[str] = set()

        person_id = "person:main"
        person_label = query.name or query.username or "Target Person"
        nodes.append({"id": person_id, "label": person_label, "type": "person", "level": 0, "size": 30})
        node_ids.add(person_id)

        for p in profiles:
            pid = f"profile:{p.provider}:{p.username or p.url}"
            if pid not in node_ids:
                nodes.append({
                    "id": pid, "label": p.title or p.username or p.url, "type": "profile",
                    "platform": p.provider, "level": 1, "size": 20,
                    "followers": getattr(p, "followers", None), "verified": getattr(p, "verified", False),
                    "score": p.score
                })
                node_ids.add(pid)
                edges.append({"from": person_id, "to": pid, "type": "owns_profile", "weight": p.score})

            extra = p.extra or {}
            for email in extra.get("emails", []):
                eid = f"email:{email}"
                if eid not in node_ids:
                    nodes.append({"id": eid, "label": email, "type": "email", "level": 2, "size": 15})
                    node_ids.add(eid)
                edges.append({"from": pid, "to": eid, "type": "has_email"})
            for phone in extra.get("phones", []):
                phid = f"phone:{phone}"
                if phid not in node_ids:
                    nodes.append({"id": phid, "label": phone, "type": "phone", "level": 2, "size": 15})
                    node_ids.add(phid)
                edges.append({"from": pid, "to": phid, "type": "has_phone"})
            loc = getattr(p, "location", None) or extra.get("location")
            if loc:
                lid = f"location:{loc}"
                if lid not in node_ids:
                    nodes.append({"id": lid, "label": loc, "type": "location", "level": 2, "size": 12})
                    node_ids.add(lid)
                edges.append({"from": pid, "to": lid, "type": "located_in"})

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "profiles": sum(1 for n in nodes if n["type"] == "profile"),
                "emails": sum(1 for n in nodes if n["type"] == "email"),
                "phones": sum(1 for n in nodes if n["type"] == "phone"),
                "locations": sum(1 for n in nodes if n["type"] == "location"),
            }
        }

async def run_enhanced_pipeline(cfg: AppConfig) -> PipelineMetrics:
    metrics = PipelineMetrics()
    cache = CacheStore(Path(cfg.cache_dir), ttl=getattr(cfg, "cache_ttl", 86400))

    query = PersonQuery(
        name=cfg.name, phone=cfg.phone, email=cfg.email, username=cfg.username,
        birth_year=cfg.birth_year, city=cfg.city, country=cfg.country
    )

    planner = AdvancedQueryPlanner(cfg)
    processor = EnhancedResultProcessor(cfg)

    providers: List[Any] = []
    if "brave" in getattr(cfg, "providers", []):
        providers.append(BraveProvider(api_key=cfg.brave_key))

    console.log(f"🚀 Запуск пайплайна для: {query.name or query.username or query.email}")

    async with HttpClient(
        cfg.timeout,
        tor_socks=getattr(cfg, "tor_socks", None) if getattr(cfg, "tor", False) else None,
        http_proxy=getattr(cfg, "http_proxy", None),
        https_proxy=getattr(cfg, "https_proxy", None),
    ) as http:

        console.log("📋 Планирование запросов...")
        tasks = planner.build_prioritized_tasks(query)
        metrics.queries_executed = len(tasks)
        console.log(f"📊 Запланировано {len(tasks)} запросов")

        console.log("🔍 Выполнение поисковых запросов...")
        semaphore = asyncio.Semaphore(getattr(cfg, "max_concurrent", 5))
        all_results: List[SourceResult] = []

        async def execute_query(task: Dict[str, Any]) -> None:
            async with semaphore:
                qtext = task["query"]
                try:
                    for prov in providers:
                        results: List[SourceResult] = await prov.search(
                            qtext, http=http, cache=cache, fresh=getattr(cfg, "fresh", False)
                        )
                        if not results:
                            continue
                        for r in results:
                            try:
                                meta = await extract_metadata(r.url, http=http)
                                if meta:
                                    r.title = r.title or meta.get("title")
                                    r.extra.update({k:v for k,v in meta.items() if k != "title"})
                                # приоритезация и стратегия — можно сохранить в extra
                                r.extra.setdefault("priority", task.get("priority", 1.0))
                                r.extra.setdefault("strategy_type", task.get("strategy_type", "unknown"))
                                r.score = score_result(r, cfg.name, cfg.city, cfg.country)
                            except Exception as e:
                                logger.warning(f"Metadata extraction failed for {r.url}: {e}")
                        all_results.extend(results)
                except Exception as e:
                    metrics.errors.append(f"Query '{qtext}': {e}")
                    logger.error(f"Query execution failed: {e}")

        await tqdm_asyncio.gather(*[execute_query(t) for t in tasks], desc="Поисковые запросы")
        console.log(f"✅ Найдено {len(all_results)} результатов")

        console.log("🔄 Обработка результатов...")
        profiles, mentions = processor.process_results(all_results)
        metrics.profiles_found = len(profiles)
        metrics.mentions_found = len(mentions)
        console.log(f"👤 Профили: {len(profiles)}, 📝 Упоминания: {len(mentions)}")

        if profiles:
            console.log("🎯 Обогащение профилей...")
            enricher = BatchEnrichmentProcessor(cfg, http)
            profiles = await enricher.enrich_profiles_batch(profiles)
            profiles.sort(key=lambda p: p.score, reverse=True)

        top_profiles = profiles[: getattr(cfg, "max_profiles_in_report", 100)]
        top_mentions = mentions[: getattr(cfg, "max_mentions_in_report", 200)]

        console.log("🕸️ Построение графа связей...")
        graph = EnhancedGraphBuilder.build_enhanced_graph(top_profiles, query)

        # 7. Сбор активности
        activity_data: List[Dict[str, Any]] = []
        platform_activity: Counter[str] = Counter()
        for p in top_profiles:
            last_active = p.last_active_at or (p.extra or {}).get("last_active_at")
            activity_data.append({
                "provider": p.provider,
                "username": p.username,
                "full_name": p.full_name,
                "followers": p.followers,
                "verified": p.verified,
                "last_active_at": last_active,
                "score": p.score,
                "url": p.url,
            })
            if p.provider:
                platform_activity[p.provider] += 1

        # 8. Метрики enrichment/cache
        try:
            if top_profiles:
                enriched_ok = 0
                for p in top_profiles:
                    if any([
                        p.full_name, p.followers, p.verified,
                        p.last_active_at, bool(p.extra)
                    ]):
                        enriched_ok += 1
                metrics.enrichment_success_rate = round(enriched_ok / max(1, len(top_profiles)), 3)
            else:
                metrics.enrichment_success_rate = 0.0
        except Exception as e:
            logger.warning(f"Failed to compute enrichment metrics: {e}")
            metrics.enrichment_success_rate = 0.0

        try:
            st = cache.stats() if hasattr(cache, "stats") else {"hits": 0, "misses": 0}
            total = st["hits"] + st["misses"]
            metrics.cache_hit_rate = round(st["hits"] / total, 3) if total else 0.0
        except Exception as e:
            logger.warning(f"Failed to read cache stats: {e}")
            metrics.cache_hit_rate = 0.0

        # 9. Экспорт графа и отчёта
        console.log("📦 Экспорт артефактов...")

        # директории
        out_dir = Path(getattr(cfg, "output_dir", "output")).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        # пути к шаблонам/статике (pipeline.py лежит в osint/core, значит на уровень выше — пакет osint)
        pkg_root = Path(__file__).resolve().parents[1]
        templates_dir = pkg_root / "templates"
        static_dir = pkg_root / "static"

        try:
            graph_path = out_dir / "graph.json"
            export_graph(graph, graph_path)
            console.log(f"🗺️  Граф сохранён: {graph_path}")
        except Exception as e:
            logger.warning(f"Graph export failed: {e}")
            metrics.errors.append(f"Graph export failed: {e}")

        try:
            # Соберём ReportData и превратим в dict
            report = ReportData(
                query=asdict(query),  # dict
                profiles=top_profiles,  # список dataclass -> asdict ниже всё развернёт рекурсивно
                mentions=top_mentions,
                activity=activity_data,
                graph=graph
            )
            data = asdict(report)  # ВАЖНО: render_report ждёт dict

            # вызов по вашей сигнатуре: (data, templates_dir, static_dir, out_dir)
            render_report(data, templates_dir, static_dir, out_dir)
            console.log(f"📄 HTML-отчёт сгенерирован: {out_dir / 'index.html'}")

        except Exception as e:
            logger.error(f"Report render failed: {e}")
            metrics.errors.append(f"Report render failed: {e}")

        console.log(
            f"🏁 Готово за {metrics.duration():.2f}s | "
            f"Запросов: {metrics.queries_executed} | "
            f"Профилей: {metrics.profiles_found} | "
            f"Упоминаний: {metrics.mentions_found}"
        )

    return metrics

async def run_pipeline(cfg: AppConfig):
    """Совместимая обёртка для CLI: вызывает расширенный пайплайн."""
    return await run_enhanced_pipeline(cfg)