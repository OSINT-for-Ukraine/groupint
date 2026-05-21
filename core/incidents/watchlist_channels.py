"""Parse channel lists for bulk watchlist import."""

from __future__ import annotations

import csv
import io
import json
import re

_TME_LINK = re.compile(
    r"^(?:https?://)?(?:www\.)?t\.me/(?P<ref>\+?[\w-]+)/?$",
    re.IGNORECASE,
)


def _normalize_channel(raw: str) -> str | None:
    """Same rules as tg_api_connector.normalize_telegram_group_ref (no Telethon import)."""
    value = (raw or "").strip()
    if not value or value.startswith("#"):
        return None
    match = _TME_LINK.match(value)
    if match:
        ref = match.group("ref")
    elif value.startswith("@"):
        ref = value[1:]
    else:
        ref = value
    if not ref or len(ref) < 2:
        return None
    return ref


def parse_channel_lines(text: str) -> list[str]:
    """Split pasted text by newlines, commas, or semicolons; dedupe in order."""
    if not text or not str(text).strip():
        return []
    seen: set[str] = set()
    out: list[str] = []
    for line in str(text).splitlines():
        for chunk in re.split(r"[,;]", line):
            ref = _normalize_channel(chunk)
            if ref and ref not in seen:
                seen.add(ref)
                out.append(ref)
    return out


def _channels_from_csv(raw: bytes) -> list[str]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    channel_cols = {"channel_ref", "channel", "username", "url", "link", "t.me"}
    start = 0
    col_idx = 0
    if header and any(h in channel_cols for h in header):
        for i, h in enumerate(header):
            if h in channel_cols:
                col_idx = i
                break
        start = 1
    seen: set[str] = set()
    out: list[str] = []
    for row in rows[start:]:
        if not row or col_idx >= len(row):
            continue
        ref = _normalize_channel(row[col_idx])
        if ref and ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def _channels_from_json(raw: bytes) -> list[str]:
    data = json.loads(raw.decode("utf-8-sig", errors="replace"))
    items: list = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("channels", "watchlist", "items"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            raw_val = item
        elif isinstance(item, dict):
            raw_val = (
                item.get("channel_ref")
                or item.get("channel")
                or item.get("url")
                or item.get("link")
                or ""
            )
        else:
            continue
        ref = _normalize_channel(str(raw_val))
        if ref and ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def parse_channels_from_upload(uploaded) -> list[str]:
    """Parse .txt, .csv, or .json channel list from Streamlit upload."""
    raw: bytes = uploaded.getvalue()
    name = (uploaded.name or "").lower()
    if name.endswith(".json"):
        return _channels_from_json(raw)
    if name.endswith(".csv"):
        return _channels_from_csv(raw)
    return parse_channel_lines(raw.decode("utf-8-sig", errors="replace"))
