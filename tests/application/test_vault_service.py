from unittest.mock import MagicMock

import pytest

from arete.application.vault_service import VaultService
from arete.infrastructure.persistence.cache import ContentCache


@pytest.fixture
def mock_cache():
    return MagicMock(spec=ContentCache)


@pytest.fixture
def temp_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def test_vault_service_uses_cache_by_default(temp_vault, mock_cache):
    """
    Verify that VaultService queries the cache when ignore_cache is False (default).
    """
    # Setup
    md_file = temp_vault / "test.md"
    md_file.write_text("---\ncards:\n  - Front: F\n    Back: B\n---\nBody", encoding="utf-8")

    # Simulate a cache hit
    mock_cache.get_file_meta.return_value = {"cards": [{"Front": "F"}], "anki_template_version": 1}

    service = VaultService(temp_vault, mock_cache, ignore_cache=False)

    files = list(service.scan_for_compatible_files())

    assert len(files) == 1
    # Should have called get_file_meta
    mock_cache.get_file_meta.assert_called_once()


def test_vault_service_bypasses_cache_when_ignored(temp_vault, mock_cache):
    """
    Verify that VaultService DOES NOT query the cache when ignore_cache is True.
    """
    # Setup
    md_file = temp_vault / "test.md"
    # Needs valid frontmatter because cache lookup will be skipped, so it must parse manually
    md_file.write_text(
        "---\nanki_template_version: 1\ndeck: Default\ncards:\n  - Front: F\n    Back: B\n---\nBody",
        encoding="utf-8",
    )

    service = VaultService(temp_vault, mock_cache, ignore_cache=True)

    files = list(service.scan_for_compatible_files())

    assert len(files) == 1
    # Should NOT have called get_file_meta
    mock_cache.get_file_meta.assert_not_called()

    # Since we bypassed cache and parsed successfully (mocked file has content),
    # it should set the new meta into cache
    mock_cache.set_file_meta.assert_called_once()
