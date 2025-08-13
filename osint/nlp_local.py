
from __future__ import annotations
from typing import List, Dict
# Все NLP – локально. Модули опциональны.
try:
    import spacy
except Exception:
    spacy = None

def load_pipelines():
    nlp_ru = nlp_en = None
    if spacy:
        try:
            nlp_ru = spacy.load("ru_core_news_lg")  # установить отдельно
        except Exception:
            nlp_ru = None
        try:
            nlp_en = spacy.load("en_core_web_lg")
        except Exception:
            nlp_en = None
    return nlp_ru, nlp_en

def extract_keywords(texts: List[str], top_k: int = 20) -> List[str]:
    # Простая эвристика (TF-like); для серьёзного качества подключите KeyBERT/embedding-модели
    from collections import Counter
    import re
    text = " ".join(texts).lower()
    tokens = re.findall(r"[a-zа-яё0-9]{3,}", text, flags=re.I)
    stop = set(["и","в","на","для","это","как","the","and","for","you","with","что","она","они","оно"]) 
    tokens = [t for t in tokens if t not in stop]
    common = Counter(tokens).most_common(top_k)
    return [w for w,_ in common]

def sentiment_stub(texts: List[str]) -> str:
    # Заглушка: оценка тональности (нужна модель). Возвращаем neutral.
    return "neutral"
