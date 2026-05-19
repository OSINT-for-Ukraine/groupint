"""Build graphs from User RELATED relationships (shared groups)."""

import networkx as nx
import plotly.graph_objects as go


def _node_label(props: dict) -> str:
    username = props.get("username")
    if username:
        return str(username)
    alias = props.get("alias")
    if alias:
        return str(alias)
    return str(props.get("id", "?"))


def _node_hover(props: dict) -> str:
    parts = [_node_label(props)]
    if props.get("telegram_url"):
        parts.append(str(props["telegram_url"]))
    if props.get("id") is not None:
        parts.append(f"id={props['id']}")
    return "<br>".join(parts)


def _node_props(props: dict) -> dict:
    return {
        "label": _node_label(props),
        "hover": _node_hover(props),
        "username": props.get("username"),
        "alias": props.get("alias"),
        "telegram_url": props.get("telegram_url"),
        "id": props.get("id"),
    }


def draw_common_groups_graph(group_data: list[dict], n: int | None = None):
    G = nx.Graph()
    for row in group_data:
        u1 = row.get("u1")
        u2 = row.get("u2")
        rel = row.get("r")
        if u1 is None or u2 is None:
            continue
        p1 = dict(u1)
        p2 = dict(u2)
        n1 = p1.get("id", str(u1.identity))
        n2 = p2.get("id", str(u2.identity))
        G.add_node(n1, **_node_props(p1))
        G.add_node(n2, **_node_props(p2))
        edge_attrs = dict(rel) if rel is not None else {}
        shared = edge_attrs.get("group") or edge_attrs.get("gr") or []
        strength = edge_attrs.get("strength", len(shared) if shared else 1)
        G.add_edge(n1, n2, strength=strength, shared_groups=shared)

    if G.number_of_nodes() == 0:
        raise ValueError(
            "No RELATED user edges found. Scrape members from multiple groups, "
            "then click **Graph by common groups**."
        )

    pos = nx.spring_layout(G, k=1.2, seed=42)
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    node_x, node_y, hover_text, labels = [], [], [], []
    for node, props in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        labels.append(props.get("label") or str(node))
        hover_text.append(props.get("hover") or str(node))

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=labels,
        textposition="top center",
        hovertext=hover_text,
        hoverinfo="text",
        marker=dict(size=12, color="#2ca02c"),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title="Users by shared groups (RELATED)",
        showlegend=False,
        margin=dict(b=20, l=20, r=20, t=40),
    )
    return fig, G
