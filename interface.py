import asyncio
import json
import subprocess
import webbrowser
from socket import socket, SOCK_STREAM, AF_INET

import requests
import streamlit as st
from draw_graph.plot import draw_graph
from main import DataManager
from streamlit_utils.text import query_hint
from draw_graph.dynamic_plot import get_graph, create_paginated_graph

# SLIDE BAR
with st.sidebar.expander('Query hint'):
    st.markdown(query_hint)
# LOAD DATA WINDOW
st.write('**Load data into storage**')
group_id = st.text_input(label='Input target group', help='id or group name')
button_clicked_load = st.button(label='Parse group')
if group_id and button_clicked_load:
    asyncio.run(DataManager.load_data(group_id))
# FETCH DATA WINDOW
st.divider()
st.write('**Fetch graph from storage**')
col1, col2 = st.columns(2)
with col1:
    query_filter = st.text_input(label='Input filter to create graph', help='You could find hint in the sidebar')
with col2:
    arg = st.text_input(label='Input integer argument if necessary')

button_clicked_fetch = st.button(label='Show graph')


def show_static(fig):
    st.plotly_chart(fig)
    st.divider()


def show_interact(G):
    graph_html, nt = get_graph(G)
    st.components.v1.html(graph_html, width=1000, height=750)
    st.divider()


def show_on_server(G):
    all_node_attributes = G.nodes.data()
    elements = []
    for node in all_node_attributes:
        elements.append({'data': {'id': node[0], 'label': node[1].pop('username'), **node[1]}})
    for edge in G.edges():
        source, target = edge
        elements.append({'data': {'source': str(source), 'target': str(target)}})
    dash_app_url = 'http://127.0.0.1:8050/'
    response = requests.post(url=dash_app_url + 'update-graph', json=elements)
    if response.status_code == 200:
        webbrowser.open_new_tab(dash_app_url)
    else:
        st.write(response.text)


if button_clicked_fetch:
    if arg:
        group_data = asyncio.run(DataManager.get_data(query_filter, int(arg)))
        fig, G = draw_graph(group_data, int(arg))
    else:
        group_data = asyncio.run(DataManager.get_data(query_filter))
        fig, G = draw_graph(group_data)
    st.button(label='Static', on_click=show_static, args=[fig])
    interact_button = st.button(label='Interact', on_click=show_interact, args=[G])
    server_button = st.button(label='On server', on_click=show_on_server, args=[G])


# RUN SERVER WITH INTERACTIVE GRAPH
def is_port_open(port):
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(1)
    result = s.connect_ex(('localhost', port))
    s.close()
    return result == 0


if not is_port_open(8050):
    subprocess.run(['python', 'draw_graph/server_plot.py'])
