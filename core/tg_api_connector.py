import asyncio
import logging
import re
from typing import AsyncGenerator, Callable, Union

ProgressFn = Callable[[float, str], None]

from telethon import TelegramClient
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    InputConstructorInvalidError,
    MsgIdInvalidError,
    UserAlreadyParticipantError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import (
    GetFullChannelRequest,
    JoinChannelRequest,
    LeaveChannelRequest,
)
from telethon.tl.functions.messages import GetRepliesRequest
from telethon.tl.types import Channel, Chat, PeerChannel, PeerUser, User

from core.telegram_session import (
    ensure_client_on_loop,
    get_telegram_client,
    persist_telegram_session,
)
from models import FetchedChannel, FetchedUser, FetchedUserFromGroup

logger = logging.getLogger(__name__)


class GroupResolveError(Exception):
    """All entity lookup strategies failed (group may exist; session/API may be wrong)."""

    def __init__(self, raw: str, ref: str, attempts: list[dict]):
        self.raw = raw
        self.ref = ref
        self.attempts = attempts
        summary = "; ".join(
            f"{a['candidate']!r} -> {type(a['error']).__name__}: {a['error']}"
            for a in attempts
        )
        super().__init__(
            f"Could not resolve {ref!r} ({raw!r}). Attempts: {summary}"
        )


_TME_LINK = re.compile(
    r"^(?:https?://)?(?:www\.)?t\.me/(?P<ref>\+?[\w-]+)/?$",
    re.IGNORECASE,
)


def normalize_telegram_group_ref(raw: str) -> str:
    """Accept @name, name, or https://t.me/name and return a Telethon-friendly ref."""
    value = raw.strip()
    if not value:
        return value
    match = _TME_LINK.match(value)
    if match:
        return match.group("ref")
    if value.startswith("@"):
        return value[1:]
    return value


def group_entity_candidates(raw: str) -> list[str]:
    """Build Telethon lookup strings; full t.me URL first (most reliable)."""
    ref = normalize_telegram_group_ref(raw)
    if not ref:
        return []
    candidates: list[str] = []
    for item in (f"https://t.me/{ref}", f"@{ref}", ref):
        if item not in candidates:
            candidates.append(item)
    stripped = raw.strip()
    if stripped and stripped not in candidates:
        candidates.append(stripped)
    return candidates


async def ensure_telegram_client(
    client: TelegramClient,
    *,
    phone: str | None = None,
    api_id: int | str | None = None,
    api_hash: str | None = None,
    holder_id: str = "default",
) -> TelegramClient:
    if phone and api_id is not None and api_hash:
        client = await ensure_client_on_loop(
            client, phone, api_id, api_hash, holder_id=holder_id
        )
    elif not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram session is not authorized. Create the client again and verify the OTP code."
        )
    return client


def _normalize_match_key(text: str) -> str:
    """Lowercase alphanumeric slug for fuzzy title/username matching."""
    return re.sub(r"[^0-9a-z]+", "", text.casefold())


def _ref_title_tokens(ref: str) -> list[str]:
    """Meaningful tokens from a @username-style ref for title matching."""
    return [t for t in re.split(r"[_\s]+", ref.casefold()) if len(t) >= 3]


async def resolve_group_from_dialogs(
    client: TelegramClient, ref: str
) -> Union[Channel, Chat, None]:
    """Find a group the logged-in user already has in their chat list."""
    ref_lower = ref.casefold()
    ref_key = _normalize_match_key(ref)
    tokens = _ref_title_tokens(ref)

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if not isinstance(entity, (Channel, Chat)):
            continue

        title = getattr(entity, "title", None) or getattr(dialog, "name", None) or ""

        username = getattr(entity, "username", None)
        if username and username.casefold() == ref_lower:
            logger.info(
                "Resolved %r from dialogs via username -> %s",
                ref,
                title or entity.id,
            )
            return entity

        title_key = _normalize_match_key(title)
        if ref_key and title_key == ref_key:
            logger.info(
                "Resolved %r from dialogs via title_exact -> %s",
                ref,
                title or entity.id,
            )
            return entity

        if tokens and title:
            title_lower = title.casefold()
            if all(tok in title_lower for tok in tokens):
                logger.info(
                    "Resolved %r from dialogs via title_tokens -> %s",
                    ref,
                    title or entity.id,
                )
                return entity

    return None


