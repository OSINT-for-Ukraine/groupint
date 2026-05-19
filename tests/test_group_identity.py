import unittest
from unittest.mock import MagicMock

from core.group_identity import (
    canonical_group_id_from_entity,
    dedupe_member_tuples,
    group_identity_from_entity,
    pick_winner_group_id,
    validate_member_count_for_persist,
)


class TestCanonicalGroupId(unittest.TestCase):
    def test_public_username(self) -> None:
        entity = MagicMock()
        entity.username = "Republic_of_Gagazia_Chat"
        entity.id = 123456
        entity.title = "Gagauzia Chat"
        self.assertEqual(
            canonical_group_id_from_entity(entity),
            "Republic_of_Gagazia_Chat",
        )

    def test_private_peer_id(self) -> None:
        entity = MagicMock()
        entity.username = None
        entity.id = 987654321
        entity.title = "Private Group"
        self.assertEqual(canonical_group_id_from_entity(entity), "peer:987654321")

    def test_aliases_from_raw_input(self) -> None:
        entity = MagicMock()
        entity.username = "my_group"
        entity.id = 1
        entity.title = "My Group"
        resolved = group_identity_from_entity(entity, "https://t.me/my_group")
        self.assertEqual(resolved.canonical_id, "my_group")
        self.assertTrue(resolved.aliases)


class TestPickWinner(unittest.TestCase):
    def test_prefers_username_over_peer(self) -> None:
        ids = ["peer:123", "Republic_of_Gagazia_Chat", "Чат_ Гагаузской"]
        self.assertEqual(pick_winner_group_id(ids), "Republic_of_Gagazia_Chat")

    def test_prefers_peer_over_title(self) -> None:
        ids = ["Чат Title", "peer:999"]
        self.assertEqual(pick_winner_group_id(ids), "peer:999")


class TestMemberDedupe(unittest.TestCase):
    def test_dedupe_by_user_id(self) -> None:
        rows = [(1, None, "a"), (1, "user1", ""), (2, None, "b")]
        out = dedupe_member_tuples(rows)
        self.assertEqual(len(out), 2)
        by_id = {r[0]: r for r in out}
        self.assertEqual(by_id[1][1], "user1")


class TestMemberSanity(unittest.TestCase):
    def test_rejects_huge_count(self) -> None:
        with self.assertRaises(ValueError):
            validate_member_count_for_persist(600_000)

    def test_rejects_double_participants(self) -> None:
        with self.assertRaises(ValueError):
            validate_member_count_for_persist(1000, participants_count=100)


if __name__ == "__main__":
    unittest.main()
