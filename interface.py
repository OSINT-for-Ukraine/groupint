import asyncio
import logging
from collections.abc import Callable

import streamlit as st
from telethon.errors import ChannelPrivateError, UsernameInvalidError, UsernameNotOccupiedError

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
    GroupResolveError,
    create_client,
    extract_endorsements_from_stored_messages,
    extract_users_from_stored_messages,
    fetch_group_messages,
    generate_otp,
    get_all_participants,
    get_telegram_authorizations,
    is_user_authorized,
    normalize_telegram_group_ref,
    verify_otp,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from core.upload_file import parse_json_users, parse_xls_users
from draw_graph.dynamic_plot import get_graph
from draw_graph.common_groups_plot import draw_common_groups_graph
from draw_graph.endorsement_plot import draw_endorsement_graph
from draw_graph.plot import draw_graph
from db.dal import GraphManager
from db.neo4j_browser import neo4j_browser_url
from main import DataManager
from streamlit_utils.text import query_hint


def _unpack_participants_fetch(
    result: object,
    raw_group: str,
) -> tuple[list[tuple[int, str | None, str]], str | None, object]:
    """Normalize participant fetch result (3-tuple or legacy 2-tuple)."""
    from core.group_identity import ResolvedGroup

    if not isinstance(result, tuple):
        raise TypeError(
            f"Participant fetch returned {type(result).__name__}, expected tuple"
        )
    if len(result) == 3:
        users, group_title, resolved = result
        return users, group_title, resolved
    if len(result) == 2:
        users, group_title = result
        resolved = ResolvedGroup(
            canonical_id=normalize_telegram_group_ref(raw_group),
            title=group_title,
        )
        return users, group_title, resolved
    raise ValueError(
        f"Participant fetch returned {len(result)} values, expected 2 or 3"
    )


def _merge_user_rows(
    existing: list[tuple], new_rows: list[tuple]
) -> list[tuple[int, str | None, str]]:
    """Merge participant tuples by Telegram user id."""
    by_id: dict[int, tuple[int, str | None, str]] = {
        int(row[0]): (int(row[0]), row[1] if len(row) > 1 else None, row[2] if len(row) > 2 else "")
        for row in existing
        if row and row[0] is not None
    }
    for row in new_rows:
        if row and row[0] is not None:
            uid = int(row[0])
            by_id[uid] = (
                uid,
                row[1] if len(row) > 1 else by_id.get(uid, (uid, None, ""))[1],
                row[2] if len(row) > 2 else by_id.get(uid, (uid, None, ""))[2],
            )
    return list(by_id.values())


def _format_scraped_group_label(row: dict) -> str:
    gid = row.get("id", "?")
    members = row.get("members", "?")
    scraped = row.get("scraped_at") or "unknown date"
    source = row.get("source") or ""
    title = row.get("title")
    label = f"{gid} ({members} members, {scraped[:10] if scraped else '?'}"
    if source:
        label += f", {source}"
    label += ")"
    if title and title != gid:
        label = f"{title} — {label}"
    return label


def _streamlit_holder_id() -> str:
    return str(id(st.session_state))


def _init_streamlit_state() -> None:
    if "event_loop" not in st.session_state:
        st.session_state.event_loop = asyncio.new_event_loop()


def _ensure_telegram_runtime() -> None:
    sync_streamlit_event_loop()


def _refresh_telegram_client() -> None:
    """Re-bind Telethon client to the current Streamlit event loop."""
    _ensure_telegram_runtime()
    phone = st.session_state.get("phone")
    api_id = st.session_state.get("api_id")
    api_hash = st.session_state.get("api_hash")
    if not phone or not api_id or not api_hash or not st.session_state.get("auth"):
        return
    client = run_until_complete(
        create_client(
            phone,
            api_id,
            api_hash,
            holder_id=_streamlit_holder_id(),
            force_new=False,
        )
    )
    st.session_state.client = client


def _connect_telegram_phone(
    phone: str, api_id: str, api_hash: str, *, force_new: bool = False
) -> bool:
    """Create or restore client; return True when Telegram session is authorized."""
    _ensure_telegram_runtime()
    client = run_until_complete(
        create_client(
            phone,
            api_id,
            api_hash,
            holder_id=_streamlit_holder_id(),
            force_new=force_new,
        )
    )
    st.session_state.client = client
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