async def resolve_group_from_search(
    client: TelegramClient, ref: str
) -> Union[Channel, Chat, None]:
    """Global search fallback when public username and dialogs did not match."""
    from telethon.tl.functions.contacts import SearchRequest

    ref_lower = ref.casefold()
    ref_key = _normalize_match_key(ref)
    try:
        result = await client(SearchRequest(q=ref, limit=20))
    except Exception as exc:
        logger.info("SearchRequest(%r) failed: %s: %s", ref, type(exc).__name__, exc)
        return None

    for chat in result.chats:
        if not isinstance(chat, (Channel, Chat)):
            continue
        username = getattr(chat, "username", None)
        if username and username.casefold() == ref_lower:
            logger.info(
                "Resolved %r from search via username -> %s",
                ref,
                getattr(chat, "title", chat.id),
            )
            return chat
        title = getattr(chat, "title", None) or ""
        if ref_key and _normalize_match_key(title) == ref_key:
            logger.info(
                "Resolved %r from search via title_exact -> %s",
                ref,
                title or chat.id,
            )
            return chat
    return None


async def resolve_group_entity(client: TelegramClient, raw: str) -> Union[Channel, Chat]:
    from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest

    await ensure_telegram_client(client)

    ref = normalize_telegram_group_ref(raw)
    if not ref:
        raise ValueError("No group link or username provided")

    if ref.startswith("+"):
        invite_hash = ref[1:]
        try:
            await client(CheckChatInviteRequest(hash=invite_hash))
        except Exception:
            pass
        updates = await client(ImportChatInviteRequest(hash=invite_hash))
        if updates.chats:
            return updates.chats[0]
        raise ValueError(f"Could not join group from invite link {raw!r}")

    attempts: list[dict] = []

    dialog_entity = await resolve_group_from_dialogs(client, ref)
    if dialog_entity is not None:
        return dialog_entity
    attempts.append(
        {
            "candidate": "iter_dialogs (username/title)",
            "error": ValueError("No matching group in your Telegram chat list"),
        }
    )

    for candidate in group_entity_candidates(raw):
        try:
            entity = await client.get_entity(candidate)
            if isinstance(entity, (Channel, Chat)):
                logger.info(
                    "Resolved %r using %r -> %s (%s members)",
                    raw,
                    candidate,
                    getattr(entity, "title", entity.id),
                    getattr(entity, "participants_count", "?"),
                )
                return entity
            attempts.append(
                {
                    "candidate": candidate,
                    "error": ValueError(
                        f"Resolved to {type(entity).__name__}, expected Channel or Chat"
                    ),
                }
            )
        except Exception as exc:
            attempts.append({"candidate": candidate, "error": exc})
            logger.info("get_entity(%r) failed: %s: %s", candidate, type(exc).__name__, exc)

    join_candidate = f"JoinChannelRequest(@{ref})"
    try:
        join_target = ref if ref.startswith("@") else f"@{ref}"
        joined = await client(JoinChannelRequest(join_target))
        if getattr(joined, "chats", None):
            entity = joined.chats[0]
            if isinstance(entity, (Channel, Chat)):
                logger.info("Resolved %r via JoinChannelRequest", ref)
                return entity
    except UserAlreadyParticipantError as exc:
        attempts.append({"candidate": join_candidate, "error": exc})
    except Exception as exc:
        attempts.append({"candidate": join_candidate, "error": exc})

    dialog_entity = await resolve_group_from_dialogs(client, ref)
    if dialog_entity is not None:
        return dialog_entity

    search_entity = await resolve_group_from_search(client, ref)
    if search_entity is not None:
        return search_entity
    attempts.append(
        {
            "candidate": f"contacts.SearchRequest({ref!r})",
            "error": ValueError("No matching public group in global search"),
        }
    )

    raise GroupResolveError(raw, ref, attempts)


