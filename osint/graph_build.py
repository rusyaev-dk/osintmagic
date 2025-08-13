
from __future__ import annotations
import networkx as nx

def build_graph(subject: str, hits):
    G = nx.MultiDiGraph()
    subj = f"person:{subject}"
    G.add_node(subj, label=subject, type="person")

    for h in hits:
        dom = h.url.split("/")[2] if "//" in h.url else h.url
        node_profile = f"profile:{h.url}"
        G.add_node(node_profile, label=h.title or h.url, type="profile", domain=dom)
        G.add_edge(subj, node_profile, label=h.category or "hit")

        if h.email:
            e = f"email:{h.email}"
            G.add_node(e, label=h.email, type="email")
            G.add_edge(node_profile, e, label="mentions")
        if h.username:
            u = f"user:{h.username}"
            G.add_node(u, label=h.username, type="username")
            G.add_edge(node_profile, u, label="username")
        if h.phone:
            p = f"phone:{h.phone}"
            G.add_node(p, label=h.phone, type="phone")
            G.add_edge(node_profile, p, label="mentions")
    return G

def export_graph(G, path: str):
    if path.endswith(".gexf"):
        nx.write_gexf(G, path)
    elif path.endswith(".graphml"):
        nx.write_graphml(G, path)
    elif path.endswith(".dot") or path.endswith(".gv"):
        nx.drawing.nx_pydot.write_dot(G, path)
    else:
        nx.write_gexf(G, path + ".gexf")
