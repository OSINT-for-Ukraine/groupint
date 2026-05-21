"""Background watchlist polling and ingest for incident pipeline."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from core.incidents.config import poll_interval_sec, poll_message_limit
from core.incidents.pipeline import run_pending_pipeline
from core.tg_api_connector import (
    create_client,
    ensure_telegram_client,
    fetch_group_messages,
    normalize_telegram_group_ref,
)
from core.telegram_session import list_sessions, session_file_exists
from db.dal import GraphManager

logger = logging.getLogger(__name__)


async def poll_watchlist_channel(
    client,
    channel_ref: str,
    *,
    limit: int | None = None,
) -> tuple[int, int]:
    """Fetch new messages for one watchlist entry. Returns (inserted, skipped)."""
    limit = limit or poll_message_limit()
    inserted, skipped, _title, _resolved = await fetch_group_messages(
        client, channel_ref, limit=limit, on_progress=None
    )
    GraphManager.upsert_watchlist_channel(
        normalize_telegram_group_ref(channel_ref),
        last_polled_at=datetime.now(timezone.utc).isoformat(),
    )
    return inserted, skipped


async def poll_all_watchlist(client) -> dict[str, int]:
    """Poll every enabled watchlist channel."""
    channels = GraphManager.list_watchlist_channels()
    stats = {"channels": 0, "inserted": 0, "skipped": 0, "errors": 0}
    await ensure_telegram_client(client)
    for ch in channels:
        if not ch.get("enabled", True):
            continue
        ref = (ch.get("channel_ref") or "").strip()
        if not ref:
            continue
        stats["channels"] += 1
        try:
            ins, sk = await poll_watchlist_channel(client, ref)
            stats["inserted"] += ins
            stats["skipped"] += sk
        except Exception as exc:
            logger.exception("Poll failed for %s: %s", ref, exc)
            stats["errors"] += 1
    return stats


def _monitor_config() -> dict:
    """Neo4j scheduler settings with env fallback for interval."""
    cfg = GraphManager.get_incident_monitor_config()
    interval = int(cfg.get("fetch_interval_sec") or 0)
    if interval <= 0:
        interval = poll_interval_sec()
    cfg["fetch_interval_sec"] = interval
    return cfg


def record_fetch_completed() -> None:
    GraphManager.upsert_incident_monitor_config(
        last_fetch_at=datetime.now(timezone.utc).isoformat()
    )


async def monitor_cycle(
    client,
    *,
    run_pipeline: bool = True,
) -> dict:
    """One ingest + optional pipeline pass."""
    ingest = await poll_all_watchlist(client)
    record_fetch_completed()
    result = {"ingest": ingest}
    if run_pipeline:
        try:
            result["pipeline"] = run_pending_pipeline(max_rounds_per_stage=3)
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            result["pipeline_error"] = str(exc)
    return result


async def fetch_watchlist_now(client, *, run_pipeline: bool = False) -> dict:
    """Manual fetch from UI; optionally run pipeline after."""
    return await monitor_cycle(client, run_pipeline=run_pipeline)


def _resolve_worker_phone_api() -> tuple[str, str, str]:
    from core.incidents.config import telegram_creds_from_env

    creds = telegram_creds_from_env()
    if creds:
        return creds
    sessions = list_sessions()
    if not sessions:
        raise RuntimeError(
            "No Telegram session. Set TELEGRAM_PHONE/API_ID/API_HASH or save a session in Groupint UI."
        )
    phone = sessions[0].get("phone") or sessions[0]["phone_key"]
    raise RuntimeError(
        f"Set TELEGRAM_PHONE, TELEGRAM_API_ID, TELEGRAM_API_HASH for worker (session: {phone})"
    )


async def run_monitor_loop(
    *,
    interval_sec: int | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run poll + pipeline until stop_event is set; reads scheduler from Neo4j each cycle."""
    phone, api_id, api_hash = _resolve_worker_phone_api()
    if not session_file_exists(phone):
        raise RuntimeError(f"No saved session file for {phone}")

    client = await create_client(
        phone, api_id, api_hash, holder_id="incident-worker", force_new=False
    )
    stop = stop_event or asyncio.Event()
    fallback_interval = interval_sec or poll_interval_sec()
    logger.info("Incident monitor started (fallback_interval=%ss)", fallback_interval)
    while not stop.is_set():
        cfg = _monitor_config()
        interval = int(cfg.get("fetch_interval_sec") or fallback_interval)
        scheduler_enabled = bool(cfg.get("scheduler_enabled"))
        run_pipeline = bool(cfg.get("run_pipeline_after_fetch", True))

        if scheduler_enabled:
            last_fetch = cfg.get("last_fetch_at")
            should_fetch = True
            if last_fetch:
                try:
                    last_dt = datetime.fromisoformat(
                        str(last_fetch).replace("Z", "+00:00")
                    )
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    next_due = last_dt + timedelta(seconds=interval)
                    should_fetch = datetime.now(timezone.utc) >= next_due
                except ValueError:
                    should_fetch = True
            if should_fetch:
                try:
                    summary = await monitor_cycle(client, run_pipeline=run_pipeline)
                    logger.info("Monitor cycle: %s", summary)
                except Exception as exc:
                    logger.exception("Monitor cycle error: %s", exc)
            else:
                logger.debug("Scheduler: next fetch not due yet")
        else:
            logger.debug("Scheduler disabled in Neo4j config")

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
    await client.disconnect()