async def ensure_joined(client: TelegramClient, entity: Union[Channel, Chat]) -> None:
    try:
        await client(JoinChannelRequest(entity))
    except UserAlreadyParticipantError:
        pass
    except Exception as exc:
        logger.warning(
            "Could not join %s (%s); continuing anyway",
            getattr(entity, "title", entity.id),
            exc,
        )


def user_alias(entity: Union[User, Channel, Chat]) -> str:
    if isinstance(entity, User):
        name = entity.first_name or ""
        surname = entity.last_name or ""
        return f"{name} {surname}".strip()
    if isinstance(entity, (Channel, Chat)):
        return entity.title or ""
    return ""


def _user_tuple(user: User) -> tuple[int, str | None, str]:
    return (int(user.id), user.username, user_alias(user))


def _message_id_chunks(message_ids: list[int], size: int = 100) -> list[list[int]]:
    return [message_ids[i : i + size] for i in range(0, len(message_ids), size)]


async def _resolve_users_via_group_messages(
    client: TelegramClient,
    entity: Union[Channel, Chat],
    pending: set[int],
    message_ids: list[int],
    on_progress: ProgressFn | None = None,
    progress_base: float = 0.1,
    progress_span: float = 0.7,
) -> dict[int, tuple[int, str | None, str]]:
    """Resolve user ids from stored message ids in the group (Telethon fills senders)."""
    resolved: dict[int, tuple[int, str | None, str]] = {}
    if not pending or not message_ids:
        return resolved
    chunks = _message_id_chunks(message_ids)
    total_chunks = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        try:
            messages = await client.get_messages(entity, ids=chunk)
        except Exception as exc:
            logger.warning("get_messages batch failed: %s", exc)
            continue
        for message in messages or []:
            if message is None:
                continue
            sender = message.sender
            if isinstance(sender, User) and sender.id in pending:
                resolved[int(sender.id)] = _user_tuple(sender)
        if on_progress and (i == 1 or i == total_chunks or i % 5 == 0):
            frac = progress_base + progress_span * (i / max(total_chunks, 1))
            _report_progress(
                on_progress,
                frac,
                f"Resolved from group messages: {len(resolved)}/{len(pending)}",
            )
        if len(resolved) >= len(pending):
            break
    return resolved


async def _resolve_telegram_user(
    client: TelegramClient,
    user_id: int,
) -> tuple[int, str | None, str] | None:
    try:
        user = await client.get_entity(user_id)
    except (ValueError, TypeError) as exc:
        logger.debug("get_entity(%s) failed: %s", user_id, exc)
        return None
    if isinstance(user, User):
        return _user_tuple(user)
    return None


async def is_user_authorized(client):
    return await client.is_user_authorized()


async def create_client(
    phone_number: str,
    API_ID: int | str,
    API_HASH: str,
    *,
    holder_id: str = "default",
    force_new: bool = False,
):
    return await get_telegram_client(
        phone_number,
        API_ID,
        API_HASH,
        holder_id=holder_id,
        force_new=force_new,
    )


async def generate_otp(client_tg, phone_number):
    result = await client_tg.send_code_request(phone=phone_number)
    phone_hash = result.phone_code_hash
    return client_tg, phone_hash


async def verify_otp(client, phone, secret_code, phone_hash):
    if not client.is_connected():
        await client.connect()
    await client.sign_in(
        phone=phone,
        code=secret_code,
        phone_code_hash=phone_hash,
    )
    try:
        persist_telegram_session(phone, client)
    except Exception as exc:
        logger.exception("Failed to save Telegram session after OTP for %s", phone)
        raise RuntimeError(
            f"Signed in to Telegram but could not save session file: {exc}"
        ) from exc


