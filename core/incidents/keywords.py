"""Keyword prefilter for incident pipeline (global + per-channel, OR match)."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_MIN_KEYWORD_LEN = 2
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def parse_keyword_lines(raw: str) -> list[str]:
    """Split textarea input by newlines and commas."""
    if not raw or not str(raw).strip():
        return []
    parts: list[str] = []
    for line in str(raw).splitlines():
        for chunk in line.split(","):
            word = chunk.strip()
            if len(word) >= _MIN_KEYWORD_LEN:
                parts.append(word)
    return _dedupe_keywords(parts)


def _dedupe_keywords(words: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        key = normalize_text(w.strip())
        if len(key) < _MIN_KEYWORD_LEN or key in seen:
            continue
        seen.add(key)
        out.append(w.strip())
    return out


def build_effective_keywords(
    *,
    global_keywords: list[str],
    global_keywords_enabled: bool,
    channel_keywords: list[str],
    channel_keywords_enabled: bool,
    use_global_keywords: bool = True,
) -> list[str]:
    """Union of global and channel lists per plan rules."""
    effective: list[str] = []
    if use_global_keywords and global_keywords_enabled:
        effective.extend(global_keywords or [])
    elif not use_global_keywords:
        effective = []
    if channel_keywords_enabled:
        effective.extend(channel_keywords or [])
    return _dedupe_keywords(effective)


def message_matches_keywords(text: str, keywords: list[str]) -> bool:
    """True if any keyword matches (substring or token equality)."""
    if not keywords:
        return True
    norm = normalize_text(text or "")
    if not norm:
        return False
    tokens = set(_TOKEN_RE.findall(norm))
    for kw in keywords:
        nkw = normalize_text(kw)
        if len(nkw) < _MIN_KEYWORD_LEN:
            continue
        if nkw in norm:
            return True
        if nkw in tokens:
            return True
    return False
