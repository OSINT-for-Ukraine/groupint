"""Individual incident pipeline stages."""

from __future__ import annotations

import logging
import uuid

from db.dal import GraphManager

from core.incidents.categories import normalize_category
from core.incidents.config import batch_size, llm_is_configured
from core.incidents.dedupe import run_dedupe_batch
from core.incidents.keyword_prefilter import (
    run_keyword_prefilter_batch as _run_keyword_prefilter_batch,
)
from core.incidents.geocode import geocode
from core.incidents.llm_client import complete_json, complete_text
from core.incidents.prompts import (
    CLEANER_SYSTEM,
    EXTRACT_SYSTEM,
    FILTER_SYSTEM,
)

logger = logging.getLogger(__name__)


def run_keyword_prefilter_batch(limit: int | None = None) -> int:
    return _run_keyword_prefilter_batch(limit=limit)


def run_clean_batch(limit: int | None = None) -> int:
    limit = limit or batch_size("clean")
    rows = GraphManager.messages_pending_clean(limit=limit)
    count = 0
    use_llm = llm_is_configured()
    for row in rows:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        if not use_llm:
            cleaned = text
        else:
            try:
                cleaned = complete_text(CLEANER_SYSTEM, text, max_tokens=1024)
            except Exception as exc:
                logger.warning("Clean failed msg %s: %s", row.get("message_id"), exc)
                cleaned = text
        if not cleaned.strip():
            cleaned = text
        GraphManager.update_message_incident_fields(
            row["group_id"],
            int(row["message_id"]),
            text_clean=cleaned.strip(),
            pipeline_stage="cleaned",
        )
        count += 1
    return count


def run_filter_batch(limit: int | None = None) -> int:
    limit = limit or batch_size("filter")
    rows = GraphManager.messages_pending_filter(limit=limit)
    count = 0
    for row in rows:
        text = (row.get("text_clean") or "").strip()
        if not text:
            GraphManager.update_message_incident_fields(
                row["group_id"],
                int(row["message_id"]),
                incident_checked=-1,
                pipeline_stage="filtered_skip",
            )
            count += 1
            continue
        try:
            data = complete_json(FILTER_SYSTEM, text, max_tokens=256)
            mappable = bool(data.get("mappable"))
        except Exception as exc:
            logger.warning("Filter failed: %s", exc)
            mappable = False
        GraphManager.update_message_incident_fields(
            row["group_id"],
            int(row["message_id"]),
            incident_checked=1 if mappable else -1,
            pipeline_stage="filtered",
        )
        count += 1
    return count


def run_extract_batch(limit: int | None = None) -> int:
    limit = limit or batch_size("extract")
    rows = GraphManager.messages_pending_extract(limit=limit)
    count = 0
    for row in rows:
        text = (row.get("text_clean") or "").strip()
        if not text:
            continue
        try:
            data = complete_json(EXTRACT_SYSTEM, text, max_tokens=512)
            category = normalize_category(data.get("category"))
            location = (data.get("location_text") or "").strip()
        except Exception as exc:
            logger.warning("Extract failed: %s", exc)
            category = "other"
            location = ""
        GraphManager.update_message_incident_fields(
            row["group_id"],
            int(row["message_id"]),
            category=category,
            location_text=location or None,
            pipeline_stage="extracted",
        )
        count += 1
    return count


def run_geocode_batch(limit: int | None = None) -> int:
    limit = limit or batch_size("geocode")
    rows = GraphManager.messages_pending_geocode(limit=limit)
    count = 0
    for row in rows:
        location = (row.get("location_text") or "").strip()
        context = row.get("text_clean") or ""
        if not location:
            GraphManager.update_message_incident_fields(
                row["group_id"],
                int(row["message_id"]),
                incident_processed=-2,
                pipeline_stage="geocode_failed",
            )
            count += 1
            continue
        coords = geocode(location, context=context)
        if coords is None:
            GraphManager.update_message_incident_fields(
                row["group_id"],
                int(row["message_id"]),
                incident_processed=-2,
                pipeline_stage="geocode_failed",
            )
        else:
            lat, lon = coords
            GraphManager.update_message_incident_fields(
                row["group_id"],
                int(row["message_id"]),
                lat=lat,
                lon=lon,
                pipeline_stage="geocoded",
            )
        count += 1
    return count


def run_link_incidents_batch(limit: int | None = None) -> int:
    limit = limit or batch_size("link")
    rows = GraphManager.messages_pending_incident_link(limit=limit)
    count = 0
    for row in rows:
        incident_id = str(uuid.uuid4())
        GraphManager.merge_incident_from_message(
            row["group_id"],
            int(row["message_id"]),
            incident_id,
            category=row.get("category") or "other",
            location_text=row.get("location_text") or "",
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            occurred_at=row.get("date"),
            summary=row.get("text_clean"),
            dedupe_cluster_id=incident_id,
        )
        count += 1
    return count


def run_dedupe(limit: int | None = None) -> int:
    return run_dedupe_batch(limit=limit or batch_size("dedupe"))
