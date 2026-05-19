import unittest
from unittest.mock import MagicMock

from core.group_identity import ResolvedGroup
from interface import _unpack_participants_fetch


class TestUnpackParticipantsFetch(unittest.TestCase):
    def test_three_tuple(self) -> None:
        resolved = ResolvedGroup(canonical_id="my_group")
        users, title, out = _unpack_participants_fetch(
            ([(1, "u", "A")], "Title", resolved), "my_group"
        )
        self.assertEqual(len(users), 1)
        self.assertEqual(title, "Title")
        self.assertIs(out, resolved)

    def test_legacy_two_tuple(self) -> None:
        users, title, resolved = _unpack_participants_fetch(
            ([(2, None, "")], "Chat"), "Republic_of_Gagazia_Chat"
        )
        self.assertEqual(users[0][0], 2)
        self.assertEqual(resolved.canonical_id, "Republic_of_Gagazia_Chat")


class TestParticipantsFetchResult(unittest.TestCase):
    def test_normalizes_rows(self) -> None:
        from core.tg_api_connector import _participants_fetch_result

        resolved = ResolvedGroup(canonical_id="g")
        users, title, out = _participants_fetch_result(
            [(1, "a"), (1, "b", "alias")],
            "T",
            resolved,
        )
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0], (1, "b", "alias"))
        self.assertIs(out, resolved)


if __name__ == "__main__":
    unittest.main()
