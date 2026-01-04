from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from o2a.services.parser import MarkdownParser


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get_hash.return_value = None  # No cache hit
    return cache


@pytest.fixture
def parser_fixture(tmp_path):
    vault_root = tmp_path / "Vault"
    vault_root.mkdir()
    media_dir = tmp_path / "Media"
    media_dir.mkdir()
    parser = MarkdownParser(vault_root, media_dir)
    return parser, vault_root


def test_parse_simple_card(parser_fixture, mock_cache):
    parser, vault = parser_fixture
    md_file = vault / "test.md"

    # Minimal valid frontmatter
    meta = {
        "deck": "Default",
        "cards": [
            {
                "model": "Basic",
                "Front": "Question",
                "Back": "Answer",
            }
        ],
    }

    notes, skipped, inventory = parser.parse_file(md_file, meta, mock_cache)

    assert len(notes) == 1
    assert len(skipped) == 0
    note = notes[0]

    # Check fields that caused the crash
    assert note.source_file == md_file
    assert note.source_index == 1
    assert len(notes) == 1
    assert notes[0].fields["Front"] == "Question"


def test_parse_basic_missing_fields(parser_fixture):
    parser, _ = parser_fixture
    meta = {
        "cards": [
            {"model": "Basic", "Front": "Only Front"},
            {"model": "Basic", "Back": "Only Back"},
        ]
    }
    notes, skipped, inventory = parser.parse_file(Path("test.md"), meta, MagicMock())
    assert len(notes) == 0
    assert len(skipped) == 2


def test_parse_cloze_missing_text(parser_fixture):
    parser, _ = parser_fixture
    meta = {
        "cards": [
            {"model": "Cloze", "Extra": "Hint"},
        ]
    }
    notes, skipped, inventory = parser.parse_file(Path("test.md"), meta, MagicMock())
    assert len(notes) == 0
    assert len(skipped) == 1


def test_parse_custom_no_fields(parser_fixture):
    parser, _ = parser_fixture
    meta = {
        "cards": [
            {"model": "Custom", "cid": "123"},  # Only special fields, no content
        ]
    }
    notes, skipped, inventory = parser.parse_file(Path("test.md"), meta, MagicMock())
    assert len(notes) == 0
    assert len(skipped) == 1


def test_parse_exception_handling(parser_fixture):
    parser, _ = parser_fixture
    parser.logger = MagicMock()  # Mock the logger

    # Mock image transform to raise exception (happens inside the loop)
    with patch("o2a.services.parser.transform_images_in_text", side_effect=Exception(" Boom ")):
        meta = {"cards": [{"model": "Basic", "Front": "F", "Back": "B"}]}
        notes, skipped, inventory = parser.parse_file(Path("test.md"), meta, MagicMock())
        assert len(notes) == 0
        assert len(skipped) == 1
        # Should log error
        parser.logger.error.assert_called()


def test_parse_missing_fields(parser_fixture, mock_cache):
    parser, vault = parser_fixture
    md_file = vault / "bad.md"

    meta = {
        "cards": [
            {
                "model": "Basic",
                # Missing Front/Back
            }
        ]
    }

    notes, skipped, inventory = parser.parse_file(md_file, meta, mock_cache)
    assert len(notes) == 0
    assert len(skipped) == 1
