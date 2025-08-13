
from __future__ import annotations
import json, os
from typing import List
from .models import Dossier

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "report_assets"))

def _read_asset(name: str) -> str:
    path = os.path.join(ASSETS_DIR, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def build_report(dossier: Dossier, out_html: str, hits_flat: list):
    css = _read_asset("style.css")
    js = _read_asset("report.js")
    data = {
        "subject": dossier.subject,
        "city": dossier.city,
        "country": dossier.country,
        "birth_year": dossier.birth_year,
        "phone": dossier.phone,
        "username": dossier.username,
        "generated_iso": dossier.generated_iso,
        "groups": {k:[h.__dict__ for h in v] for k,v in dossier.groups.items()},
        "confidence": dossier.confidence,
        "activity_heatmap": getattr(dossier, "activity_heatmap", []),
    }
    html = f"""<!doctype html>
<html lang='ru'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>OSINT Dossier — {dossier.subject}</title>
  <style>{css}</style>
</head>
<body>
  <header>
    <h1 id='subject'></h1>
    <div class='meta' id='meta'></div>
  </header>
  <main>
    <section id='cards' class='card'></section>
    <section id='timeline' class='card'><h2>Временная шкала</h2></section>
    <section id='heatmap' class='card'><h2>Тепловая карта активности</h2></section>
    <section id='graph' class='card'><h2>Граф связей</h2></section>
  </main>
  <script>window.__OSINT_DATA__ = {json.dumps(data, ensure_ascii=False)};</script>
  <script>{js}</script>
</body>
</html>"""
    os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    return out_html
