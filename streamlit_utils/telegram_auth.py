"""Shared Telegram authentication UI for Streamlit pages."""

from __future__ import annotations

import logging

import streamlit as st

from core.login import run_until_complete, sync_streamlit_event_loop
from core.telegram_session import (
    SESSIONS_DIR,
    SessionInUseError,
    delete_session_files,
    disconnect_telegram_client,
    list_saved_phones,
    list_sessions,
    sanitize_phone,
    save_string_session,
    session_file_exists,
    session_file_path,
    session_health_fraction,
    touch_session,
    update_session_check,
)
from core.tg_api_connector import (
    create_client,
    generate_otp,
    get_telegram_authorizations,
    is_user_authorized,
    verify_otp,
)

logger = logging.getLogger(__name__)


def default_telegram_creds() -> tuple[str, str, str]:
    fallbacks = ("+351966750855", "38530306", "bd81a099f245659c4cc29a2fd3a7812c")
    try:
        tg = st.secrets["telegram"]
        return (
            str(tg.get("phone", fallbacks[0])),
            str(tg.get("api_id", fallbacks[1])),
            str(tg.get("api_hash", fallbacks[2])),
        )
    except (KeyError, FileNotFoundError, AttributeError):
        return fallbacks


def streamlit_holder_id(page_id: str = "main") -> str:
    return f"{page_id}-{id(st.session_state)}"


def _key(page_id: str, name: str) -> str:
    """Session-state suffix for page-specific Telethon clients."""
    if page_id == "main":
        return name
    return f"{page_id}_{name}"


def _client_key(page_id: str) -> str:
    return _key(page_id, "client")


def _ensure_telegram_runtime() -> None:
    sync_streamlit_event_loop()


def connect_telegram_phone(
    phone: str,
    api_id: str,
    api_hash: str,
    *,
    page_id: str = "main",
    force_new: bool = False,
) -> bool:
    _ensure_telegram_runtime()
    client = run_until_complete(
        create_client(
            phone,
            api_id,
            api_hash,
            holder_id=streamlit_holder_id(page_id),
            force_new=force_new,
        )
    )
    st.session_state[_client_key(page_id)] = client
    st.session_state.phone = phone
    st.session_state.api_id = api_id
    st.session_state.api_hash = api_hash
    authorized = run_until_complete(is_user_authorized(client))
    st.session_state.auth = authorized
    update_session_check(phone, authorized)
    if authorized:
        save_string_session(phone, client)
        touch_session(phone, authorized=True)
    return authorized


def get_page_client(page_id: str = "main"):
    """Return Telethon client for page, falling back to main client."""
    return st.session_state.get(_client_key(page_id)) or st.session_state.get("client")


def auto_reconnect_telegram(
    page_id: str = "main",
    *,
    phone_default: str,
    api_id_default: str,
    api_hash_default: str,
) -> None:
    flag = f"_auto_reconnect_{page_id}"
    if st.session_state.get("auth") or st.session_state.get(flag):
        return
    st.session_state[flag] = True
    phone = st.session_state.get("phone") or phone_default
    if not session_file_exists(phone):
        sessions = list_sessions()
        if sessions:
            phone = sessions[0].get("phone") or sessions[0]["phone_key"]
    if not session_file_exists(phone):
        return
    api_id = str(st.session_state.get("api_id", api_id_default))
    api_hash = st.session_state.get("api_hash", api_hash_default)
    try:
        if connect_telegram_phone(
            phone, api_id, api_hash, page_id=page_id, force_new=False
        ):
            st.session_state._auto_reconnect_notice = (
                f"Reconnected automatically using saved session ({phone})."
            )
    except Exception as exc:
        logger.warning("Auto-reconnect failed: %s", exc)


def process_telegram_session_actions(
    page_id: str, container, defaults: tuple[str, str, str]
) -> None:
    _phone_default, _api_id_default, _api_hash_default = defaults

    if st.session_state.get("_sess_connect"):
        phone = st.session_state.pop("_sess_connect")
        try:
            ok = connect_telegram_phone(
                phone,
                str(st.session_state.get("api_id", _api_id_default)),
                st.session_state.get("api_hash", _api_hash_default),
                page_id=page_id,
                force_new=False,
            )
            if ok:
                container.success(f"Connected {phone}")
                st.rerun()
            else:
                container.warning("Not authorized — enter OTP below.")
        except Exception as exc:
            container.error(str(exc))

    if st.session_state.get("_sess_disconnect"):
        phone = st.session_state.pop("_sess_disconnect")
        run_until_complete(disconnect_telegram_client(phone))
        if st.session_state.get("phone") == phone:
            for key in ("client", _client_key(page_id), "auth", "phone_hash"):
                st.session_state.pop(key, None)
            st.session_state.auth = False
        container.info(f"Disconnected {phone}")

    if st.session_state.get("_sess_delete"):
        phone = st.session_state.pop("_sess_delete")
        if st.session_state.get("phone") == phone:
            run_until_complete(disconnect_telegram_client(phone))
            for key in ("client", _client_key(page_id), "auth", "phone_hash"):
                st.session_state.pop(key, None)
            st.session_state.auth = False
        delete_session_files(phone)
        container.warning(f"Deleted session files for {phone}")


