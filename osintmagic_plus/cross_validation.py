
from __future__ import annotations
from typing import Dict, List, Tuple
from collections import defaultdict

def cross_validate(hits) -> Dict[str, int]:
    # Считает, сколько уникальных доменов подтверждают одинаковые сущности
    email2doms = defaultdict(set)
    user2doms = defaultdict(set)
    phone2doms = defaultdict(set)

    for h in hits:
        dom = h.url.split("/")[2].lower() if "//" in h.url else h.url
        if h.email: email2doms[h.email].add(dom)
        if h.username: user2doms[h.username].add(dom)
        if h.phone: phone2doms[h.phone].add(dom)

    score = defaultdict(int)
    for h in hits:
        base = 0
        if h.email: base += len(email2doms[h.email]) - 1
        if h.username: base += len(user2doms[h.username]) - 1
        if h.phone: base += len(phone2doms[h.phone]) - 1
        score[h.url] = max(0, base)
    return score
