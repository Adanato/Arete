from unittest.mock import MagicMock, patch

import pytest

from arete.application.vault_service import VaultService
from arete.domain.models import UpdateItem
from arete.infrastructure.persistence.cache import ContentCache


@pytest.fixture
def cache():
    c = MagicMock(spec=ContentCache)
    c.get_file_meta_by_stat.return_value = None
    return c


def test_vault_scan_skipped_bad_version(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    # version 99 is invalid
    f.write_text("---\nanki_template_version: 99\ncards: [{Front: f}]\ndeck: D\n---\n")

    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 0


def test_vault_scan_version_not_int(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    # version is not an integer
    f.write_text("---\nanki_template_version: 'nan'\ncards: [{Front: f}]\ndeck: D\n---\n")
    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 0


def test_vault_scan_read_error(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.touch()

    service = VaultService(vault, cache)
    with patch("pathlib.Path.read_text", side_effect=OSError("Read error")):
        files = list(service.scan_for_compatible_files())
        assert len(files) == 0


def test_vault_scan_no_deck(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.write_text("---\narete: true\ncards: [{Front: f}]\n---\n")

    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 0


def test_vault_scan_cards_not_list(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.write_text("---\narete: true\ncards: 'not_list'\ndeck: D\n---\n")
    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 0


def test_vault_apply_updates_read_fail(tmp_path, cache):
    f = tmp_path / "test.md"
    f.write_text("---\narete: true\ncards: [{Front: f}]\ndeck: D\n---\n")
    update = UpdateItem(
        ok=True, error=None, source_file=f, source_index=1, new_nid="123", new_cid="456"
    )
    service = VaultService(tmp_path, cache)
    with patch("pathlib.Path.read_text", side_effect=OSError("Panic")):
        service.apply_updates([update])


def test_vault_apply_updates_bad_yaml(tmp_path, cache):
    f = tmp_path / "test.md"
    f.write_text("---\nbad: : :\n---\n")
    update = UpdateItem(
        ok=True, error=None, source_file=f, source_index=1, new_nid="123", new_cid="456"
    )
    service = VaultService(tmp_path, cache)
    service.apply_updates([update])


def test_vault_cache_hit(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.write_text("---\narete: true\ncards: [{Front: f}]\ndeck: D\n---\n")

    cache.get_file_meta_by_stat.return_value = {
        "arete": True,
        "cards": [{"Front": "f"}],
        "deck": "D",
    }
    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 1
    cache.get_file_meta_by_stat.assert_called_once()


def test_vault_cache_exception(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.write_text("---\narete: true\ncards: [{Front: f}]\ndeck: D\n---\n")

    cache.get_file_meta_by_stat.side_effect = Exception("DB Fail")
    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 1


def test_vault_cache_corrupted(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.write_text("---\narete: true\ncards: [{Front: f}]\ndeck: D\n---\n")

    # Return a truthy object that fails .get()
    cache.get_file_meta_by_stat.return_value = "Not a dict"
    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    # Should fall back to parsing and succeed
    assert len(files) == 1


def test_vault_sets_cache(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.write_text("---\narete: true\ncards: [{Front: f}]\ndeck: D\n---\n")

    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 1
    cache.set_file_meta.assert_called_once()


def test_vault_scan_bad_yaml_content(tmp_path, cache):
    vault = tmp_path / "vault"
    vault.mkdir()
    f = vault / "test.md"
    f.write_text("---\nbad: : :\n---\n")
    service = VaultService(vault, cache)
    files = list(service.scan_for_compatible_files())
    assert len(files) == 0


def test_vault_apply_updates_success(tmp_path, cache):
    f = tmp_path / "test.md"
    f.write_text(
        "---\narete: true\ncards:\n  - Front: f\n    nid: ''\n    cid: ''\ndeck: D\n---\nBody"
    )

    update = UpdateItem(
        ok=True, error=None, source_file=f, source_index=1, new_nid="123", new_cid="456"
    )
    service = VaultService(tmp_path, cache)
    service.apply_updates([update])

    content = f.read_text()
    assert "nid: '123'" in content
    assert "cid: '456'" in content
