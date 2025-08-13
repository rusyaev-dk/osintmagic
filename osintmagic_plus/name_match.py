
from __future__ import annotations
from typing import Tuple, List
from unidecode import unidecode
try:
    from rapidfuzz.fuzz import ratio, partial_ratio
except Exception:
    from difflib import SequenceMatcher
    def ratio(a,b): return int(100*SequenceMatcher(None, a, b).ratio())
    def partial_ratio(a,b): return ratio(a,b)

def normalize(s: str) -> str:
    return unidecode(s).lower().strip()

def translit_variants(full_name: str, synonyms: List[Tuple[str,str]] = None) -> List[str]:
    base = [full_name]
    n = normalize(full_name)
    parts = [p for p in n.replace("/"," ").replace("_"," ").split() if p]
    base.extend(parts)
    if synonyms:
        for a,b in synonyms:
            a,b = normalize(a), normalize(b)
            if a in n: base.append(n.replace(a,b))
            if b in n: base.append(n.replace(b,a))
    return sorted(set(base))

def name_similarity(a: str, b: str) -> float:
    A, B = normalize(a), normalize(b)
    return max(ratio(A,B), partial_ratio(A,B)) / 100.0
