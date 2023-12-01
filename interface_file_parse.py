import asyncio
import json
import subprocess
import webbrowser
from io import StringIO
from socket import socket, SOCK_STREAM, AF_INET
import requests
import streamlit as st
from core.tg_api_connector import create_client, generate_otp, get_all_participants, get_groups_of_which_user_is_part_of, is_user_authorized, verify_otp
from draw_graph.plot import draw_graph
from main import DataManager
from streamlit_utils.text import query_hint
from draw_graph.dynamic_plot import get_graph


def run_until_complete(coro):
    return st.session_state.event_loop.run_until_complete(coro)


# SLIDE BAR
with st.sidebar.expander('Query hint'):
    st.markdown(query_hint)
try:
    st.session_state.event_loop
except AttributeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    st.session_state.event_loop = loop
# LOAD DATA WINDOW
st.write('**Load data into storage**')

uploaded_file = st.file_uploader("Upload", label_visibility="visible")
if uploaded_file is not None:
    st.session_state.users = json.loads(uploaded_file.getvalue().decode('utf-8'))


button_clicked_query = st.button(label='Load the data')


if button_clicked_query:
    st.write("**Started adding users from file**")
    d1 = {key: value for i, (key, value) in enumerate(st.session_state.users.items()) if i % 100 == 0}
    for user in d1:
        # groups = st.session_state.users[user]["groups"]
        # st.write("adding user")
        run_until_complete(
            DataManager.add_user(st.session_state.users[user])
        )
    st.write("**Groups were found. Now based on them we will create relations between users.**")

button_clicked_relationship = st.button(label='Create relationships')

if button_clicked_relationship:
    st.write("**Creating relationships**")
    run_until_complete(
        DataManager.create_relationships()
    )
    st.write("**Finished creating relationships**")

    # st.write('**The data was loaded! Choose your params and click "show graph"**')
    # groups = run_until_complete(get_groups_of_which_user_is_part_of(st.session_state.client, user_id, dry_run=True))
    # st.write(groups)
    # st.write("implement the model for the user who're related by groups which theý're part of")
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
        if "username" in node[1]:
            label = str(node[1]["username"])
        elif "id" in node[1]:
            label = str(node[1]["id"])
        else:
            label = "Unknown"
        elements.append({'data': {'id': node[0], 'label': label, **node[1]}})
    for edge in G.edges():
        source, target = edge
        elements.append({'data': {'source': str(source), 'target': str(target)}})
    dash_app_url = 'http://127.0.0.1:8050/'
    response = requests.post(url=dash_app_url + 'update-graph', json=elements)
    if response.status_code == 200:
        webbrowser.open_new_tab(dash_app_url)
    else:
        st.write(response.text)

# if button_clicked_fetch and not model_for_user_groups_exist:
#     st.write("we are missing proper model to represent this data")
if button_clicked_fetch:
    if arg:
        group_data = run_until_complete(DataManager.get_data(query_filter, int(arg)))
        # breakpoint()
        fig, G = draw_graph(group_data, int(arg))
    else:
        group_data = run_until_complete(DataManager.get_data(query_filter))
        # breakpoint()
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