async def send_message(client, message, user="me"):
    await client.send_message(entity=user, message=message)


async def get_messages(client, user="me"):
    output = ""
    async for message in client.iter_messages(entity=user):
        output += f"""{message.id}\n{message.text}\n"""
        if message.buttons:
            output += f"""{[button[0].text for button in message.buttons]}"""
    return output


def _report_progress(on_progress: ProgressFn | None, frac: float, text: str) -> None:
    if on_progress is not None:
        on_progress(min(max(frac, 0.0), 1.0), text)


async def _participants_count(
    client: TelegramClient, entity: Union[Channel, Chat]
) -> int | None:
    try:
        if isinstance(entity, Channel):
            full = await client(GetFullChannelRequest(entity))
            return getattr(full.full_chat, "participants_count", None)
    except Exception:
        logger.debug("Could not fetch participant count", exc_info=True)
    count = getattr(entity, "participants_count", None)
    return int(count) if count is not None else None


async def _users_from_messages(
    client: TelegramClient,
    entity: Union[Channel, Chat],
    limit: int,
    on_progress: ProgressFn | None = None,
) -> list[tuple[int, str | None, str]]:
    _report_progress(on_progress, 0.05, f"Fetching up to {limit} messages…")
    messages = await client.get_messages(entity, limit=limit)
    user_by_id: dict[int, tuple[int, str | None, str]] = {}
    for message in messages:
        sender = message.sender
        if isinstance(sender, User):
            user_by_id[int(sender.id)] = _user_tuple(sender)
        elif isinstance(message.from_id, PeerUser):
            uid = message.from_id.user_id
            if uid not in user_by_id:
                try:
                    sender = await message.get_sender()
                except Exception:
                    sender = None
                if isinstance(sender, User):
                    user_by_id[uid] = _user_tuple(sender)
    _report_progress(
        on_progress, 0.15, f"Found {len(user_by_id)} unique authors in messages"
    )
    user_list = list(user_by_id.values())
    if on_progress:
        _report_progress(
            on_progress, 0.95, f"Resolved {len(user_list)} users from messages"
        )
    _report_progress(
        on_progress, 1.0, f"Done: {len(user_list)} users from messages"
    )
    return user_list


def _participants_fetch_result(
    users: list[tuple],
    group_title: str | None,
    resolved: "ResolvedGroup",
) -> tuple[list[tuple[int, str | None, str]], str | None, "ResolvedGroup"]:
    """Always return (members, title, resolved) with normalized member rows."""
    from core.group_identity import ResolvedGroup, dedupe_member_tuples

    if not isinstance(resolved, ResolvedGroup):
        raise TypeError("resolved must be a ResolvedGroup instance")
    return dedupe_member_tuples(users), group_title, resolved


