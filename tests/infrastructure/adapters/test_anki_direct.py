from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arete.domain.models import AnkiNote, WorkItem

# Adjust path to import src if needed, but pytest handles it via pythonpath usually.
from arete.infrastructure.adapters.anki_direct import AnkiDirectAdapter


@pytest.fixture
def adapter():
    return AnkiDirectAdapter(anki_base=Path("/mock/anki"))


@pytest.fixture
def mock_repo():
    # Patch the AnkiRepository context manager
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        repo_instance = MockRepo.return_value.__enter__.return_value
        # Default: col exists
        repo_instance.col = MagicMock()
        yield repo_instance


@pytest.mark.asyncio
async def test_ensure_deck(adapter, mock_repo):
    # Setup
    mock_repo.col.decks.id.return_value = 1

    # Execute
    res = await adapter.ensure_deck("MyDeck")

    # Verify
    assert res is True
    mock_repo.col.decks.id.assert_called_with("MyDeck")


@pytest.mark.asyncio
async def test_sync_notes_add(adapter, mock_repo):
    # Setup
    note = AnkiNote(
        model="Basic",
        deck="MyDeck",
        fields={"Front": "F", "Back": "B"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("test.md"),
        source_index=0,
    )
    work_item = WorkItem(note=note, source_file=Path("test.md"), source_index=0)

    # Mock behavior: update returns False (not found), add returns ID
    mock_repo.update_note.return_value = False
    mock_repo.add_note.return_value = 12345

    # Execute
    results = await adapter.sync_notes([work_item])

    # Verify
    assert len(results) == 1
    res = results[0]
    assert res.ok is True
    assert res.new_nid == "12345"
    mock_repo.add_note.assert_called_once()


@pytest.mark.asyncio
async def test_sync_notes_update(adapter, mock_repo):
    # Setup
    note = AnkiNote(
        model="Basic",
        deck="MyDeck",
        fields={"Front": "F"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("test.md"),
        source_index=0,
        nid="999",
    )
    work_item = WorkItem(note=note, source_file=Path("test.md"), source_index=0)

    # Mock behavior: update returns True
    mock_repo.update_note.return_value = True

    # Execute
    results = await adapter.sync_notes([work_item])

    # Verify
    assert len(results) == 1
    assert results[0].ok is True
    assert results[0].new_nid == "999"
    mock_repo.update_note.assert_called_once()
    mock_repo.add_note.assert_not_called()


@pytest.mark.asyncio
async def test_get_notes_in_deck(adapter, mock_repo):
    mock_repo.find_notes.return_value = [101, 102]

    res = await adapter.get_notes_in_deck("MyDeck")

    assert res == {"101": 101, "102": 102}
    mock_repo.find_notes.assert_called_with('"deck:MyDeck"')


@pytest.mark.asyncio
async def test_sync_notes_db_failure(adapter):
    """Test full failure if DB cannot be opened"""
    item = WorkItem(note=MagicMock(), source_file=Path("x"), source_index=0)

    # Mock AnkiRepository raising exception on __enter__
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        MockRepo.return_value.__enter__.side_effect = Exception("DB Locked")

        results = await adapter.sync_notes([item])

        assert len(results) == 1
        assert results[0].ok is False
        assert "DB Error" in results[0].error
        assert "DB Locked" in results[0].error


@pytest.mark.asyncio
async def test_sync_notes_item_failure(adapter, mock_repo):
    """Test individual item failure during sync"""
    item = WorkItem(note=MagicMock(nid="123"), source_file=Path("x"), source_index=0)

    # Update raises exception
    mock_repo.update_note.side_effect = Exception("Update Failed")

    results = await adapter.sync_notes([item])

    assert len(results) == 1
    assert results[0].ok is False
    # The adapter catches exception inside the loop and returns error result
    assert "Unexpected" in results[0].error or "Update Failed" in results[0].error
