"""Tests for documentation merge script."""

from pathlib import Path

from scripts.merge_docs import CHAPTERS, DOCS_DIR, merge, slugify


def test_all_chapter_sources_exist():
    missing = [rp for rp, _ in CHAPTERS if not (DOCS_DIR / rp).is_file()]
    assert not missing, f"Missing docs: {missing}"


def test_merge_includes_all_chapters():
    text = merge()
    for _, title in CHAPTERS:
        assert f"# {title}" in text
    assert "AUTO-GENERATED" in text


def test_slugify_stable():
    assert slugify("Docker: Desktop Stack") == "docker-desktop-stack"


def test_merge_writes_expected_chapter_count():
    assert len(CHAPTERS) == 17