async def get_all_participants(
    client: TelegramClient,
    channel: str,
    message_fallback_limit: int = 10000,
    on_progress: ProgressFn | None = None,
) -> tuple[list[tuple[int, str | None, str]], str | None, "ResolvedGroup"]:
    """Return (members, group_title, resolved identity) for the channel/chat."""
    from core.group_identity import (
        ResolvedGroup,
        dedupe_member_tuples,
        group_identity_from_entity,
    )

    _report_progress(on_progress, 0.02, "Resolving group…")
    await ensure_telegram_client(client)
    entity = await resolve_group_entity(client, channel)
    resolved = group_identity_from_entity(entity, channel)
    _report_progress(on_progress, 0.06, "Joining group if needed…")
    await ensure_joined(client, entity)
    group_title = getattr(entity, "title", None)
    total = await _participants_count(client, entity)
    resolved.participants_count = total

    users: list[tuple[int, str | None, str]] = []
    count = 0
    total_hint = f" (~{total})" if total else ""
    _report_progress(on_progress, 0.08, f"Fetching members{total_hint}…")
    member_list_failed = False
    try:
        async for user in client.iter_participants(entity=entity):
            if isinstance(user, User):
                users.append(_user_tuple(user))
                count += 1
                if on_progress and (count == 1 or count % 25 == 0):
                    if total and total > 0:
                        frac = 0.08 + 0.87 * min(count / total, 1.0)
                        _report_progress(
                            on_progress, frac, f"Members: {count} / ~{total}"
                        )
                    else:
                        frac = min(0.08 + count / 10000 * 0.87, 0.95)
                        _report_progress(on_progress, frac, f"Members: {count}…")
    except ChatAdminRequiredError:
        logger.info(
            "Member list restricted for %s; using message history",
            getattr(entity, "title", channel),
        )
        member_list_failed = True
    except ValueError as exc:
        logger.warning(
            "iter_participants failed for %s (%s); using message history",
            getattr(entity, "title", channel),
            exc,
        )
        member_list_failed = True
    except Exception:
        if users:
            _report_progress(on_progress, 1.0, f"Done: {len(users)} members")
            return _participants_fetch_result(users, group_title, resolved)
        raise

    if users:
        _report_progress(on_progress, 1.0, f"Done: {len(users)} members")
        return _participants_fetch_result(users, group_title, resolved)

    if member_list_failed or not users:
        logger.info(
            "No members from iter_participants for %s; using message history",
            getattr(entity, "title", channel),
        )
        _report_progress(
            on_progress, 0.4, "Member list restricted; using message history…"
        )
    users = await _users_from_messages(
        client, entity, message_fallback_limit, on_progress=on_progress
    )
    return _participants_fetch_result(users, group_title, resolved)


_MESSAGE_BATCH_SIZE = 100


async def fetch_group_messages(
    client: TelegramClient,
    channel: str,
    limit: int,
    on_progress: ProgressFn | None = None,
) -> tuple[int, int, str | None, "ResolvedGroup"]:
    """Fetch messages from Telegram and persist new ones to Neo4j."""
    from core.group_identity import group_identity_from_entity
    from db.dal import GraphManager

    _report_progress(on_progress, 0.02, "Resolving group…")
    await ensure_telegram_client(client)
    entity = await resolve_group_entity(client, channel)
    resolved = group_identity_from_entity(entity, channel)
    group_ref = resolved.canonical_id
    _report_progress(on_progress, 0.06, "Joining group if needed…")
    await ensure_joined(client, entity)
    group_title = getattr(entity, "title", None)

    existing_ids = GraphManager.stored_message_ids(group_ref)
    min_id = GraphManager.min_stored_message_id(group_ref)
    iter_kwargs: dict = {"limit": None}
    if min_id is not None:
        iter_kwargs["offset_id"] = min_id - 1
        _report_progress(
            on_progress,
            0.08,
            f"Fetching up to {limit} older messages (before id {min_id})…",
        )
    else:
        _report_progress(on_progress, 0.08, f"Fetching up to {limit} new messages…")

    batch: list[dict] = []
    inserted_total = 0
    skipped_existing = 0
    new_count = 0

    from core.message_links import truncate_message_text
    from core.telegram_urls import entity_message_url

    async for message in client.iter_messages(entity, **iter_kwargs):
        if message.id in existing_ids:
            skipped_existing += 1
            continue

        from_user_id = None
        if isinstance(message.from_id, PeerUser):
            from_user_id = message.from_id.user_id
        date_str = message.date.isoformat() if message.date else None

        batch.append(
            {
                "message_id": message.id,
                "from_user_id": from_user_id,
                "date": date_str,
                "text": truncate_message_text(message.message),
                "telegram_url": entity_message_url(group_ref, message.id, entity),
            }
        )
        existing_ids.add(message.id)
        new_count += 1

        if len(batch) >= _MESSAGE_BATCH_SIZE:
            inserted_total += GraphManager.persist_group_messages(
                group_ref, batch, group_meta=resolved
            )
            batch = []
        if on_progress and (new_count == 1 or new_count % 25 == 0):
            frac = min(0.08 + 0.92 * (new_count / max(limit, 1)), 0.99)
            _report_progress(
                on_progress,
                frac,
                f"Stored {new_count}/{limit} new messages "
                f"({skipped_existing} already in DB skipped)…",
            )
        if new_count >= limit:
            break

    if batch:
        inserted_total += GraphManager.persist_group_messages(
            group_ref, batch, group_meta=resolved
        )

    _report_progress(
        on_progress,
        1.0,
        f"Done: {inserted_total} new, {skipped_existing} skipped (already in DB)",
    )
    return inserted_total, skipped_existing, group_title, resolved


