import asyncio
import subprocess
import webbrowser
from socket import AF_INET, SOCK_STREAM, socket
import os
import json
import sys
import csv
from io import StringIO

import requests
import streamlit as st

from core.download_file import download_users_file
from core.login import check_password, run_until_complete
from core.tg_api_connector import (
    create_client,
    generate_otp,
    get_all_participants,
    get_groups_of_which_user_is_part_of,
    get_participants_based_on_messages,
    is_user_authorized,
    verify_otp,
)
from core.upload_file import parse_json_users, parse_xls_users
from draw_graph.dynamic_plot import get_graph
from draw_graph.plot import draw_graph
from main import DataManager
from streamlit_utils.text import query_hint

# ------Check user is authenticated------'''
if not check_password():
    st.stop()  # Do not continue if check_password is not True.

# -----SLIDE BAR----

with st.sidebar.expander("Query hint"):
    st.markdown(query_hint)
try:
    st.session_state.event_loop
except AttributeError:
    st.session_state.event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.event_loop)
#####  LOAD USER DETAILS  🛰️
st.write("****Confirm your details to connect to Telegram scraper**** 🛰️ ")
phone_number_input = st.text_input(label="Phone numer", help="Input your phone number")
api_id_input = st.text_input(label="Api id", help="Input your api id")
api_hash_input = st.text_input(label="Api hash", help="Input your api hash")
create_client_btn = st.button(label="Create Telegram client")


if create_client_btn and phone_number_input and api_id_input and api_hash_input:
    client = run_until_complete(
        create_client(phone_number_input, api_id_input, api_hash_input)
    )
    st.session_state.client = client
if not hasattr(st.session_state, "auth") and hasattr(st.session_state, "client"):
    if not run_until_complete(is_user_authorized(st.session_state.client)):
        st.session_state.auth = False
    else:
        st.session_state.auth = True

if hasattr(st.session_state, "auth"):
    if not st.session_state.auth:
        if create_client_btn and phone_number_input and api_id_input and api_hash_input:
            if not run_until_complete(is_user_authorized(client)):
                st.session_state.client, st.session_state.phone_hash = (
                    run_until_complete(
                        generate_otp(client_tg=client, phone_number=phone_number_input)
                    )
                )
            else:
                st.session_state.client = client
            st.session_state.phone = phone_number_input
            st.session_state.api_id = api_id_input
            st.session_state.api_hash = api_hash_input

button_verify_code = None
secret_code_input = None  # st.write('**The data was loaded! Choose your params and click "show graph"**')                                                                                    │   11 opt.expandtab = true

if hasattr(st.session_state, "auth"):
    if not st.session_state.auth:
        st.write("**Enter your secret code to authorize**")
        secret_code_input = st.text_input(
            label="Secret code", help="Input your secret code"
        )
        st.session_state.secret_code = secret_code_input
        button_verify_code = st.button(label="Verify secret code")
if hasattr(st.session_state, "auth"):
    if (
        (not st.session_state.auth)
        and button_verify_code
        and st.session_state.secret_code
    ):
        run_until_complete(
            verify_otp(
                st.session_state.client,
                st.session_state.phone,
                st.session_state.secret_code,
                st.session_state.phone_hash,
            )
        )
        st.session_state.auth = True


st.markdown(
    """<hr style="height:2px;border:none;color:#222;background-color:#222;" /> """,
    unsafe_allow_html=True,
)


# Load data into storage 📡*

group_id = None
button_clicked_load = None
model_for_user_groups_exist = True
button_clicked_query = None
button_clicked_relationship = None
button_clicked_from_messages = None
n_of_messages_input = None
st.session_state.users = []
uploaded_file = None
offset_date = None
limit_date = None

## UI for loading data into storage
if hasattr(st.session_state, "auth"):
    if st.session_state.auth:
        st.write("**Select target group 🕵️**")
        group_id = st.text_input(
            label="Input name of target group", help="id or group name"
        )
        st.markdown(
            """<hr
            style="height:2px;border:none;color:#222;background-color:#222;" /> """,
            unsafe_allow_html=True,
        )

        st.write("**Extract Data 📡**")
        col1, col2 = st.columns(2)

        with col1:
            button_clicked_load = st.button(label="Get the user from the group")
        with col2:
            fetch_xlsx_btn = st.button(label="Download users as XLSX")

        # Extract users based on messages
        n_of_messages_input = st.text_input(
            label="How many messages should be parsed?", help="integer"
        )
        offset_date = st.date_input(label="Date from messages parsing start")
        limit_date = st.date_input(label="Date where messages parsing stop")
        button_clicked_from_messages = st.button(
            label="Extract users based on messages"
        )

        # Upload JSON file
        uploaded_file = st.file_uploader(
            "Upload file", accept_multiple_files=False, type=["json", "xls", "xlsx"]
        )

        st.markdown(
            """<hr style="height:2px;border:none;color:#222;background-color:#222;" /> """,
            unsafe_allow_html=True,
        )

### Get users from the group logic
if group_id and button_clicked_load:
    # TODO here we should store the info we retrieved from telesint bot to a neo4j db
    st.session_state.users = run_until_complete(get_all_participants(st.session_state.client, group_id))
    st.write(
        f"**{len(st.session_state.users)} Users were extracted from the group. If you expect more users we will try to extract them from the messages.**"
    )


