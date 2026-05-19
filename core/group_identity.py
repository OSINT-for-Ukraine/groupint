"""Canonical Neo4j Group.id from resolved Telethon entities."""

from __future__ import annotations

from dataclasses import dataclass, field

from telethon.tl.types import Channel, Chat

from core.message_links import normalize_telegram_group_ref
from core.telegram_urls import group_url

MAX_MEMBER_PERSIST = 500_000


@dataclass
class ResolvedGroup:
    canonical_id: str
    title: str | None = None
    username: str | None = None
    telegram_peer_id: int | None = None
    telegram_url: str = ""
    aliases: list[str] = field(default_factory=list)
    participants_count: int | None = None


def canonical_group_id_from_entity(entity: Channel | Chat) -> str:
    username = getattr(entity, "username", None)
    if username and str(username).strip():
        return normalize_telegram_group_ref(str(username))
    peer_id = getattr(entity, "id", None)
    if peer_id is not None:
        return f"peer:{int(peer_id)}"
    title = getattr(entity, "title", None) or "unknown"
    return normalize_telegram_group_ref(str(title)) or f"peer:unknown"


def group_identity_from_entity(
    entity: Channel | Chat,
    raw_input: str | None = None,
) -> ResolvedGroup:
    canonical_id = canonical_group_id_from_entity(entity)
    username = getattr(entity, "username", None)
    peer_id = getattr(entity, "id", None)
    title = getattr(entity, "title", None)
    aliases: list[str] = []
    if raw_input:
        stripped = raw_input.strip()
        norm = normalize_telegram_group_ref(stripped)
        for candidate in (stripped, norm, canonical_id):
            if candidate and candidate not in aliases and candidate != canonical_id:
                aliases.append(candidate)
    url = group_url(canonical_id) if canonical_id and not canonical_id.startswith("peer:") else ""
    if not url and username:
        url = group_url(str(username))
    return ResolvedGroup(
        canonical_id=canonical_id,
        title=title,
        username=str(username) if username else None,
        telegram_peer_id=int(peer_id) if peer_id is not None else None,
        telegram_url=url,
        aliases=aliases,
    )


def pick_winner_group_id(ids: list[str]) -> str:
    """Prefer public username id over peer: over arbitrary title strings."""
    if not ids:
        return ""
    username_ids = [
        g
        for g in ids
        if g and not g.startswith("peer:") and "/" not in g and " " not in g
    ]
    if username_ids:
        return sorted(username_ids, key=lambda x: (len(x), x))[0]
    peer_ids = [g for g in ids if g.startswith("peer:")]
    if peer_ids:
        return sorted(peer_ids)[0]
    return sorted(ids)[0]


def validate_member_count_for_persist(
    user_count: int,
    participants_count: int | None = None,
) -> None:
    if user_count > MAX_MEMBER_PERSIST:
        raise ValueError(
            f"Refusing to save {user_count:,} members (limit {MAX_MEMBER_PERSIST:,}). "
            "This usually means a broadcast channel was scraped as a member list."
        )
    if participants_count and participants_count > 0 and user_count > 2 * participants_count:
        raise ValueError(
            f"Member count {user_count:,} is more than double Telegram's reported "
            f"participants ({participants_count:,}). Aborting to avoid bad data."
        )


def dedupe_member_tuples(
    users: list[tuple],
) -> list[tuple[int, str | None, str]]:
    by_id: dict[int, tuple[int, str | None, str]] = {}
    for row in users:
        if not row or row[0] is None:
            continue
        uid = int(row[0])
        username = row[1] if len(row) > 1 else None
        alias = row[2] if len(row) > 2 else ""
        if uid in by_id:
            prev = by_id[uid]
            by_id[uid] = (
                uid,
                username or prev[1],
                alias or prev[2],
            )
        else:
            by_id[uid] = (uid, username, alias)
    return list(by_id.values())
