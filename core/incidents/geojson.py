"""Build GeoJSON FeatureCollection from incident rows."""

from __future__ import annotations

import json
from typing import Any


def incidents_to_geojson(incidents: list[dict]) -> dict[str, Any]:
    features = []
    for inc in incidents:
        lat = inc.get("lat")
        lon = inc.get("lon")
        if lat is None or lon is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)],
                },
                "properties": {
                    "id": inc.get("id"),
                    "category": inc.get("category"),
                    "location_text": inc.get("location_text"),
                    "occurred_at": inc.get("occurred_at"),
                    "summary": inc.get("summary"),
                    "source_group_id": inc.get("source_group_id"),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def incidents_to_geojson_str(incidents: list[dict]) -> str:
    return json.dumps(incidents_to_geojson(incidents), ensure_ascii=False, indent=2)


def incidents_to_json_str(incidents: list[dict]) -> str:
    return json.dumps(incidents, ensure_ascii=False, indent=2)