def _auto_reconnect_telegram() -> None:
    if st.session_state.get("auth") or st.session_state.get("_auto_reconnect_attempted"):
        return
    st.session_state._auto_reconnect_attempted = True
    phone = st.session_state.get("phone") or _phone_default
    if not session_file_exists(phone):
        sessions = list_sessions()
        if sessions:
            phone = sessions[0].get("phone") or sessions[0]["phone_key"]
    if not session_file_exists(phone):
        return
    api_id = str(st.session_state.get("api_id", _api_id_default))
    api_hash = st.session_state.get("api_hash", _api_hash_default)
    try:
        if _connect_telegram_phone(phone, api_id, api_hash, force_new=False):
            st.session_state._auto_reconnect_notice = (
                f"Reconnected automatically using saved session ({phone})."
            )
    except Exception as exc:
        logger.warning("Auto-reconnect failed: %s", exc)


def _default_telegram_creds() -> tuple[str, str, str]:
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


_init_streamlit_state()

st.components.v1.html(
    """
<script>
document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')) {
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) {
      e.stopPropagation();
    }
  }
}, true);
</script>
""",
    height=0,
)

_phone_default, _api_id_default, _api_hash_default = _default_telegram_creds()

_auto_reconnect_telegram()

with st.sidebar.expander("Query hint"):
    st.markdown(query_hint)

