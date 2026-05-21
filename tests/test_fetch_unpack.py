import inspect
import unittest

from core.group_identity import ResolvedGroup
from core.tg_api_connector import extract_endorsements_from_stored_messages, normalize_telegram_group_ref


def _unpack_messages_fetch_impl(
    result: object,
    raw_group: str,
) -> tuple[int, int, str | None, ResolvedGroup]:
    if not isinstance(result, tuple):
        raise TypeError(f"expected tuple, got {type(result).__name__}")
    if len(result) == 4:
        inserted, skipped, group_title, resolved = result
        if not isinstance(resolved, ResolvedGroup):
            resolved = ResolvedGroup(
                canonical_id=normalize_telegram_group_ref(raw_group),
                title=group_title,
            )
        return int(inserted), int(skipped), group_title, resolved
    if len(result) == 3:
        inserted, skipped, group_title = result
        return (
            int(inserted),
            int(skipped),
            group_title,
            ResolvedGroup(
                canonical_id=normalize_telegram_group_ref(raw_group),
                title=group_title,
            ),
        )
    raise ValueError(f"unexpected length {len(result)}")


def _unpack_endorsements_fetch_impl(
    result: object,
    raw_group: str,
) -> tuple[int, int, ResolvedGroup]:
    if not isinstance(result, tuple):
        raise TypeError(f"expected tuple, got {type(result).__name__}")
    if len(result) == 3:
        inserted, total_links, resolved = result
        if not isinstance(resolved, ResolvedGroup):
            resolved = ResolvedGroup(canonical_id=normalize_telegram_group_ref(raw_group))
        return int(inserted), int(total_links), resolved
    if len(result) == 2:
        inserted, total_links = result
        return (
            int(inserted),
            int(total_links),
            ResolvedGroup(canonical_id=normalize_telegram_group_ref(raw_group)),
        )
    raise ValueError(f"unexpected length {len(result)}")


class TestUnpackMessagesFetch(unittest.TestCase):
    def test_four_tuple(self) -> None:
        resolved = ResolvedGroup(canonical_id="my_group")
        inserted, skipped, title, out = _unpack_messages_fetch_impl(
            (5, 2, "Title", resolved), "my_group"
        )
        self.assertEqual(inserted, 5)
        self.assertEqual(skipped, 2)
        self.assertIs(out, resolved)

    def test_legacy_three_tuple(self) -> None:
        inserted, skipped, title, resolved = _unpack_messages_fetch_impl(
            (3, 1, "Chat"), "Republic_of_Gagazia_Chat"
        )
        self.assertEqual(resolved.canonical_id, "Republic_of_Gagazia_Chat")


class TestUnpackEndorsementsFetch(unittest.TestCase):
    def test_three_tuple(self) -> None:
        resolved = ResolvedGroup(canonical_id="g")
        inserted, total, out = _unpack_endorsements_fetch_impl((2, 10, resolved), "g")
        self.assertEqual(inserted, 2)
        self.assertEqual(total, 10)
        self.assertIs(out, resolved)

    def test_legacy_two_tuple(self) -> None:
        inserted, total, resolved = _unpack_endorsements_fetch_impl((1, 5), "g")
        self.assertEqual(inserted, 1)
        self.assertEqual(resolved.canonical_id, "g")


class TestCallExtractEndorsements(unittest.TestCase):
    def test_uses_client_signature_when_present(self) -> None:
        params = list(inspect.signature(extract_endorsements_from_stored_messages).parameters)
        self.assertEqual(params[0], "client")

    def test_legacy_signature_dispatch(self) -> None:
        async def legacy(group_ref: str, on_progress=None):
            return 1, 2

        progress = None

        async def run_legacy(client, group_ref, on_progress):
            sig = inspect.signature(legacy)
            first = next(iter(sig.parameters.keys()))
            if first == "client":
                return await legacy(client, group_ref, on_progress=on_progress)
            return await legacy(group_ref, on_progress=on_progress)

        import asyncio

        result = asyncio.run(run_legacy(object(), "ref", progress))
        self.assertEqual(result, (1, 2))


if __name__ == "__main__":
    unittest.main()
