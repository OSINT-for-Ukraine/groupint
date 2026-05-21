"""Tests for Atlos export helpers."""

import sys
from unittest.mock import MagicMock, patch

from core.incidents.atlos_export import (
    incident_to_atlos_payload,
    normalize_base_url,
    _extract_slug,
    export_incidents_batch,
)


def test_normalize_base_url():
    assert normalize_base_url("http://atlos:4000/") == "http://atlos:4000"


def test_incident_to_atlos_payload_min_description():
    p = incident_to_atlos_payload(
        {
            "category": "attack",
            "location_text": "Kyiv",
            "summary": "Short",
            "lat": 50.45,
            "lon": 30.52,
            "source_urls": ["https://t.me/c/1/2"],
        }
    )
    assert len(p["description"]) >= 8
    assert p["geolocation"] == "50.45,30.52"
    assert p["tags"] == ["attack"]
    assert "https://t.me/c/1/2" in p["urls"]


def test_extract_slug():
    assert _extract_slug({"slug": "ABC123"}) == "ABC123"
    assert _extract_slug({"incident": {"slug": "XYZ"}}) == "XYZ"


def test_export_skips_without_token():
    r = export_incidents_batch([{"id": "1", "category": "other"}], base_url="http://x", api_token="")
    assert r["created"] == 0
    assert "token" in r["errors"][0].lower()


def test_export_creates_and_records_slug():
    inc = {
        "id": "uuid-1",
        "category": "shelling",
        "location_text": "Donetsk",
        "summary": "Report text here",
        "lat": 48.0,
        "lon": 37.8,
        "source_urls": [],
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"slug": "AB12CD"}

    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    mock_gm = MagicMock()
    fake_dal = MagicMock(GraphManager=mock_gm)

    with patch("core.incidents.atlos_export.httpx.Client", return_value=mock_client):
        with patch.dict(sys.modules, {"db.dal": fake_dal}):
            r = export_incidents_batch(
                [inc],
                base_url="http://atlos:4000",
                api_token="test-token",
                delay_sec=0,
            )
    assert r["created"] == 1
    mock_gm.set_incident_atlos_export.assert_called_once_with("uuid-1", "AB12CD")