async def extract_users_from_stored_messages(
    client: TelegramClient,
    group_ref: str,
    on_progress: ProgressFn | None = None,
) -> tuple[list[tuple[int, str | None, str]], str | None, "ResolvedGroup"]:
    """Resolve authors from Neo4j messages where users_processed is false."""
    from core.group_identity import ResolvedGroup, group_identity_from_entity
    from db.dal import GraphManager

    norm_ref = normalize_telegram_group_ref(group_ref)
    group_resolved = ResolvedGroup(canonical_id=norm_ref)
    ref = norm_ref
    _report_progress(on_progress, 0.05, "Loading unprocessed message authors…")
    message_rows = GraphManager.list_unprocessed_messages_for_users(norm_ref)
    author_ids = sorted({row["from_user_id"] for row in message_rows})
    message_ids = [row["message_id"] for row in message_rows]

    group_entity: Union[Channel, Chat] | None = None
    group_title: str | None = None
    try:
        await ensure_telegram_client(client)
        group_entity = await resolve_group_entity(client, group_ref)
        group_title = getattr(group_entity, "title", None)
        group_resolved = group_identity_from_entity(group_entity, group_ref)
        ref = group_resolved.canonical_id
        if ref != norm_ref:
            alt_rows = GraphManager.list_unprocessed_messages_for_users(ref)
            if alt_rows:
                message_rows = alt_rows
                author_ids = sorted({row["from_user_id"] for row in message_rows})
                message_ids = [row["message_id"] for row in message_rows]
    except Exception:
        logger.debug("Could not resolve group for message-based user lookup", exc_info=True)

    if not author_ids:
        _report_progress(on_progress, 1.0, "No unprocessed authors")
        return [], group_title, group_resolved

    known_users = GraphManager.lookup_users_by_ids(author_ids)
    user_by_id: dict[int, tuple[int, str | None, str]] = {}
    pending: set[int] = set()
    for user_id in author_ids:
        existing = known_users.get(user_id)
        if existing and (existing[1] or existing[2]):
            user_by_id[user_id] = existing
        else:
            pending.add(user_id)

    _report_progress(
        on_progress,
        0.1,
        f"Resolving {len(pending)} authors via Telegram "
        f"({len(user_by_id)} already in Neo4j)…",
    )

    if group_entity and pending and message_ids:
        from_messages = await _resolve_users_via_group_messages(
            client,
            group_entity,
            pending,
            message_ids,
            on_progress=on_progress,
            progress_base=0.1,
            progress_span=0.65,
        )
        user_by_id.update(from_messages)
        pending -= set(from_messages.keys())

    total_resolve = len(pending)
    for i, user_id in enumerate(sorted(pending), start=1):
        user_row = await _resolve_telegram_user(client, user_id)
        if user_row:
            user_by_id[user_id] = user_row
        else:
            user_by_id[user_id] = (user_id, None, "")
            logger.info(
                "Could not resolve user %s for group %s; saving id only",
                user_id,
                ref,
            )
        if on_progress and (i == 1 or i == total_resolve or i % 10 == 0):
            frac = 0.75 + 0.2 * (i / max(total_resolve, 1))
            _report_progress(
                on_progress,
                frac,
                f"Fallback resolve: {i}/{total_resolve}",
            )

    user_list = [user_by_id[uid] for uid in author_ids if uid in user_by_id]
    unresolved = sum(1 for u in user_list if not u[1] and not u[2])
    _report_progress(
        on_progress,
        1.0,
        f"Done: {len(user_list)} users"
        + (f" ({unresolved} id-only)" if unresolved else ""),
    )
    return user_list, group_title, group_resolved


