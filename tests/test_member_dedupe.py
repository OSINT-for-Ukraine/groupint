import unittest

from core.group_identity import dedupe_member_tuples


class TestIterParticipantsDedupe(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(dedupe_member_tuples([]), [])

    def test_preserves_order(self) -> None:
        rows = [(3, "c", ""), (1, "a", ""), (2, "b", "")]
        out = dedupe_member_tuples(rows)
        self.assertEqual([r[0] for r in out], [3, 1, 2])


if __name__ == "__main__":
    unittest.main()
