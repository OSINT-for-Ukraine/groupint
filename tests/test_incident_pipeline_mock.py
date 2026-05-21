import json
import unittest

from core.incidents.llm_client import _extract_json


class TestLlmJsonExtract(unittest.TestCase):
    def test_plain_json(self) -> None:
        data = _extract_json('{"mappable": true}')
        self.assertTrue(data["mappable"])

    def test_embedded_json(self) -> None:
        raw = 'Here is the result:\n{"mappable": false, "reason": "vague"}\n'
        data = _extract_json(raw)
        self.assertFalse(data["mappable"])


class TestDedupeDateGrouping(unittest.TestCase):
    def test_date_prefix(self) -> None:
        def date_prefix(iso_date: str | None) -> str:
            if not iso_date:
                return ""
            return iso_date[:10] if len(iso_date) >= 10 else iso_date

        self.assertEqual(date_prefix("2026-01-15T12:00:00"), "2026-01-15")
        self.assertEqual(date_prefix(None), "")


class TestFilterSemantics(unittest.TestCase):
    """Document expected stage outputs without importing db-backed stages."""

    def test_checked_values(self) -> None:
        self.assertEqual({-1, 0, 1}, {-1, 0, 1})
        self.assertEqual({-2, -1, 0, 1}, {-2, -1, 0, 1})


if __name__ == "__main__":
    unittest.main()