# Download XLSX with users from Telesint
if group_id and fetch_xlsx_btn:
    xlsx_data, xlsx_name = run_until_complete(
        download_users_file(st.session_state.client, group_id, button_index=0)
    )
    st.write(xlsx_name)

# Extract Users from Messages
if button_clicked_from_messages:
    print("entered")
    users_from_messages = run_until_complete(
        get_participants_based_on_messages(
            st.session_state.client, group_id, int(n_of_messages_input), offset_date, limit_date
        )
    )
    st.write(f"{len(users_from_messages)} users extracted")
    st.session_state.users.extend(users_from_messages)
    st.write(
        "**Now we need will query the telesint db for info about other groups they're part of**"
    )


# Upload and extract users from JSON or XLSX
if uploaded_file is not None:
    file_extension = uploaded_file.name.split(".")[-1]
    if file_extension == "json":
        parse_json_users(uploaded_file)
        st.write("Users extracted. You can now graph database")
    elif file_extension in ["xlsx", "xls"]:
        parse_xls_users(uploaded_file)
        st.write("Users extracted. You can now query graph database")

    # Query The Groups that users are part of and create relationships
if hasattr(st.session_state, "auth"):
    if st.session_state.auth:
        st.write("**Query users and create relationships 🕸️**")
        col1, col2 = st.columns(2)
        with col1:
            button_clicked_query = st.button(
                label="Query for the groups that users are part of"
            )
        with col2:
            button_clicked_relationship = st.button(label="Create relationships")


if button_clicked_query:
    # run_until_complete(
    #            DataManager.get_data()
    #       )
    for user in st.session_state.users:
        # user[0] is user's id
        groups = run_until_complete(
            get_groups_of_which_user_is_part_of(
                st.session_state.client, str(user[0]), dry_run=False
            )
        )
        st.write("adding user")
        run_until_complete(DataManager.add_user(user, groups))
    st.write(
        "**Groups were found. Now based on them we will create relations between users.**"
    )

# button_clicked_relationship = st.button(label='Create relationships')

if button_clicked_relationship:
    data_csv = run_until_complete(DataManager.create_relationships())
    st.download_button(
        label="Download csv",
        data=data_csv,
        file_name="graph.csv",
        mime="application/json",
    )
# st.write('**The data was loaded! Choose your params and click "show graph"**')
# groups = run_until_complete(get_groups_of_which_user_is_part_of(st.session_state.client, user_id, dry_run=True))
# st.write(groups)
# st.write("implement the model for the user who're related by groups which theý're part of")
# FETCH DATA WINDOW

query_filter = ""
arg = "0"
target_user = ""
st.divider()
st.write("**Fetch graph from storage**")
col1, col2 = st.columns(2)
with col1:
    query_filter = st.text_input(
        label="Input filter to create graph", help="You could find hint in the sidebar"
    )
with col2:
    arg = st.text_input(label="Input integer argument if necessary")
r2_col1, r2_col2 = st.columns(2)
with r2_col1:
    group_id = st.text_input(
        label="Ignore group", help="You could find hint in the sidebar"
    )
with r2_col2:
    target_user = st.text_input(label="Username of target user")

button_clicked_fetch = st.button(label="Show graph")


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
        elements.append(
            {"data": {"id": node[0], "label": node[1].pop("username", None), **node[1]}}
        )
    for edge in G.edges():
        source, target = edge
        elements.append({"data": {"source": str(source), "target": str(target)}})
    dash_app_url = "http://127.0.0.1:8050/"
    response = requests.post(url=dash_app_url + "update-graph", json=elements)
    if response.status_code == 200:
        webbrowser.open_new_tab(dash_app_url)
    else:
        st.write(response.text)


if button_clicked_fetch and not model_for_user_groups_exist:
    st.write("we are missing proper model to represent this data")
elif button_clicked_fetch and model_for_user_groups_exist:
    kwargs = {"query": query_filter}
    if arg:
        kwargs["n"] = int(arg)
    if group_id:
        kwargs["group_id"] = group_id
    if target_user:
        kwargs["target_user"] = target_user
    group_data = run_until_complete(DataManager.get_data(**kwargs))
    fig, G = draw_graph(group_data, kwargs.get("n"))
    st.button(label="Static", on_click=show_static, args=[fig])
    interact_button = st.button(label="Interact", on_click=show_interact, args=[G])
    server_button = st.button(label="On server", on_click=show_on_server, args=[G])
    st.download_button(
        label="Download json graph",
        data=DataManager.data_to_str_format(group_data, "json", target_user),
        file_name="graph.json",
        mime="application/json",
    )
    st.download_button(
        label="Download csv graph",
        data=DataManager.data_to_str_format(group_data, "csv", target_user),
        file_name="graph.csv",
        mime="application/json",
    )


# RUN SERVER WITH INTERACTIVE GRAPH
def is_port_open(port):
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(1)
    result = s.connect_ex(("localhost", port))
    s.close()
    return result == 0


if not is_port_open(8050):
    subprocess.run(["python", "draw_graph/server_plot.py"])
