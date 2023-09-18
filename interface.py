import asyncio
import json
import subprocess
import traceback
import webbrowser
from socket import socket, SOCK_STREAM, AF_INET
from telethon import utils, errors, functions, types
import requests
import streamlit as st
from telethon import TelegramClient

from draw_graph.plot import draw_graph
from main import DataManager
from streamlit_utils.text import query_hint
from draw_graph.dynamic_plot import get_graph, create_paginated_graph

# SLIDE BAR
with st.sidebar.expander('Query hint'):
    st.markdown(query_hint)



# loop = asyncio.new_event_loop()
# asyncio.set_event_loop(loop)
# LOAD DATA WINDOW
st.write('**Load data into storage**')
phone_number_input = st.text_input(label='Phone numer', help='Input your phone number')
api_id_input = st.text_input(label='Api id', help='Input your api id')
api_hash_input = st.text_input(label='Api hash', help='Input your api hash')


def write_secret_code(secret_code):
    f = open("secret.txt", "a")
    f.truncate(0)
    f.write(secret_code)
    f.close()


def read_secret_code_callback():
    print("LOG:Enter secret code")
    f = open("secret.txt", "r")
    return f.read()


class MyTelegramClient(TelegramClient):
    async def send_code_request(
            self: 'TelegramClient',
            phone: str,
            *,
            force_sms: bool = False,
            _retry_count: int = 0) -> 'types.auth.SentCode':

        if force_sms:
            force_sms = False

        result = None
        print(f"LOG 1:{phone}")
        print(f"LOG 2:{self._phone}")
        phone = utils.parse_phone(phone) or self._phone
        print(f"LOG 3:{phone}")
        phone_hash = self._phone_code_hash.get(phone)
        print(f"LOG 4:{phone_hash}")
        if not phone_hash:
            print(f"LOG 4.1:{phone_hash}")
            try:
                print(f"LOG 4.2:{self}")
                print(f"LOG 4.2.1:{self(functions.auth.SendCodeRequest(phone, self.api_id, self.api_hash, types.CodeSettings()))}")
                result = await self(functions.auth.SendCodeRequest(
                    phone, self.api_id, self.api_hash, types.CodeSettings()))
                print(f"LOG 4.3:{phone_hash} {self.api_id} {self.api_hash} {result}")

            except errors.AuthRestartError:
                print(f"LOG:AuthRestartError {traceback.format_exc()}")
                if _retry_count > 2:
                    raise
                return await self.send_code_request(
                    phone, force_sms=force_sms, _retry_count=_retry_count+1)
            print(f"LOG 5:{result}, print 3")
            # TODO figure out when/if/how this can happen
            if isinstance(result, types.auth.SentCodeSuccess):
                raise RuntimeError('logged in right after sending the code')

            # If we already sent a SMS, do not resend the code (hash may be empty)
            if isinstance(result.type, types.auth.SentCodeTypeSms):
                force_sms = False

            # phone_code_hash may be empty, if it is, do not save it (#1283)
            if result.phone_code_hash:
                self._phone_code_hash[phone] = phone_hash = result.phone_code_hash
        else:
            force_sms = True

        self._phone = phone

        if force_sms:
            print(f"LOG 6:{self._phone}, {phone}, {phone_hash}")
            try:
                result = await self(
                    functions.auth.ResendCodeRequest(phone, phone_hash))
            except errors.PhoneCodeExpiredError:
                print(f"LOG 7:{self._phone}, {phone}, {phone_hash}")
                print(traceback.format_exc())
                if _retry_count > 2:
                    raise
                self._phone_code_hash.pop(phone, None)
                self._log[__name__].info(
                    "Phone code expired in ResendCodeRequest, requesting a new code"
                )
                return await self.send_code_request(
                    phone, force_sms=False, _retry_count=_retry_count+1)
            print(f"LOG 8:{self._phone}, {phone}, {phone_hash}")
            if isinstance(result, types.auth.SentCodeSuccess):
                raise RuntimeError('logged in right after resending the code')

            self._phone_code_hash[phone] = result.phone_code_hash

        return result

def create_client(phone_number, API_ID, API_HASH):
    client_tg = MyTelegramClient(phone_number, API_ID, API_HASH)
    client_tg.connect()
    return client_tg

async def print_test():
    print("LOG:print_test 1")
    print("LOG:print_test 2")

async def generate_otp(client_tg, phone_number):
    await print_test()
    print(f"LOG:Enter secret code 1: {phone_number}:{client_tg}")
    result = await client_tg.send_code_request(
        phone=phone_number
    )
    # task = asyncio.create_task(result)
    phone_hash = result.phone_code_hash
    print("LOG:Enter secret code 2")
    return client_tg, phone_hash


async def verify_otp(client, phone, secret_code, phone_hash):
    print("LOG:verify_otp 1")
    await client.connect()
    print("LOG:verify_otp 2")
    await client.sign_in(
        phone=phone,
        code=secret_code,
        phone_code_hash=phone_hash,
    )
    print("LOG:verify_otp 3")

button_request_code = st.button(label='Request secret code')


if button_request_code and phone_number_input and api_id_input and api_hash_input:
    client = create_client(phone_number_input, api_id_input, api_hash_input)

    st.session_state.client, st.session_state.phone_hash = asyncio.run(generate_otp(client_tg=client,
                                                                                    phone_number=phone_number_input))
    st.session_state.phone = phone_number_input
    st.session_state.api_id = api_id_input
    st.session_state.api_hash = api_hash_input

secret_code_input = st.text_input(label='Secret code', help='Input your secret code')
st.session_state.secret_code = secret_code_input
button_verify_code = st.button(label='Verify secret code')

if button_verify_code and st.session_state.secret_code:
    verify_otp(st.session_state.client,
               st.session_state.phone,
               st.session_state.secret_code,
               st.session_state.phone_hash)

group_id = st.text_input(label='Input target group', help='id or group name')
button_clicked_load = st.button(label='Parse group')
if group_id and button_clicked_load:
    asyncio.run(DataManager.load_data(group_id, st.session_state.api_id, st.session_state.api_hash,
                                      st.session_state.phone, st.session_state.bot_token))
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
