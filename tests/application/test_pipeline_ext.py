import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arete.application.config import AppConfig
from arete.application.pipeline import _prune_orphans, run_pipeline
from arete.domain.models import AnkiNote, UpdateItem

# from arete.infrastructure.adapters.anki_direct import AnkiDirectAdapter # Imported inside test to avoid early load?
# No, let's allow early load if mocked correctly.
from arete.infrastructure.adapters.anki_direct import AnkiDirectAdapter


@pytest.fixture
def logger():
    return logging.getLogger("test_pipeline")


@pytest.mark.asyncio
async def test_run_pipeline_no_compatible_files(logger):
    config = AppConfig(vault_root=Path("/mock"))
    vault_service = MagicMock()
    vault_service.scan_for_compatible_files.return_value = []

    stats = await run_pipeline(
        config, logger, "run1", vault_service, MagicMock(), MagicMock(), MagicMock()
    )

    assert stats.total_generated == 0
    assert stats.total_imported == 0


@pytest.mark.asyncio
async def test_run_pipeline_sync_failure(logger, tmp_path):
    config = AppConfig(vault_root=tmp_path, workers=1)
    vault_service = MagicMock()
    vault_service.scan_for_compatible_files.return_value = [(tmp_path / "test.md", {}, True)]

    parser = MagicMock()
    # Mock parse_file to return one note
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=tmp_path / "test.md",
        source_index=0,
        content_hash="h1",
    )
    parser.parse_file.return_value = ([note], [], [note])

    anki_bridge = AsyncMock()
    # Mock sync failure
    update = UpdateItem(
        ok=False,
        error="Sync error",
        source_file=tmp_path / "test.md",
        source_index=0,
        new_nid=None,
        new_cid=None,
    )
    anki_bridge.sync_notes.return_value = [update]

    cache = MagicMock()

    stats = await run_pipeline(config, logger, "run1", vault_service, parser, anki_bridge, cache)

    assert stats.total_errors == 1


@pytest.mark.asyncio
async def test_run_pipeline_consumer_crash(logger, tmp_path):
    config = AppConfig(vault_root=tmp_path, workers=1)
    vault_service = MagicMock()
    file_path = tmp_path / "test.md"
    vault_service.scan_for_compatible_files.return_value = [(file_path, {}, True)]

    parser = MagicMock()
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=tmp_path / "test.md",
        source_index=0,
        content_hash="h1",
    )
    parser.parse_file.return_value = ([note], [], [note])

    anki_bridge = AsyncMock()
    anki_bridge.sync_notes.side_effect = Exception("Crash")

    stats = await run_pipeline(
        config, logger, "run1", vault_service, parser, anki_bridge, MagicMock()
    )

    assert stats.total_errors == 1


@pytest.mark.asyncio
async def test_prune_orphans_wrong_root(logger):
    config = AppConfig(vault_root=Path("/vault"), root_input=Path("/vault/subdir"), prune=True)
    recorder = MagicMock()
    bridge = AsyncMock()

    await _prune_orphans(config, recorder, bridge, logger)
    bridge.get_deck_names.assert_not_called()


@pytest.mark.asyncio
async def test_prune_orphans_no_decks(logger):
    config = AppConfig(vault_root=Path("/vault"), root_input=Path("/vault"), prune=True)
    recorder = MagicMock()
    recorder.inventory_decks = ["Default"]
    bridge = AsyncMock()
    bridge.get_deck_names.return_value = ["Default"]

    await _prune_orphans(config, recorder, bridge, logger)
    bridge.get_notes_in_deck.assert_not_called()


@pytest.mark.asyncio
async def test_prune_orphans_abort(logger):
    config = AppConfig(
        vault_root=Path("/vault"), root_input=Path("/vault"), prune=True, force=False
    )
    recorder = MagicMock()
    recorder.inventory_nids = []
    recorder.inventory_decks = ["D1"]
    bridge = AsyncMock()
    bridge.get_deck_names.return_value = ["D1", "D2"]
    bridge.get_notes_in_deck.return_value = {}

    with patch("builtins.input", return_value="no"):
        await _prune_orphans(config, recorder, bridge, logger)
        bridge.delete_decks.assert_not_called()


@pytest.mark.asyncio
async def test_run_pipeline_with_apy_sequential(logger, tmp_path):
    config = AppConfig(vault_root=tmp_path, workers=4)
    vault_service = MagicMock()
    vault_service.scan_for_compatible_files.return_value = []

    # AnkiDirectAdapter is sequential (SQLite)

    bridge = MagicMock(spec=AnkiDirectAdapter)

    await run_pipeline(config, logger, "run1", vault_service, MagicMock(), bridge, MagicMock())
