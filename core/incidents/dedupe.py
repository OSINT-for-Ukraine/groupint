"""Contextual deduplication of incident messages by date."""

from __future__ import annotations

import logging
from collections import defaultdict

from db.dal import GraphManager

from core.incidents.llm_client import complete_json
from core.incidents.prompts import DEDUPE_SYSTEM

logger = logging.getLogger(__name__)


def _date_prefix(iso_date: str | None) -> str:
    if not iso_date:
        return ""
    return iso_date[:10] if len(iso_date) >= 10 else iso_date


def _is_duplicate(canonical_text: str, candidate_text: str) -> bool:
    try:
        data = complete_json(
            DEDUPE_SYSTEM,
            f"Canonical:\n{canonical_text}\n\nCandidate:\n{candidate_text}",
            max_tokens=256,
        )
        return bool(data.get("duplicate"))
    except Exception as exc:
        logger.warning("Dedupe LLM call failed: %s", exc)
        return False


def run_dedupe_batch(limit: int = 200) -> int:
    """Cluster pending messages by calendar day; mark canonical vs duplicate."""
    rows = GraphManager.messages_pending_dedupe(limit=limit)
    if not rows:
        return 0

    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_day[_date_prefix(row.get("date")) or "unknown"].append(row)

    processed = 0
    for _day, day_rows in by_day.items():
        if not day_rows:
            continue
        canonical = day_rows[0]
        gid = canonical["group_id"]
        mid = int(canonical["message_id"])
        GraphManager.update_message_incident_fields(
            gid,
            mid,
            incident_processed=1,
            pipeline_stage="dedupe_canonical",
        )
        processed += 1
        canon_text = canonical.get("text_clean") or ""

        for dup in day_rows[1:]:
            dup_gid = dup["group_id"]
            dup_mid = int(dup["message_id"])
            if _is_duplicate(canon_text, dup.get("text_clean") or ""):
                GraphManager.update_message_incident_fields(
                    dup_gid,
                    dup_mid,
                    incident_processed=-1,
                    pipeline_stage="dedupe_duplicate",
                )
            else:
                GraphManager.update_message_incident_fields(
                    dup_gid,
                    dup_mid,
                    incident_processed=1,
                    pipeline_stage="dedupe_canonical",
                )
                canonical = dup
                canon_text = dup.get("text_clean") or ""
            processed += 1

    return processed
