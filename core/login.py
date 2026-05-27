import asyncio

import nest_asyncio
import streamlit as st


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    """Create or replace Streamlit session asyncio loop (pages without interface.py)."""
    loop = st.session_state.get("event_loop")
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        st.session_state.event_loop = loop
    return loop


def sync_streamlit_event_loop() -> asyncio.AbstractEventLoop:
    """Bind asyncio to Streamlit's session loop; re-patch nest_asyncio if loop changed."""
    loop = ensure_event_loop()
    asyncio.set_event_loop(loop)
    curr = id(loop)
    prev = st.session_state.get("_nest_asyncio_loop_id")
    if prev != curr:
        nest_asyncio.apply(loop)
        st.session_state._nest_asyncio_loop_id = curr
        if prev is not None:
            from core.telegram_session import registry

            registry.clear_clients()
    return loop


def run_until_complete(coro):
    sync_streamlit_event_loop()
    return st.session_state.event_loop.run_until_complete(coro)
