
from __future__ import annotations
from typing import Dict
from .name_match import name_similarity

def score_hit(hit, subject: str) -> float:
    s = 0.0
    text = f"{hit.title} {hit.snippet} {hit.url}".lower()
    # базовый сигнал по имени
    s += 50.0 * name_similarity(subject, text)
    # бонусы за метаданные
    if hit.og_image: s += 5.0
    if hit.username and hit.username in text: s += 10.0
    if hit.email and hit.email in text: s += 10.0
    if hit.category == "Social": s += 5.0
    # штрафы
    if "404" in text or "not found" in text: s -= 10.0
    return max(0.0, min(100.0, s))

def confidence_label(score: float, cross_score: int) -> str:
    # cross_score — сколько совпадений (email/телефон/username) на разных доменах
    v = score + cross_score * 10
    if v >= 70: return "Высокая уверенность"
    if v >= 45: return "Средняя уверенность"
    return "Возможное совпадение"
