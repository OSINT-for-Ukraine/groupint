"""Tests for incident keyword prefilter."""

from core.incidents.keywords import (
    build_effective_keywords,
    message_matches_keywords,
    normalize_text,
    parse_keyword_lines,
)


def test_parse_keyword_lines():
    assert parse_keyword_lines("взрыв\nудар, ракета") == ["взрыв", "удар", "ракета"]
    assert parse_keyword_lines("a") == []


def test_normalize_cyrillic():
    assert normalize_text("ВЗРЫВ") == normalize_text("взрыв")


def test_build_effective_global_only():
    kw = build_effective_keywords(
        global_keywords=["взрыв"],
        global_keywords_enabled=True,
        channel_keywords=[],
        channel_keywords_enabled=False,
    )
    assert kw == ["взрыв"]


def test_build_effective_channel_only():
    kw = build_effective_keywords(
        global_keywords=["global"],
        global_keywords_enabled=True,
        channel_keywords=["local"],
        channel_keywords_enabled=True,
        use_global_keywords=False,
    )
    assert kw == ["local"]


def test_build_effective_union():
    kw = build_effective_keywords(
        global_keywords=["взрыв"],
        global_keywords_enabled=True,
        channel_keywords=["харків"],
        channel_keywords_enabled=True,
        use_global_keywords=True,
    )
    assert set(kw) == {"взрыв", "харків"}


def test_message_matches_substring():
    assert message_matches_keywords("Сообщение про взрыв в городе", ["взрыв"])


def test_message_matches_no_hit():
    assert not message_matches_keywords("Погода сегодня солнечная", ["взрыв"])


def test_empty_keywords_pass_all():
    assert message_matches_keywords("anything", [])
