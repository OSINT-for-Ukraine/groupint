import networkx as nx
import plotly.graph_objects as go

def draw_graph(group_data, n=None):
    connection = n if n else None
    G = nx.Graph()
    node_ids = []
    
    # Add nodes to the graph
    for data in group_data:
        node = data.get("n")
        label = str(node.labels)
        node_prop = dict(node)
        node_id = node_prop.pop("id")
        if label == ":User":
            G.add_node(node_id, **node_prop)
            node_ids.append(node_id)
    
    # Add edges to the graph only if there is at least one connection
    for i in range(len(node_ids) - 1):
        for j in range(i + 1, len(node_ids)):
            first = node_ids[i]
            second = node_ids[j]
            if connection:
                G.add_edge(first, second, relationship=connection)
            else:
                G.add_edge(first, second)
    
    # Remove nodes with no connections
    isolated_nodes = [node for node in G.nodes if G.degree(node) == 0]
    G.remove_nodes_from(isolated_nodes)
    
    # Compute the layout
    pos = nx.spring_layout(G)
    
    # Extract edge positions
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    # Extract node positions and texts
    node_x = []
    node_y = []
    node_text = []
    for node, properties in G.nodes.data():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        if "username" in properties:
            label = str(properties["username"])
        else:
            label = str(node)
        node_text.append(label)

    node_trace = go.Scatter(
<<<<<<< HEAD
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        hoverinfo='text',
=======
        x=node_x,
        y=node_y,
        mode="markers",
        hoverinfo="text",
>>>>>>> 8236b8637b092d1b37e5fc7b6e56ef3da307fbfe
        marker=dict(
            showscale=True,
            colorscale="YlGnBu",
            size=10,
            colorbar=dict(
                thickness=15,
                title="Node Connections",
                xanchor="left",
                titleside="right",
            ),
        ),
    )

<<<<<<< HEAD
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
=======
    node_trace.text = node_text

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title="<br>Users cluster",
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[
                dict(showarrow=False, xref="paper", yref="paper", x=0.005, y=-0.002)
            ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        ),
    )
>>>>>>> 8236b8637b092d1b37e5fc7b6e56ef3da307fbfe

    return fig, G