async def extract_endorsements_from_stored_messages(
    client: TelegramClient,
    group_ref: str,
    on_progress: ProgressFn | None = None,
) -> tuple[int, int, "ResolvedGroup"]:
    """Parse Telegram links from unprocessed messages; persist ENDORSES edges."""
    from core.group_identity import ResolvedGroup, group_identity_from_entity
    from core.message_links import extract_telegram_links, normalize_telegram_group_ref
    from db.dal import GraphManager

    norm_ref = normalize_telegram_group_ref(group_ref)
    group_resolved = ResolvedGroup(canonical_id=norm_ref)
    try:
        await ensure_telegram_client(client)
        entity = await resolve_group_entity(client, group_ref)
        group_resolved = group_identity_from_entity(entity, group_ref)
    except Exception:
        logger.debug("Could not resolve group for endorsements", exc_info=True)
    ref = group_resolved.canonical_id
    _report_progress(on_progress, 0.05, "Loading messages for link extraction…")
    messages = GraphManager.list_unprocessed_messages_for_links(ref)
    if not messages and ref != norm_ref:
        messages = GraphManager.list_unprocessed_messages_for_links(norm_ref)
    if not messages:
        _report_progress(on_progress, 1.0, "No messages pending link extraction")
        return 0, 0, group_resolved

    from core.telegram_urls import group_url

    links: list[dict] = []
    total = len(messages)
    for i, msg in enumerate(messages, start=1):
        for link in extract_telegram_links(msg["text"], source_ref=ref):
            target_ref = link["target_ref"]
            links.append(
                {
                    "target_ref": target_ref,
                    "target_telegram_url": group_url(target_ref),
                    "link_raw": link["link_raw"],
                    "message_id": msg["message_id"],
                }
            )
        if on_progress and (i == 1 or i == total or i % 50 == 0):
            frac = 0.1 + 0.6 * (i / max(total, 1))
            _report_progress(
                on_progress, frac, f"Parsed links in {i}/{total} messages…"
            )

    _report_progress(on_progress, 0.75, f"Saving {len(links)} endorsements to Neo4j…")
    inserted = GraphManager.persist_endorsements(ref, links)
    marked = GraphManager.mark_messages_links_processed(ref)
    _report_progress(
        on_progress,
        1.0,
        f"Done: {inserted} new endorsements, {marked} messages marked",
    )
    return inserted, len(links), group_resolved


async def get_telegram_authorizations(client: TelegramClient) -> list[dict]:
    """List active Telegram account sessions (device list from Telegram)."""
    from telethon.tl.functions.account import GetAuthorizationsRequest

    await ensure_telegram_client(client)
    result = await client(GetAuthorizationsRequest())
    rows: list[dict] = []
    for auth in result.authorizations:
        rows.append(
            {
                "hash": auth.hash,
                "device": auth.device_model or auth.app_name or "Unknown",
                "platform": auth.platform or "",
                "current": bool(getattr(auth, "current", False)),
                "date_active": auth.date_active.isoformat()
                if auth.date_active
                else "",
                "date_created": auth.date_created.isoformat()
                if auth.date_created
                else "",
            }
        )
    return rows


