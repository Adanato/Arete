from unittest.mock import MagicMock

import pytest
from o2a.consts import CURRENT_TEMPLATE_VERSION
from o2a.infrastructure.cache import ContentCache
from o2a.services.vault import VaultService


@pytest.fixture
def mock_cache():
    # Helper to mock ContentCache
    c = MagicMock(spec=ContentCache)
    c.get_file_meta.return_value = None
    c.set_file_meta.return_value = None
    return c


def test_quick_check_valid_file(tmp_path, mock_cache):
    f = tmp_path / "valid.md"
    f.write_text(
        f"""---
anki_template_version: {CURRENT_TEMPLATE_VERSION}
deck: Test
cards:
  - Front: Q
    Back: A
---
Content
""",
        encoding="utf-8",
    )

    service = VaultService(root=tmp_path, cache=mock_cache)
    ok, count, err, meta = service._quick_check_file(f)
    assert ok is True
    assert count == 1
    assert err is None
    assert meta is not None
    assert meta["deck"] == "Test"


def test_quick_check_invalid_version(tmp_path, mock_cache):
    f = tmp_path / "old.md"
    f.write_text(
        """---
anki_template_version: 0
cards: []
---
""",
        encoding="utf-8",
    )

    service = VaultService(root=tmp_path, cache=mock_cache)
    ok, count, err, meta = service._quick_check_file(f)
    assert ok is False
    assert err == "bad_template_version"


def test_quick_check_no_cards(tmp_path, mock_cache):
    f = tmp_path / "empty.md"
    f.write_text(
        f"""---
anki_template_version: {CURRENT_TEMPLATE_VERSION}
deck: Test
---
""",
        encoding="utf-8",
    )

    service = VaultService(root=tmp_path, cache=mock_cache)
    ok, count, err, meta = service._quick_check_file(f)
    assert ok is False
    assert err == "no_cards"


def test_quick_check_cache_hit(tmp_path, mock_cache):
    f = tmp_path / "cached.md"
    f.write_text("Dummy content on disk", encoding="utf-8")

    # Simulate cache hit
    mock_cache.get_file_meta.return_value = {"cards": [1, 2, 3], "deck": "D"}

    service = VaultService(root=tmp_path, cache=mock_cache)
    ok, count, err, meta = service._quick_check_file(f)

    assert ok is True
    assert count == 3
    # Should not have parsed the "Dummy content" as YAML because it hit cache
