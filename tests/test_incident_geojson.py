import json
import unittest

from core.incidents.geojson import incidents_to_geojson


class TestIncidentGeojson(unittest.TestCase):
    def test_feature_collection(self) -> None:
        data = incidents_to_geojson(
            [
                {
                    "id": "a1",
                    "lat": 50.45,
                    "lon": 30.52,
                    "category": "attack",
                    "location_text": "Kyiv",
                    "occurred_at": "2026-01-01T12:00:00",
                    "summary": "Test",
                }
            ]
        )
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 1)
        feat = data["features"][0]
        self.assertEqual(feat["geometry"]["coordinates"], [30.52, 50.45])
        self.assertEqual(feat["properties"]["category"], "attack")

    def test_skips_missing_coords(self) -> None:
        data = incidents_to_geojson([{"id": "x", "category": "other"}])
        self.assertEqual(data["features"], [])

    def test_valid_json_roundtrip(self) -> None:
        raw = json.dumps(
            incidents_to_geojson(
                [{"id": "1", "lat": 1.0, "lon": 2.0, "category": "other"}]
            )
        )
        parsed = json.loads(raw)
        self.assertIn("features", parsed)


if __name__ == "__main__":
    unittest.main()
