
from __future__ import annotations
import asyncio, aiohttp, random, datetime, logging, math
from typing import Dict, List, Tuple
from tqdm import tqdm

from .config import Config
from .rate import AsyncRateLimiter, DomainRateLimiter
from .cache import TTLCache
from .async_fetcher import fetch_and_parse, build_session
from .models import SearchHit, Dossier, Entities
from .ranking import score_hit, confidence_label
from .cross_validation import cross_validate
from .username_filter import looks_bad
from .name_match import translit_variants
from .report_html import build_report
from .graph_build import build_graph, export_graph
from .sources_db import load_sources, categorize_url
from .providers import pick_providers, ProviderBase
from .nlp_local import extract_keywords, sentiment_stub

log = logging.getLogger("osint.orchestrator")

def _adapt_items(items, provider_name: str) -> List[SearchHit]:
    out: List[SearchHit] = []
    if not items:
        return out
    for it in items:
        url = (it.get("link") or it.get("url") or "").strip()
        if not url:
            continue
        out.append(SearchHit(
            title=(it.get("title") or url)[:300],
            url=url,
            snippet=(it.get("snippet") or it.get("description") or "")[:600],
            provider=provider_name,
            category=it.get("category"),
            username=it.get("username"),
            email=it.get("email"),
            phone=it.get("phone"),
        ))
    return out

async def _call_provider(query: str, prov: ProviderBase) -> List[SearchHit]:
    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, lambda: prov.search(query, limit=10))
    except Exception as e:
        log.debug("Provider %s failed: %s", getattr(prov, "NAME", "?"), e)
        return []
    return _adapt_items(raw, prov.NAME)

def _build_queries(subject: str, city: str|None, country: str|None, username: str|None) -> List[str]:
    variants = translit_variants(subject)
    geo = " ".join([x for x in [city, country] if x])
    queries: List[str] = []
    for v in variants:
        base = f'{v} {geo}'.strip()
        if base: queries.append(base)
        queries += [f'{base} профиль', f'{base} email', f'{base} github', f'{base} site:linkedin.com']
        queries.append(f'"{v}" site:twitter.com')
        queries.append(f'"{v}" site:x.com')
        queries.append(f'"{v}" site:instagram.com')
        if username:
            queries.append(f'{v} "{username}"')
            queries.append(f'"{username}" {geo}')
    # dedupe while preserving order
    seen = set(); uniq = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            uniq.append(q); seen.add(q)
    return uniq[:50]

def _build_heatmap(hits: List[SearchHit]):
    counts = {}
    for h in hits:
        dt = h.last_activity or h.created_at
        if not dt: 
            continue
        if isinstance(dt, str):
            try:
                from dateutil import parser
                dt = parser.parse(dt)
            except Exception:
                continue
        key = (dt.year, dt.month)
        counts[key] = counts.get(key, 0) + 1
    items = [{"y": y, "m": m, "v": v} for (y,m), v in sorted(counts.items())]
    return items

async def orchestrate(subject: str, city: str|None, country: str|None, birth_year: int|None,
                      phone: str|None, username: str|None, cfg: Config,
                      report_path: str|None = None, graph_path: str|None = None,
                      provider_selection: str = "all"):
    cache = TTLCache(ttl_sec=cfg.cache_ttl_sec); await cache.init()
    global_limiter = AsyncRateLimiter(cfg.rps)
    domain_limiter = DomainRateLimiter(default_rps=max(cfg.rps/2, 0.5))
    session = build_session(cfg)

    providers: List[ProviderBase] = pick_providers(provider_selection)
    prov_names = [getattr(p, "NAME", "unknown") for p in providers]
    log.info("Провайдеры: %s", ", ".join(prov_names) if prov_names else "<нет доступных>")
    if not providers:
        log.warning("Нет доступных провайдеров (проверь .env и --providers). Отчёт будет пустым.")

    # --- запросы ---
    queries = _build_queries(subject, city, country, username)
    log.info("Сгенерировано запросов: %d", len(queries))

    # --- конкурентный запуск ---
    hits: List[SearchHit] = []
    async def run_one(q: str, prov: ProviderBase):
        # global and per-domain pacing to reduce fingerprinting
        await global_limiter.wait(jitter_ms=cfg.jitter_ms)
        return await _call_provider(q, prov)

    tasks = [asyncio.create_task(run_one(q, p))
             for q in queries
             for p in providers]

    with tqdm(total=len(tasks), desc="Search", unit="task", disable=len(tasks)==0) as pbar:
        for t in asyncio.as_completed(tasks):
            try:
                chunk = await t
                hits.extend(chunk)
            finally:
                pbar.update(1)

    log.info("Получено сырых результатов: %d", len(hits))

    # Категоризация по домену
    srcdb = load_sources()
    for h in hits:
        if not getattr(h, 'category', None):
            h.category = categorize_url(h.url, srcdb) or h.category

    # --- мета-fetch + NLP ---
    meta_limit = int(getattr(cfg, "max_meta", 80))
    top_for_fetch = hits[:min(meta_limit, len(hits))]
    meta_sema = asyncio.Semaphore(int(getattr(cfg, "meta_concurrency", 8)))

    async def fetch_one(h: SearchHit):
        await meta_sema.acquire()
        try:
            await global_limiter.wait(1.0, jitter_ms=cfg.jitter_ms)
            await domain_limiter.wait(h.url, jitter_ms=cfg.jitter_ms)  # пер-доменный темп
            meta = await asyncio.wait_for(
                fetch_and_parse(h.url, cfg, session),
                timeout=cfg.timeout + 5
            )
            # ... перенос метаданных в h ...
            return h
        finally:
            meta_sema.release()

    meta_tasks = [asyncio.create_task(fetch_one(h)) for h in top_for_fetch]
    with tqdm(total=len(meta_tasks), desc="Meta", unit="page", disable=len(meta_tasks)==0) as pbar2:
        done: List[SearchHit] = []
        for t in asyncio.as_completed(meta_tasks):
            try:
                h = await t
                done.append(h)
            finally:
                pbar2.update(1)

    url_to_hit = {h.url: h for h in done}
    for i, h in enumerate(hits):
        if h.url in url_to_hit:
            hits[i] = url_to_hit[h.url]

    # --- фильтрация юзернеймов ---
    hits = [h for h in hits if not (h.username and looks_bad(h.username))]

    # --- кросс-валидация ---
    cross = cross_validate(hits)

    # --- скоринг/группировка ---
    for h in hits:
        h.score = score_hit(h, subject)
    hits.sort(key=lambda x: x.score, reverse=True)

    groups: Dict[str, List[SearchHit]] = {}
    for h in hits:
        sec = h.category or "Прочее"
        groups.setdefault(sec, []).append(h)

    dossier = Dossier(
        subject=subject, city=city, country=country, birth_year=birth_year, phone=phone, username=username,
        generated_iso=datetime.datetime.utcnow().isoformat(),
        groups=groups, entities=Entities(),
        providers_used=prov_names,
    )
    dossier.confidence = {h.url: confidence_label(h.score, cross.get(h.url, 0)) for h in hits}
    dossier.activity_heatmap = _build_heatmap(hits)

    if report_path:
        flat = [h for lst in groups.values() for h in lst]
        build_report(dossier, report_path, flat)

    if graph_path:
        G = build_graph(subject, [h for lst in groups.values() for h in lst])
        export_graph(G, graph_path)

    await session.close()
    return dossier