with st.sidebar.expander("Telegram sessions", expanded=True):
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
                if st.button("Connect", key=f"sess_conn_{sess['phone_key']}"):
                    st.session_state["_sess_connect"] = phone_label
            with c2:
                if st.button("Disconnect", key=f"sess_disc_{sess['phone_key']}"):
                    st.session_state["_sess_disconnect"] = phone_label
            with c3:
                if st.button("Delete", key=f"sess_del_{sess['phone_key']}"):
                    st.session_state["_sess_delete"] = phone_label
            st.divider()

    if (
        st.session_state.get("auth")
        and hasattr(st.session_state, "client")
        and st.button("Refresh Telegram device list", key="refresh_tg_auths")
    ):
        try:
            st.session_state["_tg_authorizations"] = run_until_complete(
                get_telegram_authorizations(st.session_state.client)
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

if st.session_state.get("_sess_connect"):
    phone = st.session_state.pop("_sess_connect")
    try:
        ok = _connect_telegram_phone(
            phone, str(st.session_state.get("api_id", _api_id_default)),
            st.session_state.get("api_hash", _api_hash_default),
            force_new=False,
        )
        if ok:
            st.sidebar.success(f"Connected {phone}")
            st.rerun()
        else:
            st.sidebar.warning("Not authorized — enter OTP below.")
    except Exception as exc:
        st.sidebar.error(str(exc))

if st.session_state.get("_sess_disconnect"):
    phone = st.session_state.pop("_sess_disconnect")
    run_until_complete(disconnect_telegram_client(phone))
    if st.session_state.get("phone") == phone:
        for key in ("client", "auth", "phone_hash"):
            st.session_state.pop(key, None)
        st.session_state.auth = False
    st.sidebar.info(f"Disconnected {phone}")

if st.session_state.get("_sess_delete"):
    phone = st.session_state.pop("_sess_delete")
    if st.session_state.get("phone") == phone:
        run_until_complete(disconnect_telegram_client(phone))
        for key in ("client", "auth", "phone_hash"):
            st.session_state.pop(key, None)
        st.session_state.auth = False
    delete_session_files(phone)
    st.sidebar.warning(f"Deleted session files for {phone}")

#####  LOAD USER DETAILS
st.write("****Confirm your details to connect to Telegram scraper****")

if st.session_state.get("_auto_reconnect_notice"):
    st.success(st.session_state.pop("_auto_reconnect_notice"))

saved_phones = list_saved_phones()
if saved_phones:
    st.caption("Saved Telegram sessions on this server")
    selected_saved = st.selectbox(
        "Reconnect saved phone",
        options=["— new or other —"] + saved_phones,
        format_func=lambda x: x if x != "— new or other —" else x,
    )
    if selected_saved != "— new or other —":
        if st.button("Reconnect saved session"):
            prev_phone = st.session_state.get("phone")
            if prev_phone and prev_phone != selected_saved:
                run_until_complete(disconnect_telegram_client(prev_phone))
            st.session_state.phone = selected_saved
            st.session_state.api_id = st.session_state.get("api_id", _api_id_default)
            st.session_state.api_hash = st.session_state.get("api_hash", _api_hash_default)
            if st.session_state.api_id and st.session_state.api_hash:
                try:
                    client = run_until_complete(
                        create_client(
                            selected_saved,
                            st.session_state.api_id,
                            st.session_state.api_hash,
                            holder_id=_streamlit_holder_id(),
                        )
                    )
                    st.session_state.client = client
                    st.session_state.auth = run_until_complete(
                        is_user_authorized(client)
                    )
                    if st.session_state.auth:
                        touch_session(selected_saved, authorized=True)
                        st.success(f"Reconnected session for {selected_saved}")
                        st.rerun()
                    else:
                        st.warning("Session file exists but is not authorized. Verify OTP.")
                except SessionInUseError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Reconnect failed: {exc}")
            else:
                st.warning("Enter API id and API hash below, then click Reconnect again.")

phone_number_input = st.text_input(
    label="Phone number",
    value=st.session_state.get("phone", _phone_default),
    help="International format, e.g. +373...",
)
api_id_input = st.text_input(
    label="Api id",
    value=str(st.session_state.get("api_id", _api_id_default)),
    help="From https://my.telegram.org/apps",
)
api_hash_input = st.text_input(
    label="Api hash",
    value=st.session_state.get("api_hash", _api_hash_default),
    help="From https://my.telegram.org/apps",
)
col_create, col_disconnect = st.columns(2)
with col_create:
    create_client_btn = st.button(label="Create / connect Telegram client")
with col_disconnect:
    disconnect_btn = st.button(label="Disconnect current phone")

if disconnect_btn and st.session_state.get("phone"):
    run_until_complete(disconnect_telegram_client(st.session_state.phone))
    for key in ("client", "auth", "phone_hash"):
        st.session_state.pop(key, None)
    st.session_state.auth = False
    st.info(f"Disconnected {st.session_state.phone}")

if (
    create_client_btn
    and phone_number_input
    and api_id_input
    and api_hash_input
):
    prev_phone = st.session_state.get("phone")
    if prev_phone and sanitize_phone(prev_phone) != sanitize_phone(phone_number_input):
        run_until_complete(disconnect_telegram_client(prev_phone))

    use_force_new = not session_file_exists(phone_number_input)
    try:
        if _connect_telegram_phone(
            phone_number_input,
            api_id_input,
            api_hash_input,
            force_new=use_force_new,
        ):
            st.success("Connected with saved authorization.")
            st.rerun()
        else:
            st.session_state.client, st.session_state.phone_hash = run_until_complete(
                generate_otp(
                    client_tg=st.session_state.client,
                    phone_number=phone_number_input,
                )
            )
            st.info("OTP sent. Enter the code below.")
    except SessionInUseError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Could not create Telegram client: {type(exc).__name__}: {exc}")
        logger.exception("create_client failed")

elif hasattr(st.session_state, "client") and st.session_state.get("phone"):
    if "auth" not in st.session_state:
        st.session_state.auth = run_until_complete(
            is_user_authorized(st.session_state.client)
        )

secret_code_input = None
button_verify_code = None

if hasattr(st.session_state, "auth") and not st.session_state.auth:
    st.write("**Enter your secret code to authorize**")
    secret_code_input = st.text_input(label="Secret code", help="Telegram OTP")
    button_verify_code = st.button(label="Verify secret code")

if (
    hasattr(st.session_state, "auth")
    and not st.session_state.auth
    and button_verify_code
    and secret_code_input
    and hasattr(st.session_state, "client")
):
    try:
        run_until_complete(
            verify_otp(
                st.session_state.client,
                st.session_state.phone,
                secret_code_input,
                st.session_state.phone_hash,
            )
        )
        st.session_state.auth = True
        touch_session(st.session_state.phone, authorized=True)
        path = session_file_path(st.session_state.phone)
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            st.success(
                f"Telegram authorized. Session saved to `{path}` "
                "(survives page refresh)."
            )
        else:
            st.warning(
                "Telegram authorized in memory, but the session file was not "
                "written. Check permissions on the sessions directory."
            )
        st.rerun()
    except Exception as exc:
        st.error(f"OTP verification failed: {exc}")

if st.session_state.get("auth") and st.session_state.get("phone"):
    path = session_file_path(st.session_state.phone)
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        st.caption(f"Session file: `{path}`")
    elif st.session_state.get("auth"):
        st.warning(
            "Authorized in memory but no session file on disk — "
            "click **Create / connect** again or re-verify OTP."
        )

st.markdown(
    """<hr style="height:2px;border:none;color:#222;background-color:#222;" /> """,
    unsafe_allow_html=True,
)

group_id = None
button_clicked_load = None
model_for_user_groups_exist = True
button_clicked_graph_common = None
button_clicked_graph_endorsements = None
graph_arg = None
button_clicked_fetch_messages = None
button_clicked_extract_users = None
button_clicked_extract_endorsements = None
n_of_messages_input = None
users = []
uploaded_file = None

if st.session_state.get("auth"):
    scraped_groups = GraphManager.list_scraped_groups()
    if scraped_groups:
        st.write("**Previously scraped groups**")
        scraped_options = {row["id"]: row for row in scraped_groups}
        picked_id = st.selectbox(
            "Load from history",
            options=["— enter new group —"] + list(scraped_options.keys()),
            format_func=lambda x: (
                _format_scraped_group_label(scraped_options[x])
                if x in scraped_options
                else x
            ),
        )
        if picked_id != "— enter new group —":
            st.session_state.selected_group_ref = picked_id

        with st.expander("Manage Neo4j data"):
            st.caption(
                "Merge duplicate Group nodes (same chat scraped under different names), "
                "or delete one group's data."
            )
            merge_confirm = st.checkbox(
                "I understand merge rewires members, messages, and endorsements",
                key="neo4j_merge_confirm",
            )
            if st.button(
                "Merge duplicate groups",
                key="neo4j_merge_btn",
                disabled=not merge_confirm,
            ):
                try:
                    with st.spinner("Merging duplicate groups in Neo4j…"):
                        result = GraphManager.merge_duplicate_groups(
                            ensure_unique_constraint=True
                        )
                except Exception as exc:
                    st.error(f"Merge failed: {exc}")
                else:
                    if result.get("errors"):
                        st.warning("; ".join(result["errors"]))
                    st.success(
                        f"Merged **{result.get('merged', 0)}** duplicate node(s) across "
                        f"**{result.get('clusters', 0)}** cluster(s)."
                    )
                    if result.get("same_id_nodes_merged"):
                        st.caption(
                            f"Includes **{result['same_id_nodes_merged']}** extra node(s) "
                            "that shared the same `Group.id`."
                        )
                    if result.get("constraint_applied"):
                        st.caption("Unique constraint on `Group.id` is active.")
                    st.rerun()
            st.divider()
            for idx, row in enumerate(scraped_groups):
                gid = row["id"]
                st.write(_format_scraped_group_label(row))
                confirm_key = f"neo4j_del_confirm_{idx}"
                btn_key = f"neo4j_del_btn_{idx}"
                confirmed = st.checkbox(
                    "I understand this cannot be undone",
                    key=confirm_key,
                )
                if st.button(
                    "Delete group data",
                    key=btn_key,
                    disabled=not confirmed,
                ):
                    deleted_nodes = GraphManager.delete_group_data(gid)
                    if deleted_nodes > 0:
                        if st.session_state.get("selected_group_ref") == gid:
                            st.session_state.pop("selected_group_ref", None)
                        if st.session_state.get("last_group_ref") == gid:
                            st.session_state.pop("last_group_ref", None)
                        st.success(
                            f"Removed Neo4j data for `{gid}` "
                            f"({deleted_nodes} Group node(s) deleted)."
                        )
                        st.rerun()
                    else:
                        st.error(f"Could not delete data for `{gid}` (group not found?).")
                st.divider()
    else:
        st.caption(
            "No groups in Neo4j yet. Scrape a group below; it will appear here on the next run."
        )

    default_group = st.session_state.get(
        "selected_group_ref", st.session_state.get("last_group_ref", "")
    )
    st.write("**Select target group**")
    group_id = st.text_input(
        label="Input name of target group",
        value=default_group,
        help="Public @username or t.me link, e.g. Republic_of_Gagazia_Chat or https://t.me/Republic_of_Gagazia_Chat",
    )
    st.markdown(
        """<hr style="height:2px;border:none;color:#222;background-color:#222;" /> """,
        unsafe_allow_html=True,
    )

    st.write("**Extract members**")
    button_clicked_load = st.button(label="Get users list")

    st.markdown(
        """<hr style="height:1px;border:none;color:#444;background-color:#444;" /> """,
        unsafe_allow_html=True,
    )
    st.write("**Messages**")
    st.caption(
        "Step 1: **Get messages from group** stores chat history in Neo4j. "
        "Step 2: **Extract users from stored messages** resolves authors only from messages "
        "not processed yet."
    )
    n_of_messages_input = st.text_input(
        label="How many messages to fetch?",
        help="Integer. Re-run to fetch older messages incrementally.",
        key="messages_fetch_limit",
    )
    col_get_messages, col_extract_users, col_endorse = st.columns(3)
    with col_get_messages:
        button_clicked_fetch_messages = st.button(
            label="Get messages from group",
            type="primary",
            key="btn_get_messages",
        )
    with col_extract_users:
        button_clicked_extract_users = st.button(
            label="Extract users from stored messages",
            key="btn_extract_users_from_messages",
            help="Uses messages already saved by **Get messages from group**",
        )
    with col_endorse:
        button_clicked_extract_endorsements = st.button(
            label="Extract endorsements from messages",
            key="btn_extract_endorsements",
            help="Telegram t.me / @ links → ENDORSES edges between groups",
        )

    if group_id and str(group_id).strip():
        try:
            _msg_counts = GraphManager.count_group_messages(
                normalize_telegram_group_ref(group_id)
            )
            if _msg_counts["total"] > 0:
                st.caption(
                    f"{_msg_counts['total']:,} messages stored, "
                    f"{_msg_counts['unprocessed']:,} pending user extraction, "
                    f"{_msg_counts.get('links_unprocessed', 0):,} pending link extraction"
                )
            else:
                st.caption("No messages stored yet for this group.")
        except Exception:
            st.caption(
                "Message counts unavailable (Neo4j). Buttons still work."
            )

    uploaded_file = st.file_uploader(
        "Upload file (JSON or XLSX)", accept_multiple_files=False, type=["json", "xls", "xlsx"]
    )

    st.markdown(
        """<hr style="height:2px;border:none;color:#222;background-color:#222;" /> """,
        unsafe_allow_html=True,
    )


def _root_telegram_error(exc: BaseException) -> BaseException:
    cause = exc
    while cause.__cause__ is not None:
        cause = cause.__cause__
    return cause


def _attempts_include_username_errors(exc: GroupResolveError) -> bool:
    for attempt in exc.attempts:
        err = attempt.get("error")
        if isinstance(err, UsernameNotOccupiedError | UsernameInvalidError):
            return True
    return False


_MEMBER_GROUP_HINT = (
    "You may already be in this group. Public @username lookup failed (renamed or "
    "private megagroup). Open the chat in Telegram, then retry with the exact t.me link "
    "or the group title as shown in your chat list."
)


def _show_telegram_group_error(action: str, raw: str, exc: BaseException) -> None:
    ref = normalize_telegram_group_ref(raw)
    root = _root_telegram_error(exc)
    logger.exception("%s failed for group ref=%r (raw=%r)", action, ref, raw)

    if isinstance(exc, GroupResolveError):
        st.error(
            f"Groupint could not open **{ref}** via the Telegram API, even though the group may exist. "
            "This is usually **not a wrong link** if you are already a member."
        )
        if _attempts_include_username_errors(exc):
            st.warning(_MEMBER_GROUP_HINT)
        st.code(str(exc), language="text")
        with st.expander("Technical details (each lookup attempt)"):
            for attempt in exc.attempts:
                st.write(
                    f"- `{attempt['candidate']}` → "
                    f"**{type(attempt['error']).__name__}**: {attempt['error']}"
                )
        return

    if isinstance(exc, RuntimeError) and "not authorized" in str(exc).lower():
        st.error(str(exc))
        return

    if isinstance(root, UsernameNotOccupiedError | UsernameInvalidError) or isinstance(
        exc, UsernameNotOccupiedError | UsernameInvalidError
    ):
        st.error(f"Telegram API error for **{ref}**: `{type(root).__name__}: {root}`")
        st.info(_MEMBER_GROUP_HINT)
    elif isinstance(exc, ChannelPrivateError):
        st.error(f"**{ref}** — Telegram returned ChannelPrivateError: {exc}")
    else:
        st.error(f"Could not {action} for **{ref}**: `{type(exc).__name__}: {exc}`")


def _require_telegram_client() -> bool:
    if not hasattr(st.session_state, "client"):
        st.error("Create a Telegram client and verify the OTP code before extracting data.")
        return False
    if not st.session_state.get("auth"):
        st.error("Complete Telegram OTP verification before extracting data.")
        return False
    try:
        _refresh_telegram_client()
    except Exception as exc:
        st.error(f"Telegram client reconnect failed: {exc}")
        return False
    return True


def _run_extract_with_progress(
    coro_factory: Callable[[Callable[[float, str], None]], object],
):
    """Run an async extract coroutine and update st.progress while it runs."""
    progress = st.progress(0.0)
    caption = st.empty()

    def on_progress(frac: float, text: str) -> None:
        progress.progress(min(max(frac, 0.0), 1.0))
        caption.caption(text)

    try:
        result = run_until_complete(coro_factory(on_progress))
        progress.progress(1.0)
        return result
    finally:
        caption.empty()


if group_id and button_clicked_load and _require_telegram_client():
    try:
        fetch_result = _run_extract_with_progress(
            lambda on_progress: get_all_participants(
                st.session_state.client, group_id, on_progress=on_progress
            )
        )
        users, group_title, resolved = _unpack_participants_fetch(
            fetch_result, group_id
        )
    except Exception as exc:
        _show_telegram_group_error("load members", group_id, exc)
    else:
        from core.group_identity import validate_member_count_for_persist

        group_ref = resolved.canonical_id
        try:
            validate_member_count_for_persist(
                len(users), resolved.participants_count
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            saved = GraphManager.add_extracted_group_members(
                group_ref,
                users,
                group_title=group_title or resolved.title,
                scrape_source="members",
                group_meta=resolved,
            )
            st.write(
                f"**{len(users)} users extracted** and **{saved} saved to Neo4j** "
                f"(Group `{group_ref}`). Use graph query `*N` or **On server** after this."
            )
            if resolved.canonical_id != normalize_telegram_group_ref(group_id):
                st.caption(
                    f"Stored under canonical id `{group_ref}` "
                    f"(input was `{group_id.strip()}`)."
                )
            st.session_state.users = users
            st.session_state.last_group_ref = group_ref
            st.session_state.selected_group_ref = group_ref

if button_clicked_fetch_messages and _require_telegram_client():
    if not group_id:
        st.error("Enter a group @username or t.me link before fetching messages.")
    elif not n_of_messages_input or not str(n_of_messages_input).strip().isdigit():
        st.error("Enter how many messages to fetch (a positive number).")
    else:
        try:
            inserted, skipped, group_title, resolved = _run_extract_with_progress(
                lambda on_progress: fetch_group_messages(
                    st.session_state.client,
                    group_id,
                    int(n_of_messages_input),
                    on_progress=on_progress,
                )
            )
        except Exception as exc:
            _show_telegram_group_error("fetch messages", group_id, exc)
        else:
            group_ref = resolved.canonical_id
            counts = GraphManager.count_group_messages(group_ref)
            st.success(
                f"**{inserted} new** messages stored ({skipped} already in DB). "
                f"**{counts['unprocessed']:,}** awaiting user extraction "
                f"({counts['total']:,} total stored)."
            )
            if group_title:
                st.caption(f"Group title: {group_title} · Neo4j id `{group_ref}`")
            st.session_state.last_group_ref = group_ref
            st.session_state.selected_group_ref = group_ref

if button_clicked_extract_users and _require_telegram_client():
    if not group_id:
        st.error("Enter a group @username or t.me link before extracting users.")
    else:
        group_ref = normalize_telegram_group_ref(group_id)
        pending = GraphManager.count_group_messages(group_ref)["unprocessed"]
        if pending == 0:
            st.info(
                "No unprocessed messages for this group. Use **Fetch messages from group** first."
            )
        else:
            try:
                users_from_messages, group_title, resolved = _run_extract_with_progress(
                    lambda on_progress: extract_users_from_stored_messages(
                        st.session_state.client,
                        group_id,
                        on_progress=on_progress,
                    )
                )
            except Exception as exc:
                _show_telegram_group_error(
                    "extract users from stored messages", group_id, exc
                )
            else:
                group_ref = resolved.canonical_id
                if not users_from_messages:
                    st.info("No authors to resolve in unprocessed messages.")
                else:
                    from core.group_identity import validate_member_count_for_persist

                    try:
                        validate_member_count_for_persist(len(users_from_messages))
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        marked = GraphManager.mark_group_messages_processed(group_ref)
                        prior = list(st.session_state.get("users") or [])
                        saved = GraphManager.add_extracted_group_members(
                            group_ref,
                            users_from_messages,
                            group_title=group_title or resolved.title,
                            scrape_source="messages",
                            group_meta=resolved,
                        )
                        merged = _merge_user_rows(prior, users_from_messages)
                        counts = GraphManager.count_group_messages(group_ref)
                        st.write(
                            f"**{len(users_from_messages)} users** merged into Neo4j "
                            f"({saved} members for this group); "
                            f"**{marked:,} messages** marked processed "
                            f"({counts['unprocessed']:,} still pending)."
                        )
                        st.session_state.users = merged
                st.session_state.last_group_ref = group_ref
                st.session_state.selected_group_ref = group_ref

if button_clicked_extract_endorsements and _require_telegram_client():
    if not group_id:
        st.error("Enter a group @username or t.me link before extracting endorsements.")
    else:
        group_ref = normalize_telegram_group_ref(group_id)
        pending_links = GraphManager.count_group_messages(group_ref).get(
            "links_unprocessed", 0
        )
        if pending_links == 0:
            st.info(
                "No messages pending link extraction. Fetch messages with text first."
            )
        else:
            try:
                inserted, total_links, resolved = _run_extract_with_progress(
                    lambda on_progress: extract_endorsements_from_stored_messages(
                        st.session_state.client,
                        group_id,
                        on_progress=on_progress,
                    )
                )
            except Exception as exc:
                _show_telegram_group_error("extract endorsements", group_id, exc)
            else:
                group_ref = resolved.canonical_id
                st.success(
                    f"**{inserted} new** endorsement edges "
                    f"({total_links} links parsed). "
                    f"Visualize with graph query `endorsement_graph`."
                )
                st.session_state.last_group_ref = group_ref
                st.session_state.selected_group_ref = group_ref

if uploaded_file is not None:
    file_extension = uploaded_file.name.split(".")[-1]
    try:
        if file_extension == "json":
            saved_by_group = parse_json_users(uploaded_file)
            total = sum(saved_by_group.values())
            st.success(
                f"Imported JSON into Neo4j: {total} user rows across "
                f"{len(saved_by_group)} group(s)."
            )
        elif file_extension in ["xlsx", "xls"]:
            if group_id and str(group_id).strip():
                count = parse_xls_users(uploaded_file, group_id)
                ref = normalize_telegram_group_ref(group_id)
                st.success(f"Imported {count} users into Neo4j for group `{ref}`.")
                st.session_state.last_group_ref = ref
                st.session_state.selected_group_ref = ref
            else:
                st.warning(
                    "Enter the target group in **Input name of target group** "
                    "before uploading XLSX."
                )
    except Exception as exc:
        st.error(f"File import failed: {exc}")

def show_static(fig):
    st.plotly_chart(fig)
    st.divider()


def show_interact(G):
    graph_html, nt = get_graph(G)
    st.components.v1.html(graph_html, width=1000, height=750)
    st.divider()


def _graph_limit_arg(arg: str | None) -> int:
    if arg and str(arg).strip().isdigit():
        return max(1, int(str(arg).strip()))
    return 200


def _show_graph_result(fig, G, query_key: str, n_arg: int | None) -> None:
    col_static, col_interact, col_server = st.columns(3)
    with col_static:
        st.button(label="Static", on_click=show_static, args=[fig])
    with col_interact:
        st.button(label="Interact", on_click=show_interact, args=[G])
    with col_server:
        try:
            st.link_button(
                label="On server",
                url=neo4j_browser_url(query_key, n_arg),
                help="Open Neo4j Browser with this query (graph view)",
            )
        except ValueError as exc:
            st.warning(str(exc))
    st.caption(
        "**On server** opens Neo4j Browser (http://localhost:17474) with "
        "**No authentication** and your query pre-filled. "
        "Click **Connect** once (not username/password); then run the query "
        "(Ctrl+Enter). The browser remembers this server for next time."
    )


if st.session_state.get("auth"):
    st.write("**Graphs from Neo4j**")
    graph_arg = st.text_input(
        label="Graph limit N (optional)",
        help="Max edges/nodes to load for the graph buttons below (default 200).",
        key="graph_limit_n",
    )
    col_graph_common, col_graph_endorse = st.columns(2)
    with col_graph_common:
        button_clicked_graph_common = st.button(
            label="Graph by common groups",
            help="Build RELATED edges between users who share scraped groups, then visualize",
        )
    with col_graph_endorse:
        button_clicked_graph_endorsements = st.button(
            label="Graph by endorsements",
            help="Visualize Group→Group ENDORSES edges from extracted message links",
        )

if button_clicked_graph_common:
    n_arg = _graph_limit_arg(graph_arg)
    try:
        run_until_complete(DataManager.create_relationships())
        group_data = run_until_complete(
            DataManager.get_data("common_groups_graph", n_arg)
        )
        fig, G = draw_common_groups_graph(group_data, n_arg)
    except ValueError as exc:
        st.error(str(exc))
        if "No RELATED" in str(exc):
            st.info(
                "Scrape **Get users list** for at least two groups so users share "
                "membership, then try again."
            )
    except Exception as exc:
        st.error(f"Graph by common groups failed: {type(exc).__name__}: {exc}")
    else:
        _show_graph_result(fig, G, "common_groups_graph", n_arg)

if button_clicked_graph_endorsements:
    n_arg = _graph_limit_arg(graph_arg)
    try:
        group_data = run_until_complete(
            DataManager.get_data("endorsement_graph", n_arg)
        )
        fig, G = draw_endorsement_graph(group_data, n_arg)
    except ValueError as exc:
        st.error(str(exc))
        st.info("Run **Extract endorsements from messages** first.")
    except Exception as exc:
        st.error(f"Graph by endorsements failed: {type(exc).__name__}: {exc}")
    else:
        _show_graph_result(fig, G, "endorsement_graph", n_arg)

st.divider()
st.write("**Fetch graph from storage**")
col1, col2 = st.columns(2)
with col1:
    query_filter = st.text_input(
        label="Input filter to create graph", help="You could find hint in the sidebar"
    )
with col2:
    arg = st.text_input(label="Input integer argument if necessary")

button_clicked_fetch = st.button(label="Show graph")


if button_clicked_fetch and not model_for_user_groups_exist:
    st.write("we are missing proper model to represent this data")
elif button_clicked_fetch and model_for_user_groups_exist:
    query_key = (query_filter or "").strip()
    if not query_key:
        st.error(
            "Enter a graph query name in **Input filter to create graph** "
            "(see Query hint in the sidebar)."
        )
    else:
        try:
            if query_key == "endorsement_graph":
                n_arg = _graph_limit_arg(arg)
                group_data = run_until_complete(DataManager.get_data(query_key, n_arg))
                fig, G = draw_endorsement_graph(group_data, n_arg)
            elif query_key == "common_groups_graph":
                n_arg = _graph_limit_arg(arg)
                run_until_complete(DataManager.create_relationships())
                group_data = run_until_complete(DataManager.get_data(query_key, n_arg))
                fig, G = draw_common_groups_graph(group_data, n_arg)
            else:
                n_arg = int(arg) if arg and str(arg).strip() else None
                group_data = run_until_complete(DataManager.get_data(query_key, n_arg))
                fig, G = draw_graph(group_data, n_arg)
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Graph query failed: {type(exc).__name__}: {exc}")
        else:
            _show_graph_result(fig, G, query_key, n_arg)