class ChannelParser:
    def __init__(self, client: TelegramClient):
        self.client = client

    async def start(self) -> None:
        await self.client.start()

    async def about_me(self) -> User:
        return await self.client.get_me()

    async def update_name(self, name: str) -> None:
        await self.client(UpdateProfileRequest(first_name=name))

    async def send_message(self, user_id: str, message: str) -> None:
        await self.client.send_message(user_id, message)

    async def join_channel(self, channel: Union[str, int]) -> None:
        if isinstance(channel, int):
            await self.client(JoinChannelRequest(channel=channel))
        else:
            await self.client(JoinChannelRequest(channel=f"@{channel}"))

    async def leave_channel(self, channel: Union[str, int]) -> None:
        if isinstance(channel, int):
            await self.client(LeaveChannelRequest(channel=channel))
        else:
            await self.client(LeaveChannelRequest(channel=f"@{channel}"))

    async def get_all_participants(self, channel: Union[str, int]) -> FetchedChannel:
        channel_data = FetchedChannel()
        try:
            if isinstance(channel, int):
                entity = await self.client.get_entity(channel)
            else:
                entity = await resolve_group_entity(self.client, channel)
            channel_data.id = entity.id
            channel_data.title = entity.title
            if entity.broadcast:
                print("Chanel")
                users_messages_set = await self.get_comments_from_channel(
                    entity
                )  # here is data with messages !!!
                user_set = {
                    (user.user_id, user.user_name, user.first_name)
                    for user in users_messages_set
                }
                user_array = list(user_set)
                channel_data.user_set = user_array
                channel_data.user_counts = len(user_array)
                return channel_data
            else:
                print("Group")
                async for members in self.get_chunked_participants(entity.id):
                    channel_data.user_set.extend(
                        [
                            (
                                user.id,
                                user.username or "NULL",
                                user.first_name or "NULL",
                            )
                            async for user in members
                        ]
                    )
                channel_data.user_counts = len(channel_data.user_set)
                print(channel_data.user_counts)
                users_messages_set = await self.get_comments_from_chat(
                    entity
                )  # here is data with messages !!!
                return channel_data
        except (
            ChannelInvalidError,
            ChannelPrivateError,
            ChatAdminRequiredError,
            InputConstructorInvalidError,
            TimeoutError,
        ) as e:
            print(str(e))

    async def get_chunked_participants(
        self, channel: Union[str, int], key_word: str = ""  # CONFIG
    ) -> AsyncGenerator:
        participants = self.client.iter_participants(entity=channel, search=key_word)
        yield participants

    async def get_comments_from_chat(
        self, chat_entity: Chat
    ) -> list[FetchedUserFromGroup]:
        messages = self.client.iter_messages(chat_entity, limit=1)  # CONFIG
        users_messages_set = []
        async for message in messages:
            try:
                user_message = FetchedUserFromGroup(
                    user_id=message.from_id.user_id,
                    message=message.message if message.message else "NULL",
                    channel_id=chat_entity.id if chat_entity.id else "NULL",
                    channel_title=chat_entity.title if chat_entity.title else "NULL",
                )
                users_messages_set.append(user_message)
            except AttributeError:
                ...
        return users_messages_set

    async def get_comments_from_channel(
        self, channel_entity: Channel
    ) -> list[FetchedUser]:
        posts = await self.client.get_messages(channel_entity, limit=50)  # CONFIG
        messages = []
        for post in posts:
            if post.id:
                try:
                    channel_messages = await self.client(
                        GetRepliesRequest(
                            peer=channel_entity,
                            msg_id=post.id,
                            offset_id=0,
                            limit=0,
                            max_id=0,
                            min_id=0,
                            hash=0,
                            offset_date=None,
                            add_offset=0,
                        )
                    )
                    messages.extend(channel_messages.messages)
                except MsgIdInvalidError:
                    pass
        users_messages_set = []
        for message in messages:
            if isinstance(message.from_id, PeerUser):
                user_id = message.from_id.user_id
                user = await self.client.get_entity(user_id)
                user_message = FetchedUser(
                    user_id=user.id,
                    user_name=user.username if user.username else "NULL",
                    first_name=user.first_name if user.first_name else "NULL",
                    last_name=user.last_name if user.last_name else "NULL",
                    phone=user.phone if user.phone else "NULL",
                    message=message.message if message.message else "NULL",
                    channel_id=channel_entity.id if channel_entity.id else "NULL",
                    channel_title=(
                        channel_entity.title if channel_entity.title else "NULL"
                    ),
                )
                users_messages_set.append(user_message)
        return users_messages_set
