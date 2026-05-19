import unittest

from core.tg_api_connector import _message_id_chunks


class TestMessageIdChunks(unittest.TestCase):
    def test_chunks_splits_correctly(self) -> None:
        ids = list(range(250))
        chunks = _message_id_chunks(ids, size=100)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 100)
        self.assertEqual(len(chunks[2]), 50)

    def test_empty(self) -> None:
        self.assertEqual(_message_id_chunks([]), [])


if __name__ == "__main__":
    unittest.main()
