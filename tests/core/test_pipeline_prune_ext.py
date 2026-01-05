from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from o2a.core.pipeline import _prune_orphans


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.vault_root = Path("/v")
    config.root_input = Path("/v")
    config.force = False
    config.dry_run = False
    return config


@pytest.mark.asyncio
async def test_prune_orphans_aborted(mock_config):
    anki_bridge = MagicMock()
    anki_bridge.get_deck_names = AsyncMock(return_value=["Default", "Deck1"])
    anki_bridge.get_notes_in_deck = AsyncMock(return_value={"2": 222})

    recorder = MagicMock()
    recorder.inventory_nids = {"1"}  # "2" is orphan
    recorder.inventory_decks = {"Deck1"}

    logger = MagicMock()

    with patch("builtins.input", return_value="no"):
        await _prune_orphans(mock_config, recorder, anki_bridge, logger)
        anki_bridge.delete_notes.assert_not_called()


@pytest.mark.asyncio
async def test_prune_orphans_success_confirmed(mock_config):
    anki_bridge = MagicMock()
    anki_bridge.get_deck_names = AsyncMock(return_value=["Default", "Deck1"])
    anki_bridge.get_notes_in_deck = AsyncMock(return_value={"2": 222})
    anki_bridge.delete_notes = AsyncMock(return_value=True)
    anki_bridge.delete_decks = AsyncMock(return_value=True)

    recorder = MagicMock()
    recorder.inventory_nids = {"1"}
    recorder.inventory_decks = {"Deck1"}

    logger = MagicMock()

    with patch("builtins.input", return_value="yes"):
        await _prune_orphans(mock_config, recorder, anki_bridge, logger)
        anki_bridge.delete_notes.assert_called_once_with([222])


@pytest.mark.asyncio
async def test_prune_orphans_dry_run(mock_config):
    mock_config.dry_run = True
    anki_bridge = MagicMock()
    anki_bridge.get_deck_names = AsyncMock(return_value=["Default", "Deck1"])
    anki_bridge.get_notes_in_deck = AsyncMock(return_value={"2": 222})

    recorder = MagicMock()
    recorder.inventory_nids = {"1"}
    recorder.inventory_decks = {"Deck1"}

    logger = MagicMock()
    with patch("builtins.input", return_value="yes"):
        await _prune_orphans(mock_config, recorder, anki_bridge, logger)

    anki_bridge.delete_notes.assert_not_called()
    logger.warning.assert_any_call("[prune] DRY RUN: Destructive actions skipped.")


@pytest.mark.asyncio
async def test_prune_orphans_empty(mock_config):
    anki_bridge = MagicMock()
    anki_bridge.get_deck_names = AsyncMock(return_value=["Default", "Deck1"])
    anki_bridge.get_notes_in_deck = AsyncMock(return_value={"1": 111})

    recorder = MagicMock()
    recorder.inventory_nids = {"1"}
    recorder.inventory_decks = {"Deck1"}

    logger = MagicMock()
    await _prune_orphans(mock_config, recorder, anki_bridge, logger)
    anki_bridge.delete_notes.assert_not_called()


@pytest.mark.asyncio
async def test_prune_orphans_skipped_root_mismatch(mock_config):
    mock_config.root_input = Path("/v/sub")
    mock_config.vault_root = Path("/v")

    anki_bridge = MagicMock()
    recorder = MagicMock()
    logger = MagicMock()

    await _prune_orphans(mock_config, recorder, anki_bridge, logger)
    logger.warning.assert_called_with(
        "[prune] SKIPPED: Pruning requires running on the entire vault root to ensure safety."
    )


@pytest.mark.asyncio
async def test_prune_orphans_delete_error_handling(mock_config):
    anki_bridge = MagicMock()
    anki_bridge.get_deck_names = AsyncMock(return_value=["Default", "Deck1"])
    anki_bridge.get_notes_in_deck = AsyncMock(return_value={"2": 222})
    anki_bridge.delete_notes = AsyncMock(side_effect=Exception("API Error"))

    recorder = MagicMock()
    recorder.inventory_nids = {"1"}
    recorder.inventory_decks = {"Deck1"}

    logger = MagicMock()
    with patch("builtins.input", return_value="yes"):
        await _prune_orphans(mock_config, recorder, anki_bridge, logger)
        logger.error.assert_called_with("[prune] Failed to delete notes: API Error")
