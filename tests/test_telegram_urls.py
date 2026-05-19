import unittest

from core.telegram_urls import group_url, message_url, user_url


class TestTelegramUrls(unittest.TestCase):
    def test_group_url(self) -> None:
        self.assertEqual(
            group_url("https://t.me/Republic_of_Gagazia_Chat"),
            "https://t.me/Republic_of_Gagazia_Chat",
        )

    def test_user_url_with_username(self) -> None:
        self.assertEqual(user_url(123, "@alice"), "https://t.me/alice")

    def test_user_url_without_username(self) -> None:
        self.assertEqual(user_url(385768518, None), "tg://user?id=385768518")

    def test_message_url_public(self) -> None:
        self.assertEqual(
            message_url("mygroup", 42, username="mygroup"),
            "https://t.me/mygroup/42",
        )

    def test_message_url_private_channel(self) -> None:
        self.assertEqual(
            message_url("x", 99, channel_id=-1001234567890),
            "https://t.me/c/1234567890/99",
        )

    def test_message_url_fallback_group_ref(self) -> None:
        self.assertEqual(
            message_url("Republic_of_Gagazia_Chat", 7),
            "https://t.me/Republic_of_Gagazia_Chat/7",
        )


if __name__ == "__main__":
    unittest.main()
