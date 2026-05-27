"""CSV export for Atlos bulk import (manual upload to cloud Atlos)."""

from __future__ import annotations

import csv
import io
from typing import Any

DEFAULT_STATUS = "To Do"
DEFAULT_SENSITIVE = "Not Sensitive"

# Atlos bulk import: required lowercase headers (see Atlos docs).
ATLOS_CSV_FIELDS = ("status", "description", "sensitive", "geolocation")


def build_incident_description(inc: dict) -> str:
    """Human-readable description shared with API export formatting."""
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
    return description


def format_geolocation(inc: dict) -> str:
    lat, lon = inc.get("lat"), inc.get("lon")
    if lat is None or lon is None:
        return ""
    return f"{float(lat)},{float(lon)}"


def incident_to_atlos_csv_row(
    inc: dict,
    *,
    status: str = DEFAULT_STATUS,
    sensitive: str = DEFAULT_SENSITIVE,
) -> dict[str, str]:
    row = {
        "status": status,
        "description": build_incident_description(inc),
        "sensitive": sensitive,
        "geolocation": format_geolocation(inc),
    }
    return row


def incidents_to_atlos_csv_str(
    incidents: list[dict],
    *,
    status: str = DEFAULT_STATUS,
    sensitive: str = DEFAULT_SENSITIVE,
    require_coordinates: bool = True,
) -> str:
    """Build CSV for Atlos Manage → Bulk import."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=list(ATLOS_CSV_FIELDS),
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for inc in incidents:
        if require_coordinates and (
            inc.get("lat") is None or inc.get("lon") is None
        ):
            continue
        writer.writerow(
            incident_to_atlos_csv_row(inc, status=status, sensitive=sensitive)
        )
    return buf.getvalue()