def render_telegram_sessions_panel(
    page_id: str = "main",
    *,
    container=None,
    key_prefix: str = "",
) -> None:
    """Saved sessions list with connect/disconnect/delete."""
    container = container or st
    kp = key_prefix or page_id
    with container.expander("Telegram sessions", expanded=True):
        st.caption(f"Sessions directory: `{SESSIONS_DIR}`")
        sessions = list_sessions()
        if not sessions:
            st.caption("No saved sessions yet. Complete OTP once to persist.")
        else:
            for sess in sessions:
                phone_label = sess.get("phone") or sess["phone_key"]
                st.write(f"**{phone_label}**")
                health = session_health_fraction(sess)
                if (
                    st.session_state.get("auth")
                    and sanitize_phone(st.session_state.get("phone", ""))
                    == sanitize_phone(phone_label)
                ):
                    health = 1.0
                st.progress(health)
                if health >= 1.0:
                    st.caption("Authorized — no scheduled expiry")
                elif sess.get("authorized_at"):
                    st.caption("Session file present — click Connect to verify")
                else:
                    st.caption("Re-login required")
                if sess.get("last_used_at"):
                    st.caption(f"Last used: {sess['last_used_at'][:19]}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Connect", key=f"{kp}_sess_conn_{sess['phone_key']}"):
                        st.session_state["_sess_connect"] = phone_label
                with c2:
                    if st.button("Disconnect", key=f"{kp}_sess_disc_{sess['phone_key']}"):
                        st.session_state["_sess_disconnect"] = phone_label
                with c3:
                    if st.button("Delete", key=f"{kp}_sess_del_{sess['phone_key']}"):
                        st.session_state["_sess_delete"] = phone_label
                st.divider()

        client = get_page_client(page_id)
        if (
            st.session_state.get("auth")
            and client
            and st.button("Refresh Telegram device list", key=f"{kp}_refresh_tg_auths")
        ):
            try:
                st.session_state["_tg_authorizations"] = run_until_complete(
                    get_telegram_authorizations(client)
                )
            except Exception as exc:
                st.warning(f"Could not load device list: {exc}")

        tg_auths = st.session_state.get("_tg_authorizations")
        if tg_auths:
            with st.expander("Telegram account devices (from API)"):
                for row in tg_auths:
                    current = " (this app)" if row.get("current") else ""
                    st.write(
                        f"- {row.get('device')} / {row.get('platform')}{current} — "
                        f"active {row.get('date_active', '?')[:19]}"
                    )


