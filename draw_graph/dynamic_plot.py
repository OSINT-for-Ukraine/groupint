from pyvis.network import Network


def get_graph(G):
    nt = Network(height='750px', width='100%', directed=False, font_color='black')
    nt.repulsion()
    nt.show_buttons(filter_=['physics'])
    all_node_attributes = G.nodes.data()
    for node in all_node_attributes:
        nt.add_node(n_id=node[0], label=str(node[0]), title=str(node[1]))
    for edge in G.edges():
        nt.add_edge(edge[0], edge[1])
    graph_html = nt.generate_html()
    return graph_html, nt


def create_paginated_graph(G, nodes_per_page=10, page_number=1):
    start_index = (page_number - 1) * nodes_per_page
    end_index = start_index + nodes_per_page

    nt = Network(notebook=True, height='750px', width='100%', directed=False)

    for node in list(G.nodes())[start_index:end_index]:
        nt.add_node(node)

    for edge in list(G.edges())[start_index:end_index]:
        nt.add_edge(edge[0], edge[1])

    graph_html = nt.generate_html()
    return graph_html
