"""Geocode location strings via Google Maps API or Nominatim fallback."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.incidents.config import google_maps_api_key
from core.incidents.llm_client import complete_json
from core.incidents.prompts import GEOCODE_REFINE_SYSTEM

logger = logging.getLogger(__name__)


def refine_location_query(location_text: str, context: str = "") -> str:
    if not location_text or not location_text.strip():
        return ""
    try:
        data = complete_json(
            GEOCODE_REFINE_SYSTEM,
            f"Location mention: {location_text}\nContext: {context[:500]}",
            max_tokens=256,
        )
        query = (data.get("query") or "").strip()
        return query or location_text.strip()
    except Exception as exc:
        logger.warning("Location refine failed: %s", exc)
        return location_text.strip()


def geocode(location_text: str, *, context: str = "") -> tuple[float, float] | None:
    query = refine_location_query(location_text, context=context)
    if not query:
        return None
    coords = _geocode_google(query)
    if coords is None:
        coords = _geocode_nominatim(query)
    return coords


def _geocode_google(query: str) -> tuple[float, float] | None:
    key = google_maps_api_key()
    if not key:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": query, "key": key},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        loc = data["results"][0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])
    except Exception as exc:
        logger.warning("Google geocode failed for %r: %s", query, exc)
        return None


def _geocode_nominatim(query: str) -> tuple[float, float] | None:
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": "groupint-osint-incidents/1.0"},
            )
            resp.raise_for_status()
            rows: list[dict[str, Any]] = resp.json()
        if not rows:
            return None
        return float(rows[0]["lat"]), float(rows[0]["lon"])
    except Exception as exc:
        logger.warning("Nominatim geocode failed for %r: %s", query, exc)
        return None
