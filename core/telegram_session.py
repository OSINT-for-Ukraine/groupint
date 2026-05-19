"""Per-phone StringSession storage and a single TelegramClient per account in-process."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import portalocker
from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(
    os.environ.get("GROUPINT_SESSIONS_DIR", "/home/appuser/.groupint/sessions")
)
SESSION_FILE_SUFFIX = ".string"
METADATA_SUFFIX = ".meta"

_PHONE_SAFE = re.compile(r"[^0-9a-zA-Z]+")
_META_LINE = re.compile(r"^([a-z_]+)=(.*)$", re.IGNORECASE)


class SessionInUseError(RuntimeError):
    """Another browser tab or user is already connected with this phone in this process."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone.strip())
    return digits or _PHONE_SAFE.sub("_", phone.strip())[:64] or "unknown"


def session_file_path(phone: str) -> Path:
    return SESSIONS_DIR / f"{sanitize_phone(phone)}{SESSION_FILE_SUFFIX}"


def metadata_file_path(phone: str) -> Path:
    return SESSIONS_DIR / f"{sanitize_phone(phone)}{METADATA_SUFFIX}"


def session_file_exists(phone: str) -> bool:
    path = session_file_path(phone)
    if not path.is_file():
        return False
    return bool(path.read_text(encoding="utf-8").strip())


def ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not os.access(SESSIONS_DIR, os.W_OK):
        raise PermissionError(
            f"Cannot write Telegram sessions to {SESSIONS_DIR!r}. "
            "Restart the container so the entrypoint can fix volume permissions."
        )


