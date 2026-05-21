"""Tests for bulk watchlist channel parsing."""

from core.incidents.watchlist_channels import parse_channel_lines, _channels_from_csv


def test_parse_channel_lines_multiline():
    text = "OsintTV\n@other, https://t.me/third"
    assert parse_channel_lines(text) == ["OsintTV", "other", "third"]


def test_parse_channel_lines_skips_comments():
    assert parse_channel_lines("# comment\n\nfoo") == ["foo"]


def test_parse_csv_first_column():
    raw = b"channel_ref\nAlpha\nBeta\n"
    assert _channels_from_csv(raw) == ["Alpha", "Beta"]
