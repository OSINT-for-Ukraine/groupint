"""Build graphs from Group ENDORSES relationships."""

import networkx as nx
import plotly.graph_objects as go


def _group_hover(props: dict, label: str) -> str:
    parts = [label]
    if props.get("telegram_url"):
        parts.append(str(props["telegram_url"]))
    if props.get("id"):
        parts.append(f"id={props['id']}")
    return "<br>".join(parts)


def draw_endorsement_graph(group_data: list[dict], n: int | None = None):
    G = nx.DiGraph()
    for row in group_data:
        g1 = row.get("g1")
        g2 = row.get("g2")
        rel = row.get("rel")
        if g1 is None or g2 is None:
            continue
        src = dict(g1).get("id", str(g1.identity))
        tgt = dict(g2).get("id", str(g2.identity))
        p1 = dict(g1)
        p2 = dict(g2)
        title_src = p1.get("title") or src
        title_tgt = p2.get("title") or tgt
        G.add_node(
            src,
            title=title_src,
            label=title_src,
            hover=_group_hover(p1, title_src),
        )
        G.add_node(
            tgt,
            title=title_tgt,
            label=title_tgt,
            hover=_group_hover(p2, title_tgt),
        )
        edge_attrs = dict(rel) if rel is not None else {}
        G.add_edge(src, tgt, **edge_attrs)

    if G.number_of_nodes() == 0:
        raise ValueError("No ENDORSES relationships found. Extract endorsements first.")

    pos = nx.spring_layout(G, k=1.5, seed=42)
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    node_x, node_y, node_text, hover_text = [], [], [], []
    for node, props in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        label = props.get("label") or props.get("title") or str(node)
        node_text.append(label)
        hover_text.append(props.get("hover") or label)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        hovertext=hover_text,
        hoverinfo="text",
        marker=dict(size=14, color="#1f77b4"),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title="Group endorsement graph (ENDORSES)",
        showlegend=False,
        margin=dict(b=20, l=20, r=20, t=40),
    )
    return fig, G
