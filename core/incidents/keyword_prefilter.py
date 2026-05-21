"""Run keyword prefilter stage using monitor config and watchlist."""

from __future__ import annotations

import logging

from core.incidents.keywords import build_effective_keywords, message_matches_keywords
from core.tg_api_connector import normalize_telegram_group_ref
from db.dal import GraphManager

logger = logging.getLogger(__name__)


def _channel_for_group(group_id: str) -> dict | None:
    ref = normalize_telegram_group_ref(group_id)
    ch = GraphManager.get_watchlist_channel(ref)
    if ch:
        return ch
    for row in GraphManager.list_watchlist_channels():
        if normalize_telegram_group_ref(row.get("channel_ref", "")) == ref:
            return row
    return None


def run_keyword_prefilter_batch(limit: int | None = None) -> int:
    from core.incidents.config import batch_size

    limit = limit or batch_size("keyword")
    config = GraphManager.get_incident_monitor_config()
    global_kw = list(config.get("global_keywords") or [])
    global_on = bool(config.get("global_keywords_enabled"))

    rows = GraphManager.messages_pending_keyword_prefilter(limit=limit)
    count = 0
    for row in rows:
        text = (row.get("text") or "").strip()
        group_id = row.get("group_id") or ""
        ch = _channel_for_group(group_id) or {}
        effective = build_effective_keywords(
            global_keywords=global_kw,
            global_keywords_enabled=global_on,
            channel_keywords=list(ch.get("keywords") or []),
            channel_keywords_enabled=bool(ch.get("keywords_enabled")),
            use_global_keywords=bool(ch.get("use_global_keywords", True)),
        )
        if message_matches_keywords(text, effective):
            GraphManager.update_message_incident_fields(
                group_id,
                int(row["message_id"]),
                pipeline_stage="keyword_passed",
            )
        else:
            GraphManager.update_message_incident_fields(
                group_id,
                int(row["message_id"]),
                incident_checked=-1,
                pipeline_stage="keyword_rejected",
            )
        count += 1
    return count
