from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json, shutil

def render_report(data: dict, templates_dir: Path, static_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape()
    )
    tmpl = env.get_template("report.html")
    html = tmpl.render(data=data)

    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # copy static
    dst_static = out_dir / "static"
    if dst_static.exists():
        shutil.rmtree(dst_static)
    shutil.copytree(static_dir, dst_static)
