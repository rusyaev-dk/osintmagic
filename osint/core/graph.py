from __future__ import annotations
import networkx as nx
from pathlib import Path

def build_graph(profiles: list, leaks: list) -> dict:
    G = nx.Graph()
    # Узел персоны
    G.add_node("person", label="Person", type="person")

    # Профили
    for p in profiles:
        nid = f"profile:{p.provider}:{p.username or p.url}"
        G.add_node(nid, label=p.username or p.title or p.url, type="profile", provider=p.provider)
        G.add_edge("person", nid)

    # Утечки
    for leak in leaks:
        lid = f"leak:{leak.get('source')}:{leak.get('id','?')}"
        G.add_node(lid, label=leak.get("source"), type="leak")
        G.add_edge("person", lid)

    data = {
        "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes()],
        "edges": [{"from": u, "to": v} for u, v in G.edges()],
    }
    return data

def export_graph(graph_data: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    # GEXF
    try:
        G = nx.Graph()
        for n in graph_data["nodes"]:
            G.add_node(n["id"], **{k:v for k,v in n.items() if k!="id"})
        for e in graph_data["edges"]:
            G.add_edge(e["from"], e["to"])
        nx.write_gexf(G, out_dir / "graph.gexf")
        nx.write_graphml(G, out_dir / "graph.graphml")
        try:
            import pydot
            nx.drawing.nx_pydot.write_dot(G, out_dir / "graph.dot")
        except Exception:
            pass
    except Exception:
        pass
