import asyncio
import subprocess
import webbrowser
from socket import socket, SOCK_STREAM, AF_INET
import requests
import streamlit as st
from core.tg_api_connector import create_client, generate_otp, get_all_participants, get_groups_of_which_user_is_part_of, get_participants_based_on_messages, is_user_authorized, verify_otp
from draw_graph.plot import draw_graph
from main import DataManager
from streamlit_utils.text import query_hint
from draw_graph.dynamic_plot import get_graph

import hmac


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the passward is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False


if not check_password():
    st.stop()  # Do not continue if check_password is not True.



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


# result = await get_groups_of_which_user_is_part_of(client_tg, "total_ordering", True)
# print(result)

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
model_for_user_groups_exist = None
button_clicked_query = None
button_clicked_relationship = None
button_clicked_from_messages = None
n_of_messages_input = None
users=[]
if hasattr(st.session_state, 'auth'):
    if st.session_state.auth:
        group_id = st.text_input(label='Input target group', help='id or group name')
        button_clicked_load = st.button(label='Get the user from the group')
if group_id and button_clicked_load:
    # TODO here we should store the info we retrieved from telesint bot
    # to a neo4j db
    #     run_until_complete(
    #    DataManager.load_data(client=st.session_state.client, channel=group_id)) 
    users = run_until_complete(
        get_all_participants(st.session_state.client,group_id))
        # participants = self.client.iter_participants(entity=channel, limit=limit, search=key_word)
        # DataManager.get_users(client=st.session_state.client, channel=group_id))
    st.write(f"**{len(users)} Users were extracted from the group. If you expect more users we will try to extract them from the messages.**")
    st.session_state.users=users
n_of_messages_input = st.text_input(label="How many messages should be parsed?",help="integer")
button_clicked_from_messages = st.button(label='Extract users based on messages')


if button_clicked_from_messages:
        print("entered")
        users_from_messages = run_until_complete(
            get_participants_based_on_messages(st.session_state.client,group_id,int(n_of_messages_input))
        )
        st.write(f"{len(users_from_messages)} users extracted")
        st.session_state.users=users + users_from_messages
        st.write("**Now we need will query the telesint db for info about other groups they're part of**")  
    
    
    # st.write(st.session_state.users)

button_clicked_query = st.button(label='Query for the groups that users are part of')

if button_clicked_query:
    # run_until_complete(
#            DataManager.get_data()
#       )
    for user in st.session_state.users[:100]:
        groups = run_until_complete(
             get_groups_of_which_user_is_part_of(st.session_state.client,str(user[0]),dry_run=False)
        )
        st.write("adding user")
        run_until_complete(
            DataManager.add_user(user,groups)
        )
    st.write("**Groups were found. Now based on them we will create relations between users.**")

button_clicked_relationship = st.button(label='Create relationships')

if button_clicked_relationship:
        run_until_complete(
            DataManager.create_relationships()
        )
    # st.write('**The data was loaded! Choose your params and click "show graph"**')
    # groups = run_until_complete(get_groups_of_which_user_is_part_of(st.session_state.client, user_id, dry_run=True))
    # st.write(groups)
    # st.write("implement the model for the user who're related by groups which theý're part of")
# FETCH DATA WINDOW

# st.divider()
# st.write('**Fetch graph from storage**')
# col1, col2 = st.columns(2)
# with col1:
#     query_filter = st.text_input(label='Input filter to create graph', help='You could find hint in the sidebar')
# with col2:
#     arg = st.text_input(label='Input integer argument if necessary')

# button_clicked_fetch = st.button(label='Show graph')


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

# if button_clicked_fetch and not model_for_user_groups_exist:
#     st.write("we are missing proper model to represent this data")
# elif button_clicked_fetch and model_for_user_groups_exist:
#     if arg:
#         group_data = run_until_complete(DataManager.get_data(query_filter, int(arg)))
#         fig, G = draw_graph(group_data, int(arg))
#     else:
#         group_data = run_until_complete(DataManager.get_data(query_filter))
#         fig, G = draw_graph(group_data)
#     st.button(label='Static', on_click=show_static, args=[fig])
#     interact_button = st.button(label='Interact', on_click=show_interact, args=[G])
#     server_button = st.button(label='On server', on_click=show_on_server, args=[G])


# RUN SERVER WITH INTERACTIVE GRAPH
def is_port_open(port):
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(1)
    result = s.connect_ex(('localhost', port))
    s.close()
    return result == 0


if not is_port_open(8050):
    subprocess.run(['python', 'draw_graph/server_plot.py'])
