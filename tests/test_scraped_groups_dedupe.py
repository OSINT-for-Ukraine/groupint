import unittest

from db.dal import dedupe_scraped_groups


class TestDedupeScrapedGroups(unittest.TestCase):
    def test_duplicate_ids_keeps_newer_scraped_at(self) -> None:
        rows = [
            {
                "id": "Republic_of_Gagazia_Chat",
                "scraped_at": "2026-01-01T00:00:00+00:00",
                "title": "Old",
            },
            {
                "id": "Republic_of_Gagazia_Chat",
                "scraped_at": "2026-05-19T12:00:00+00:00",
                "title": "New",
            },
        ]
        result = dedupe_scraped_groups(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "New")

    def test_unique_ids_preserved(self) -> None:
        rows = [
            {"id": "group_a", "scraped_at": "2026-05-01"},
            {"id": "group_b", "scraped_at": "2026-05-02"},
        ]
        result = dedupe_scraped_groups(rows)
        self.assertEqual(len(result), 2)
        ids = {row["id"] for row in result}
        self.assertEqual(ids, {"group_a", "group_b"})

    def test_widget_keys_unique_after_dedupe(self) -> None:
        rows = [
            {"id": "Republic_of_Gagazia_Chat", "scraped_at": "2026-01-01"},
            {"id": "Republic_of_Gagazia_Chat", "scraped_at": "2026-05-19"},
            {"id": "other_group", "scraped_at": "2026-05-18"},
        ]
        deduped = dedupe_scraped_groups(rows)
        keys = [f"neo4j_del_confirm_{idx}" for idx, _ in enumerate(deduped)]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(deduped), 2)

    def test_skips_empty_id(self) -> None:
        rows = [{"id": "", "scraped_at": "2026-05-01"}, {"id": "valid", "scraped_at": "2026-05-02"}]
        result = dedupe_scraped_groups(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "valid")

    def test_clusters_by_telegram_peer_id(self) -> None:
        rows = [
            {
                "id": "Чат_ Гагаузской",
                "telegram_peer_id": 111,
                "scraped_at": "2026-01-01",
                "members": 100,
            },
            {
                "id": "Republic_of_Gagazia_Chat",
                "telegram_peer_id": 111,
                "scraped_at": "2026-05-19",
                "members": 50,
            },
        ]
        result = dedupe_scraped_groups(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "Republic_of_Gagazia_Chat")
        self.assertEqual(result[0]["members"], 100)

    def test_clusters_by_telegram_url(self) -> None:
        rows = [
            {
                "id": "alias_a",
                "telegram_url": "https://t.me/MyGroup",
                "scraped_at": "2026-01-01",
            },
            {
                "id": "MyGroup",
                "telegram_url": "https://t.me/MyGroup",
                "scraped_at": "2026-05-01",
            },
        ]
        result = dedupe_scraped_groups(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "MyGroup")


if __name__ == "__main__":
    unittest.main()