def _read_metadata(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _META_LINE.match(line.strip())
        if match:
            data[match.group(1).lower()] = match.group(2).strip()
    return data


def _write_metadata(path: Path, fields: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in sorted(fields.items()) if value]
    with portalocker.Lock(path, mode="w", timeout=10):
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _phone_from_meta_or_stem(meta: dict[str, str], stem: str) -> str:
    return meta.get("phone") or stem


def list_saved_phones() -> list[str]:
    return [s["phone_key"] for s in list_sessions()]


def list_sessions() -> list[dict]:
    """All saved StringSessions with metadata for the dashboard."""
    ensure_sessions_dir()
    sessions: list[dict] = []
    for path in sorted(SESSIONS_DIR.glob(f"*{SESSION_FILE_SUFFIX}")):
        if not path.read_text(encoding="utf-8").strip():
            continue
        stem = path.stem
        meta_path = SESSIONS_DIR / f"{stem}{METADATA_SUFFIX}"
        meta = _read_metadata(meta_path)
        phone_display = _phone_from_meta_or_stem(meta, stem)
        sessions.append(
            {
                "phone_key": stem,
                "phone": phone_display,
                "string_path": str(path),
                "meta_path": str(meta_path),
                "authorized_at": meta.get("authorized_at", ""),
                "last_used_at": meta.get("last_used_at", ""),
                "last_check_at": meta.get("last_check_at", ""),
                "last_check_ok": meta.get("last_check_ok", "").lower() == "true",
            }
        )
    sessions.sort(
        key=lambda s: s.get("last_used_at") or s.get("authorized_at") or "",
        reverse=True,
    )
    return sessions


def touch_session(phone: str, *, authorized: bool | None = None) -> None:
    ensure_sessions_dir()
    meta_path = metadata_file_path(phone)
    meta = _read_metadata(meta_path)
    now = _utc_now_iso()
    meta["phone"] = phone.strip()
    meta["last_used_at"] = now
    if authorized is True:
        meta["authorized_at"] = meta.get("authorized_at") or now
        meta["last_check_ok"] = "true"
        meta["last_check_at"] = now
    _write_metadata(meta_path, meta)


def update_session_check(phone: str, ok: bool) -> None:
    ensure_sessions_dir()
    meta_path = metadata_file_path(phone)
    meta = _read_metadata(meta_path)
    meta["phone"] = phone.strip()
    meta["last_check_at"] = _utc_now_iso()
    meta["last_check_ok"] = "true" if ok else "false"
    _write_metadata(meta_path, meta)


def delete_session_files(phone: str) -> None:
    for path in (session_file_path(phone), metadata_file_path(phone)):
        if path.is_file():
            path.unlink()


def session_health_fraction(session: dict) -> float:
    """0.0 = re-login required; 1.0 = authorized with no scheduled expiry."""
    if session.get("last_check_ok"):
        return 1.0
    if session.get("authorized_at"):
        return 0.35
    return 0.0


def load_string_session(phone: str) -> StringSession | None:
    path = session_file_path(phone)
    if not path.is_file():
        return None
    ensure_sessions_dir()
    with portalocker.Lock(path, mode="r", timeout=10):
        data = path.read_text(encoding="utf-8").strip()
    if not data:
        return None
    return StringSession(data)


def save_string_session(phone: str, client: TelegramClient) -> None:
    ensure_sessions_dir()
    path = session_file_path(phone)
    session_string = client.session.save()
    with portalocker.Lock(path, mode="w", timeout=10):
        path.write_text(session_string, encoding="utf-8")
    touch_session(phone, authorized=True)
    logger.info("Saved StringSession for phone %s to %s", sanitize_phone(phone), path)


def _lock_key(path: Path) -> str:
    return str(path.resolve())


class ClientRegistry:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._clients: dict[str, TelegramClient] = {}
        self._holders: dict[str, str] = {}

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def clear_clients(self) -> None:
        """Drop cached clients when the asyncio loop identity changes (sync)."""
        self._clients.clear()
        self._holders.clear()

    async def _disconnect_key(self, key: str) -> None:
        client = self._clients.pop(key, None)
        self._holders.pop(key, None)
        if client is not None and client.is_connected():
            await client.disconnect()

    async def disconnect_phone(self, phone: str) -> None:
        key = _lock_key(session_file_path(phone))
        async with self._get_lock(key):
            await self._disconnect_key(key)

    async def disconnect_holder(self, holder_id: str) -> None:
        keys = [k for k, h in self._holders.items() if h == holder_id]
        for key in keys:
            async with self._get_lock(key):
                await self._disconnect_key(key)

    async def get_client(
        self,
        phone: str,
        api_id: int | str,
        api_hash: str,
        *,
        holder_id: str = "default",
        force_new: bool = False,
    ) -> TelegramClient:
        ensure_sessions_dir()
        path = session_file_path(phone)
        key = _lock_key(path)
        lock = self._get_lock(key)

        async with lock:
            existing = self._clients.get(key)
            if existing is not None and not force_new:
                running = asyncio.get_running_loop()
                client_loop = getattr(existing, "_loop", None)
                if client_loop is not None and client_loop is not running:
                    await self._disconnect_key(key)
                    existing = None
            if existing is not None and not force_new:
                current_holder = self._holders.get(key)
                if current_holder and current_holder != holder_id:
                    raise SessionInUseError(
                        f"Phone {phone!r} is already connected in this Groupint instance "
                        f"(holder {current_holder!r}). Disconnect the other session first."
                    )
                if not existing.is_connected():
                    await existing.connect()
                self._holders[key] = holder_id
                touch_session(phone)
                return existing

            await self._disconnect_key(key)

            session = load_string_session(phone) or StringSession()
            client = TelegramClient(session, int(api_id), api_hash)
            await client.connect()
            self._clients[key] = client
            self._holders[key] = holder_id
            touch_session(phone)
            return client


registry = ClientRegistry()


async def get_telegram_client(
    phone: str,
    api_id: int | str,
    api_hash: str,
    *,
    holder_id: str = "default",
    force_new: bool = False,
) -> TelegramClient:
    return await registry.get_client(
        phone, api_id, api_hash, holder_id=holder_id, force_new=force_new
    )


async def disconnect_telegram_client(phone: str) -> None:
    await registry.disconnect_phone(phone)


async def ensure_client_on_loop(
    client: TelegramClient,
    phone: str,
    api_id: int | str,
    api_hash: str,
    *,
    holder_id: str = "default",
) -> TelegramClient:
    """Reconnect if Telethon was bound to a different event loop."""
    running = asyncio.get_running_loop()
    client_loop = getattr(client, "_loop", None)
    if client_loop is not None and client_loop is not running:
        await registry.disconnect_phone(phone)
        return await registry.get_client(
            phone, api_id, api_hash, holder_id=holder_id, force_new=True
        )
    if not client.is_connected():
        await client.connect()
    return client


def persist_telegram_session(phone: str, client: TelegramClient) -> None:
    """Write StringSession to disk (sync — must run inside verify_otp, not as unawaited coroutine)."""
    save_string_session(phone, client)