def render_telegram_auth_panel(
    page_id: str = "main",
    *,
    location: str = "main",
    key_prefix: str = "",
    sessions_container=None,
    actions_container=None,
) -> None:
    """Phone, API credentials, OTP, connect/disconnect."""
    _phone_default, _api_id_default, _api_hash_default = default_telegram_creds()
    kp = key_prefix or page_id

    if location == "sidebar":
        ui = st.sidebar
    else:
        ui = st

    auto_reconnect_telegram(
        page_id,
        phone_default=_phone_default,
        api_id_default=_api_id_default,
        api_hash_default=_api_hash_default,
    )

    sess_ui = sessions_container or ui
    act_ui = actions_container or sess_ui
    render_telegram_sessions_panel(page_id, container=sess_ui, key_prefix=kp)
    process_telegram_session_actions(
        page_id, act_ui, (_phone_default, _api_id_default, _api_hash_default)
    )

    ui.write("**Connect to Telegram**")

    if st.session_state.get("_auto_reconnect_notice"):
        ui.success(st.session_state.pop("_auto_reconnect_notice"))

    saved_phones = list_saved_phones()
    if saved_phones:
        ui.caption("Saved Telegram sessions on this server")
        selected_saved = ui.selectbox(
            "Reconnect saved phone",
            options=["— new or other —"] + saved_phones,
            format_func=lambda x: x,
            key=f"{kp}_saved_phone",
        )
        if selected_saved != "— new or other —":
            if ui.button("Reconnect saved session", key=f"{kp}_reconnect_saved"):
                prev_phone = st.session_state.get("phone")
                if prev_phone and prev_phone != selected_saved:
                    run_until_complete(disconnect_telegram_client(prev_phone))
                st.session_state.phone = selected_saved
                st.session_state.api_id = st.session_state.get("api_id", _api_id_default)
                st.session_state.api_hash = st.session_state.get(
                    "api_hash", _api_hash_default
                )
                if st.session_state.api_id and st.session_state.api_hash:
                    try:
                        client = run_until_complete(
                            create_client(
                                selected_saved,
                                st.session_state.api_id,
                                st.session_state.api_hash,
                                holder_id=streamlit_holder_id(page_id),
                            )
                        )
                        st.session_state[_client_key(page_id)] = client
                        st.session_state.client = client
                        st.session_state.auth = run_until_complete(
                            is_user_authorized(client)
                        )
                        if st.session_state.auth:
                            touch_session(selected_saved, authorized=True)
                            ui.success(f"Reconnected session for {selected_saved}")
                            st.rerun()
                        else:
                            ui.warning(
                                "Session file exists but is not authorized. Verify OTP."
                            )
                    except SessionInUseError as exc:
                        ui.error(str(exc))
                    except Exception as exc:
                        ui.error(f"Reconnect failed: {exc}")
                else:
                    ui.warning("Enter API id and API hash below, then reconnect.")

    phone_number_input = ui.text_input(
        label="Phone number",
        value=st.session_state.get("phone", _phone_default),
        help="International format, e.g. +373...",
        key=f"{kp}_phone",
    )
    api_id_input = ui.text_input(
        label="Api id",
        value=str(st.session_state.get("api_id", _api_id_default)),
        help="From https://my.telegram.org/apps",
        key=f"{kp}_api_id",
    )
    api_hash_input = ui.text_input(
        label="Api hash",
        value=st.session_state.get("api_hash", _api_hash_default),
        help="From https://my.telegram.org/apps",
        key=f"{kp}_api_hash",
    )
    col_create, col_disconnect = ui.columns(2)
    with col_create:
        create_client_btn = ui.button(
            label="Create / connect Telegram client",
            key=f"{kp}_create_client",
        )
    with col_disconnect:
        disconnect_btn = ui.button(
            label="Disconnect current phone",
            key=f"{kp}_disconnect",
        )

    if disconnect_btn and st.session_state.get("phone"):
        run_until_complete(disconnect_telegram_client(st.session_state.phone))
        for key in ("client", _client_key(page_id), "auth", "phone_hash"):
            st.session_state.pop(key, None)
        st.session_state.auth = False
        ui.info(f"Disconnected {st.session_state.phone}")

    if create_client_btn and phone_number_input and api_id_input and api_hash_input:
        prev_phone = st.session_state.get("phone")
        if prev_phone and sanitize_phone(prev_phone) != sanitize_phone(phone_number_input):
            run_until_complete(disconnect_telegram_client(prev_phone))

        use_force_new = not session_file_exists(phone_number_input)
        try:
            if connect_telegram_phone(
                phone_number_input,
                api_id_input,
                api_hash_input,
                page_id=page_id,
                force_new=use_force_new,
            ):
                st.session_state.client = st.session_state[_client_key(page_id)]
                ui.success("Connected with saved authorization.")
                st.rerun()
            else:
                client = st.session_state[_client_key(page_id)]
                st.session_state.client = client
                st.session_state.client, st.session_state.phone_hash = run_until_complete(
                    generate_otp(
                        client_tg=client,
                        phone_number=phone_number_input,
                    )
                )
                ui.info("OTP sent. Enter the code below.")
        except SessionInUseError as exc:
            ui.error(str(exc))
        except Exception as exc:
            ui.error(f"Could not create Telegram client: {type(exc).__name__}: {exc}")
            logger.exception("create_client failed")

    elif get_page_client(page_id) and st.session_state.get("phone"):
        if "auth" not in st.session_state:
            st.session_state.auth = run_until_complete(
                is_user_authorized(get_page_client(page_id))
            )

    secret_code_input = None
    button_verify_code = None

    if hasattr(st.session_state, "auth") and not st.session_state.auth:
        ui.write("**Enter your secret code to authorize**")
        secret_code_input = ui.text_input(
            label="Secret code",
            help="Telegram OTP",
            key=f"{kp}_otp",
        )
        button_verify_code = ui.button(
            label="Verify secret code",
            key=f"{kp}_verify_otp",
        )

    if (
        hasattr(st.session_state, "auth")
        and not st.session_state.auth
        and button_verify_code
        and secret_code_input
        and get_page_client(page_id)
    ):
        try:
            client = get_page_client(page_id)
            run_until_complete(
                verify_otp(
                    client,
                    st.session_state.phone,
                    secret_code_input,
                    st.session_state.phone_hash,
                )
            )
            st.session_state.auth = True
            touch_session(st.session_state.phone, authorized=True)
            path = session_file_path(st.session_state.phone)
            if path.is_file() and path.read_text(encoding="utf-8").strip():
                ui.success(
                    f"Telegram authorized. Session saved to `{path}` "
                    "(survives page refresh)."
                )
            else:
                ui.warning(
                    "Telegram authorized in memory, but the session file was not written."
                )
            st.rerun()
        except Exception as exc:
            ui.error(f"OTP verification failed: {exc}")

    if st.session_state.get("auth") and st.session_state.get("phone"):
        path = session_file_path(st.session_state.phone)
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            ui.caption(f"Session file: `{path}`")
        else:
            ui.warning(
                "Authorized in memory but no session file on disk — reconnect or re-verify OTP."
            )
