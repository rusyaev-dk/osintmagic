from __future__ import annotations
from .normalization import fuzzy_match, looks_like_garbage_username

def score_result(res, target_name: str | None, city: str | None, country: str | None) -> float:
    score = 0.0
    if res.full_name and target_name:
        score += fuzzy_match(res.full_name, target_name) / 2.0  # 0..50
    if res.username and target_name:
        score += fuzzy_match(res.username, target_name) / 4.0    # 0..25
    if looks_like_garbage_username(res.username or ""):
        score -= 30
    if res.last_active_at:
        score += 10  # свежесть
    if res.followers:
        score += min(20, res.followers / 10000.0)  # максимум +20
    if res.verified:
        score += 10
    return max(0.0, score)
