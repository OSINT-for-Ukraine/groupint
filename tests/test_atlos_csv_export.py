"""Tests for Atlos bulk-import CSV export."""

import csv
import io

from core.incidents.atlos_csv_export import (
    ATLOS_CSV_FIELDS,
    build_incident_description,
    incident_to_atlos_csv_row,
    incidents_to_atlos_csv_str,
)


def _parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_csv_header_lowercase():
    text = incidents_to_atlos_csv_str(
        [
            {
                "category": "shelling",
                "location_text": "Kharkiv",
                "summary": "Long enough summary text",
                "lat": 49.99,
                "lon": 36.23,
            }
        ]
    )
    rows = _parse_csv(text)
    assert list(rows[0].keys()) == list(ATLOS_CSV_FIELDS)
    assert "status" in rows[0]
    assert "description" in rows[0]
    assert "sensitive" in rows[0]


def test_description_min_length():
    row = incident_to_atlos_csv_row({"category": "x", "summary": ""})
    assert len(row["description"]) >= 8


def test_geolocation_format():
    row = incident_to_atlos_csv_row(
        {"category": "other", "lat": 50.45, "lon": 30.52}
    )
    assert row["geolocation"] == "50.45,30.52"


def test_skips_without_coordinates_when_required():
    text = incidents_to_atlos_csv_str(
        [{"category": "other", "summary": "no coords here ok"}],
        require_coordinates=True,
    )
    assert _parse_csv(text) == []


def test_sensitive_quoting_with_comma():
    text = incidents_to_atlos_csv_str(
        [
            {
                "category": "other",
                "summary": "Enough text for description field",
                "lat": 1.0,
                "lon": 2.0,
            }
        ],
        sensitive="Deleted by Source,Deceptive or Misleading",
    )
    rows = _parse_csv(text)
    assert rows[0]["sensitive"] == "Deleted by Source,Deceptive or Misleading"


def test_build_incident_description_includes_category():
    desc = build_incident_description(
        {
            "category": "drone_strike",
            "location_text": "Odesa",
            "summary": "Drone reported",
            "occurred_at": "2024-01-01",
        }
    )
    assert "[drone_strike]" in desc
    assert "Odesa" in desc
