"""Build canonical Telegram web/tg links for groups, users, and messages."""

from __future__ import annotations

from core.tg_api_connector import normalize_telegram_group_ref


def group_url(group_ref: str) -> str:
    ref = normalize_telegram_group_ref(group_ref)
    if not ref:
        return ""
    return f"https://t.me/{ref}"


def user_url(user_id: int, username: str | None = None) -> str:
    if username and str(username).strip():
        handle = str(username).strip().lstrip("@")
        return f"https://t.me/{handle}"
    return f"tg://user?id={int(user_id)}"


def _channel_internal_id(channel_id: int) -> str:
    """Telegram /c/ links use the numeric id without the -100 prefix."""
    cid = int(channel_id)
    s = str(cid)
    if s.startswith("-100"):
        return s[4:]
    return s.lstrip("-")


def message_url(
    group_ref: str,
    message_id: int,
    *,
    username: str | None = None,
    channel_id: int | None = None,
) -> str:
    """Public group/channel: t.me/{username}/{id}; private: t.me/c/{internal}/{id}."""
    mid = int(message_id)
    if username and str(username).strip():
        handle = str(username).strip().lstrip("@")
        return f"https://t.me/{handle}/{mid}"
    if channel_id is not None:
        return f"https://t.me/c/{_channel_internal_id(channel_id)}/{mid}"
    ref = normalize_telegram_group_ref(group_ref)
    if ref:
        return f"https://t.me/{ref}/{mid}"
    return ""


def entity_message_url(group_ref: str, message_id: int, entity) -> str:
    """Build message URL from a resolved Telethon channel/chat entity."""
    username = getattr(entity, "username", None)
    channel_id = getattr(entity, "id", None)
    return message_url(
        group_ref,
        message_id,
        username=username,
        channel_id=channel_id,
    )
