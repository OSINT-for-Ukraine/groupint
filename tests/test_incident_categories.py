import unittest

from core.incidents.categories import normalize_category


class TestNormalizeCategory(unittest.TestCase):
    def test_known(self) -> None:
        self.assertEqual(normalize_category("drone_strike"), "drone_strike")

    def test_alias(self) -> None:
        self.assertEqual(normalize_category("IED"), "explosion")

    def test_unknown(self) -> None:
        self.assertEqual(normalize_category("random_news"), "other")

    def test_empty(self) -> None:
        self.assertEqual(normalize_category(None), "other")


if __name__ == "__main__":
    unittest.main()
