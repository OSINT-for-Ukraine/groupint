import plotly.graph_objects as go
import networkx as nx


def draw_graph(group_data, n=None):
    connection = n if n else None
    G = nx.Graph()
    node_ids = []
    for data in group_data:
        node = data.get('n')
        label = str(node.labels)
        node_prop = dict(node)
        node_id = node_prop.pop('id')
        if label == ':User':
            G.add_node(node_id, **node_prop)
            node_ids.append(node_id)
    i = 0
    j = i + 1
    while i < len(node_ids) - 1:
        while j < len(node_ids):
            first = node_ids[i]
            second = node_ids[j]
            if connection:
                G.add_edge(first, second, relationship=connection)
            else:
                G.add_edge(first, second)
            j += 1
        i += 1
        j = i + 1
    pos = nx.spring_layout(G)
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines')

    node_x = []
    node_y = []
    node_text = []
    for node,properties in G.nodes.data():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        if "username" in properties:
            label = str(properties["username"])
        elif "id" in properties:
            label = str(properties["id"])
        else:
            label = "Unknown"
        node_text.append(label + "(" + str(node) + ")")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        marker=dict(
            showscale=True,
            colorscale='YlGnBu',
            size=10,
            colorbar=dict(
                thickness=15,
                title='Node Connections',
                xanchor='left',
                titleside='right'
            )
        )
    )

    node_trace.text = node_text

    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title='<br>Users cluster',
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        annotations=[dict(
                            showarrow=False,
                            xref="paper", yref="paper",
                            x=0.005, y=-0.002)],
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                    )

    return fig, G
