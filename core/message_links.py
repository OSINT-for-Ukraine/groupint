"""Extract Telegram group/channel references from message text."""

from __future__ import annotations

import re

_TME_LINK = re.compile(
    r"^(?:https?://)?(?:www\.)?t\.me/(?P<ref>\+?[\w-]+)/?$",
    re.IGNORECASE,
)
_TME_URL = re.compile(
    r"(?:https?://)?(?:www\.)?t\.me/(?P<ref>[+]?[\w-]+)",
    re.IGNORECASE,
)
_AT_MENTION = re.compile(r"(?<![\w.])@([a-zA-Z][\w_]{3,31})")
_SKIP_AT = frozenset({"joinchat", "addstickers", "share", "iv", "s", "c"})

_MAX_TEXT_LEN = 4096


def normalize_telegram_group_ref(raw: str) -> str:
    value = raw.strip()
    if not value:
        return value
    match = _TME_LINK.match(value)
    if match:
        return match.group("ref")
    if value.startswith("@"):
        return value[1:]
    return value


def truncate_message_text(text: str | None) -> str:
    if not text:
        return ""
    return text[:_MAX_TEXT_LEN]


def extract_telegram_links(text: str, *, source_ref: str) -> list[dict]:
    """
  Return unique link dicts: target_ref, link_raw.
  Skips self-references and non-group patterns.
    """
    if not text or not str(text).strip():
        return []
    source_norm = normalize_telegram_group_ref(source_ref)
    seen: set[str] = set()
    results: list[dict] = []

    def add(raw: str, ref: str) -> None:
        normalized = normalize_telegram_group_ref(ref)
        if not normalized or normalized.startswith("+"):
            return
        if normalized.casefold() == source_norm.casefold():
            return
        key = normalized.casefold()
        if key in seen:
            return
        seen.add(key)
        results.append({"target_ref": normalized, "link_raw": raw})

    for match in _TME_URL.finditer(text):
        add(match.group(0), match.group("ref"))

    for match in _AT_MENTION.finditer(text):
        username = match.group(1)
        if username.lower() in _SKIP_AT:
            continue
        add(f"@{username}", username)

    return results
