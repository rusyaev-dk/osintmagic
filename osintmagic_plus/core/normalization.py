import re, unicodedata
from rapidfuzz import fuzz

def normalize_name(n: str) -> str:
    n = unicodedata.normalize("NFKC", n or "").strip()
    n = re.sub(r"\s+", " ", n)
    return n

def translit_variants(first_last: str) -> list[str]:
    # Очень простой набор вариантов транслитерации, можно расширять
    variants = {first_last}
    # Примеры: Alisher <-> Алишер, Morgenshtern <-> Моргенштерн
    repl = {
        "sh": "ш", "Sh": "Ш",
        "zh": "ж", "Zh": "Ж",
        "ch": "ч", "Ch": "Ч",
        "yo": "ё", "Yo": "Ё",
        "ya": "я", "Ya": "Я",
        "yu": "ю", "Yu": "Ю",
        "kh": "х", "Kh": "Х",
        "a": "а", "o": "о", "e": "е", "i": "и", "r": "р", "m": "м", "g": "г", "n": "н", "t":"т", "s":"с", "h":"х",
    }
    for latin, cyr in repl.items():
        variants.update({first_last.replace(latin, cyr), first_last.replace(cyr, latin)})
    return list(variants)

def fuzzy_match(a: str, b: str) -> int:
    return fuzz.token_set_ratio((a or "").lower(), (b or "").lower())

def looks_like_garbage_username(u: str) -> bool:
    u = (u or "").lower()
    if re.fullmatch(r"\d{6,}", u):
        return True
    if u in {"qwerty","asdfgh","admin","user","test"}:
        return True
    if re.fullmatch(r"[a-z_]{1,}\d{3,}", u) and any(k in u for k in ["user","test","admin"]):
        return True
    if set(u) == {"_"}:
        return True
    return False
