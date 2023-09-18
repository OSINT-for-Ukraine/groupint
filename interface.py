import asyncio
import subprocess
import webbrowser
from socket import socket, SOCK_STREAM, AF_INET
import requests
import streamlit as st
from telethon import TelegramClient

from draw_graph.plot import draw_graph
from main import DataManager
from streamlit_utils.text import query_hint
from draw_graph.dynamic_plot import get_graph

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


async def is_user_authorized(client):
    return await client.is_user_authorized()


async def create_client(phone_number, API_ID, API_HASH):
    client_tg = TelegramClient(phone_number, API_ID, API_HASH)
    await client_tg.connect()
    return client_tg


async def generate_otp(client_tg, phone_number):
    result = await client_tg.send_code_request(
        phone=phone_number
    )
    phone_hash = result.phone_code_hash
    return client_tg, phone_hash


def run_until_complete(coro):
    return st.session_state.event_loop.run_until_complete(coro)


async def verify_otp(client, phone, secret_code, phone_hash):
    await client.connect()
    await client.sign_in(
        phone=phone,
        code=secret_code,
        phone_code_hash=phone_hash,
    )


phone_number_input = st.text_input(label='Phone numer', help='Input your phone number')
api_id_input = st.text_input(label='Api id', help='Input your api id')
api_hash_input = st.text_input(label='Api hash', help='Input your api hash')
create_client_btn = st.button(label='Create Telegram client')
if create_client_btn and phone_number_input and api_id_input and api_hash_input:
    client = run_until_complete(
        create_client(phone_number_input, api_id_input, api_hash_input)
    )
    st.session_state.client = client
if not hasattr(st.session_state, 'auth') and hasattr(st.session_state, 'client'):
    if not run_until_complete(is_user_authorized(st.session_state.client)):
        st.session_state.auth = False
    else:
        st.session_state.auth = True

if hasattr(st.session_state, 'auth'):
    if not st.session_state.auth:
        if create_client_btn and phone_number_input and api_id_input and api_hash_input:
            if not run_until_complete(is_user_authorized(client)):
                st.session_state.client, st.session_state.phone_hash = run_until_complete(
                    generate_otp(client_tg=client,
                                 phone_number=phone_number_input)
                )
            else:
                st.session_state.client = client
            st.session_state.phone = phone_number_input
            st.session_state.api_id = api_id_input
            st.session_state.api_hash = api_hash_input

button_verify_code = None
secret_code_input = None
if hasattr(st.session_state, 'auth'):
    if not st.session_state.auth:
        st.write('**Enter your secret code to authorize**')
        secret_code_input = st.text_input(label='Secret code', help='Input your secret code')
        st.session_state.secret_code = secret_code_input
        button_verify_code = st.button(label='Verify secret code')
if hasattr(st.session_state, 'auth'):
    if (not st.session_state.auth) and button_verify_code and st.session_state.secret_code:
        run_until_complete(verify_otp(st.session_state.client,
                                      st.session_state.phone,
                                      st.session_state.secret_code,
                                      st.session_state.phone_hash))
        st.session_state.auth = True
group_id = None
button_clicked_load = None
if hasattr(st.session_state, 'auth'):
    if st.session_state.auth:
        group_id = st.text_input(label='Input target group', help='id or group name')
        button_clicked_load = st.button(label='Parse group')
if group_id and button_clicked_load:
    run_until_complete(
        DataManager.load_data(client=st.session_state.client, channel=group_id))
    st.write('**The data was loaded! Choose your params and click "show graph"**')
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
        group_data = run_until_complete(DataManager.get_data(query_filter, int(arg)))
        fig, G = draw_graph(group_data, int(arg))
    else:
        group_data = run_until_complete(DataManager.get_data(query_filter))
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
