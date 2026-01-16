from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arete.domain.models import AnkiNote, WorkItem
from arete.infrastructure.adapters.anki_direct import AnkiDirectAdapter


@pytest.fixture
def mock_repo():
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as mock:
        # Context manager support
        mock_instance = mock.return_value
        mock_instance.__enter__.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def adapter():
    return AnkiDirectAdapter(anki_base=Path("/tmp/anki"))


@pytest.mark.asyncio
async def test_get_deck_names(adapter, mock_repo):
    mock_repo.col.decks.all_names.return_value = ["Default", "Math"]

    names = await adapter.get_deck_names()

    assert "Math" in names
    mock_repo.col.decks.all_names.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_deck_exists(adapter, mock_repo):
    mock_repo.col.decks.id.return_value = 1

    result = await adapter.ensure_deck("New Deck")

    assert result is True
    mock_repo.col.decks.id.assert_called_with("New Deck")


@pytest.mark.asyncio
async def test_sync_notes_insert(adapter, mock_repo):
    # Setup WorkItem
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "Q", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=5,
        source_file=Path("test.md"),
        source_index=1,
        nid=None,
    )
    item = WorkItem(source_file=Path("test.md"), source_index=0, note=note)

    # Setup mocks
    mock_repo.add_note.return_value = 12345

    # Execute
    updates = await adapter.sync_notes([item])

    # Verify
    assert len(updates) == 1
    assert updates[0].ok is True
    assert updates[0].new_nid == "12345"
    mock_repo.add_note.assert_called_once()


@pytest.mark.asyncio
async def test_sync_notes_update(adapter, mock_repo):
    # Setup WorkItem with NID
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "Q", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=5,
        source_file=Path("test.md"),
        source_index=1,
        nid="12345",
    )
    item = WorkItem(source_file=Path("test.md"), source_index=0, note=note)

    # Setup mocks
    mock_repo.update_note.return_value = True

    # Execute
    updates = await adapter.sync_notes([item])

    # Verify
    assert updates[0].ok is True
    assert updates[0].new_nid == "12345"
    mock_repo.update_note.assert_called_once()


@pytest.mark.asyncio
async def test_delete_notes(adapter, mock_repo):
    result = await adapter.delete_notes([1, 2, 3])
    assert result is True
    mock_repo.col.remove_notes.assert_called_once()


@pytest.mark.asyncio
async def test_get_learning_insights(adapter, mock_repo):
    # Mock find_cards
    # col.find_cards returns list of CIDs
    mock_repo.col.find_cards.side_effect = [
        [1, 2, 3],  # total cards
        [2],  # troublesome cards
    ]

    # Mock get_card
    mock_card = MagicMock()
    mock_card.nid = 100
    mock_card.lapses = 5
    mock_repo.col.get_card.return_value = mock_card

    # Mock get_note
    mock_note = MagicMock()
    mock_note.note_type.return_value = {
        "name": "Basic",
        "flds": [{"name": "Front"}, {"name": "Back"}],
    }
    mock_note.fields = ["Bad Card", "Back Content"]
    mock_repo.col.get_note.return_value = mock_note

    stats = await adapter.get_learning_insights(lapse_threshold=3)

    assert stats.total_cards == 3
    assert len(stats.problematic_notes) == 1
    assert stats.problematic_notes[0].note_name == "Bad Card"
    assert stats.problematic_notes[0].lapses == 5
