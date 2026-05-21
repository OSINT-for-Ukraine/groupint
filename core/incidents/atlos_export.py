"""Export Groupint incidents to Atlos API v2."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from core.incidents.config import (
    apply_atlos_secrets,
    default_atlos_api_token,
    default_atlos_base_url,
)

logger = logging.getLogger(__name__)

DEFAULT_SENSITIVE = ["Not Sensitive"]
DEFAULT_STATUS = "To Do"
REQUEST_TIMEOUT = 60.0


def normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def atlos_config() -> dict[str, str]:
    """Neo4j saved settings override env defaults (local Docker by default)."""
    from db.dal import GraphManager

    apply_atlos_secrets()
    row = GraphManager.get_incident_monitor_config()
    base = normalize_base_url(row.get("atlos_base_url") or "") or default_atlos_base_url()
    token = (row.get("atlos_api_token") or "").strip() or default_atlos_api_token()
    return {"base_url": base, "api_token": token}


def incident_to_atlos_payload(
    inc: dict,
    *,
    sensitive: list[str] | None = None,
    status: str = DEFAULT_STATUS,
) -> dict[str, Any]:
    category = (inc.get("category") or "other").strip()
    location = (inc.get("location_text") or "").strip()
    summary = (inc.get("summary") or "").strip()
    occurred = inc.get("occurred_at") or ""
    parts = [f"[{category}]"]
    if location:
        parts.append(location)
    if summary:
        parts.append(summary)
    if occurred:
        parts.append(f"Occurred: {occurred}")
    description = "\n\n".join(parts).strip()
    if len(description) < 8:
        description = (description + " — Groupint OSINT incident export").strip()
        if len(description) < 8:
            description = "Groupint OSINT incident export."

    payload: dict[str, Any] = {
        "description": description,
        "sensitive": sensitive or DEFAULT_SENSITIVE,
        "status": status,
        "tags": [category],
    }
    lat, lon = inc.get("lat"), inc.get("lon")
    if lat is not None and lon is not None:
        payload["geolocation"] = f"{float(lat)},{float(lon)}"
    urls = []
    for u in inc.get("source_urls") or []:
        s = str(u).strip()
        if s.startswith("http://") or s.startswith("https://"):
            urls.append(s)
    if urls:
        payload["urls"] = urls
    return payload


def _extract_slug(data: dict | list | None) -> str | None:
    if not data:
        return None
    if isinstance(data, dict):
        for key in ("slug", "incident_slug"):
            if data.get(key):
                return str(data[key])
        for nested in ("incident", "data", "result"):
            inner = data.get(nested)
            if isinstance(inner, dict):
                found = _extract_slug(inner)
                if found:
                    return found
    return None


def create_atlos_incident(
    client: httpx.Client,
    base_url: str,
    token: str,
    payload: dict[str, Any],
) -> str:
    url = urljoin(base_url + "/", "api/v2/incidents/new")
    resp = client.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    try:
        body = resp.json()
    except Exception:
        body = {}
    slug = _extract_slug(body if isinstance(body, dict) else {})
    if slug:
        return slug
    raise ValueError(f"Atlos response missing slug: {body!r}")


def test_atlos_connection(base_url: str, token: str) -> tuple[bool, str]:
    if not token:
        return False, "API token is empty."
    base_url = normalize_base_url(base_url)
    url = urljoin(base_url + "/", "api/v2/incidents")
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 1},
            )
        if resp.status_code in (200, 401, 403):
            if resp.status_code == 200:
                return True, "Connected to Atlos API."
            return False, f"Atlos returned HTTP {resp.status_code}: check API token."
        return False, f"Unexpected HTTP {resp.status_code}: {resp.text[:200]}"
    except httpx.RequestError as exc:
        return False, f"Could not reach Atlos: {exc}"


def export_incidents_batch(
    incidents: list[dict],
    *,
    base_url: str,
    api_token: str,
    sensitive: list[str] | None = None,
    skip_exported: bool = True,
    delay_sec: float = 0.3,
) -> dict[str, Any]:
    base_url = normalize_base_url(base_url)
    if not api_token:
        return {
            "created": 0,
            "skipped": len(incidents),
            "failed": 0,
            "errors": ["ATLOS_API_TOKEN is not set."],
        }
    from db.dal import GraphManager

    created = 0
    skipped = 0
    failed = 0
    errors: list[str] = []
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for inc in incidents:
            if skip_exported and inc.get("atlos_slug"):
                skipped += 1
                continue
            try:
                payload = incident_to_atlos_payload(inc, sensitive=sensitive)
                slug = create_atlos_incident(client, base_url, api_token, payload)
                GraphManager.set_incident_atlos_export(str(inc["id"]), slug)
                created += 1
                if delay_sec > 0:
                    time.sleep(delay_sec)
            except Exception as exc:
                failed += 1
                msg = f"{inc.get('id')}: {exc}"
                errors.append(msg)
                logger.warning("Atlos export failed: %s", msg)
    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }
