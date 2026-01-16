from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

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
async def test_db_open_failure(adapter, mock_repo):
    # Simulate DB open failure in Context Manager
    # The context manager __enter__ raises, or the constructor?
    # The code does: with AnkiRepository(...) as repo:
    # If AnkiRepository constructor opens DB, it might raise there.
    # The current mock implementation mocks the class.
    # To mock failure, we can make the instance's __enter__ raise.
    mock_repo.__enter__.side_effect = Exception("DB Locked")

    item = WorkItem(
        source_file=Path("f.md"),
        source_index=0,
        note=AnkiNote(
            model="M",
            deck="D",
            fields={},
            tags=[],
            start_line=1,
            end_line=1,
            source_file=Path("f.md"),
            source_index=1,
        ),
    )

    results = await adapter.sync_notes([item])

    assert len(results) == 1
    assert results[0].ok is False
    assert "DB Error" in results[0].error
    assert "DB Locked" in results[0].error


@pytest.mark.asyncio
async def test_update_missing_note_fallback(adapter, mock_repo):
    # Note has NID but update returns False (not found)
    note = AnkiNote(
        model="M",
        deck="D",
        fields={},
        nid="999",
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("f.md"),
        source_index=1,
    )
    item = WorkItem(source_file=Path("f.md"), source_index=0, note=note)

    # Update returns False
    mock_repo.update_note.return_value = False
    # Add returns new ID
    mock_repo.add_note.return_value = 1000

    results = await adapter.sync_notes([item])

    assert results[0].ok is True
    assert results[0].new_nid == "1000"
    mock_repo.update_note.assert_called()
    mock_repo.add_note.assert_called()


@pytest.mark.asyncio
async def test_get_model_names(adapter, mock_repo):
    mock_repo.col.models.all.return_value = [{"name": "Basic"}, {"name": "Cloze"}]

    names = await adapter.get_model_names()

    assert "Basic" in names
    assert "Cloze" in names


@pytest.mark.asyncio
async def test_delete_decks(adapter, mock_repo):
    mock_repo.col.decks.id.return_value = 1

    result = await adapter.delete_decks(["OldDeck"])

    assert result is True
    assert result is True
    mock_repo.col.decks.remove.assert_called_with([1])


@pytest.mark.asyncio
async def test_repo_no_collection_fallbacks(adapter):
    # Mock AnkiRepository context to return an object with col=None
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.col = None

        # Test all methods that guard on repo.col
        assert await adapter.get_model_names() == []
        assert (
            await adapter.ensure_deck("D") is False
        )  # Actually guards inside? existing logic returns False
        assert await adapter.get_deck_names() == []
        assert await adapter.get_notes_in_deck("D") == {}
        assert await adapter.delete_notes([1]) is False
        assert await adapter.delete_decks(["D"]) is False

        stats = await adapter.get_learning_insights()
        assert stats.total_cards == 0


@pytest.mark.asyncio
async def test_delete_notes_empty(adapter):
    assert await adapter.delete_notes([]) is True


@pytest.mark.asyncio
async def test_insights_missing_model(adapter, mock_repo):
    # Mock find_cards returning cards
    # Use lambda to avoid iterator exhaustion/StopIteration
    mock_repo.col.find_cards.side_effect = lambda *args: [1]

    # Mock card
    mock_card = MagicMock()
    mock_card.nid = 100
    mock_card.lapses = 5
    mock_repo.col.get_card.return_value = mock_card

    # Mock note with missing model
    mock_note = MagicMock()
    mock_note.note_type.return_value = None  # No model
    mock_repo.col.get_note.return_value = mock_note

    stats = await adapter.get_learning_insights(lapse_threshold=3)

    stats = await adapter.get_learning_insights(lapse_threshold=3)

    assert len(stats.problematic_notes) == 0


@pytest.mark.asyncio
async def test_add_failed(adapter, mock_repo):
    item = WorkItem(
        source_file=Path("f.md"),
        source_index=0,
        note=AnkiNote(
            model="M",
            deck="D",
            fields={},
            nid=None,
            tags=[],
            start_line=1,
            end_line=1,
            source_file=Path("f"),
            source_index=0,
        ),
    )
    mock_repo.add_note.side_effect = Exception("Add Error")

    results = await adapter.sync_notes([item])
    assert "Add failed" in results[0].error


@pytest.mark.asyncio
async def test_loop_exception(adapter, mock_repo):
    # Mock item such that accessing item.note raises
    item = MagicMock()
    type(item).note = PropertyMock(side_effect=Exception("Critical Fail"))
    item.source_file = Path("f.md")
    item.source_index = 0

    results = await adapter.sync_notes([item])
    assert results[0].ok is False
    assert "Unexpected error" in results[0].error


@pytest.mark.asyncio
async def test_insights_fallback_name(adapter, mock_repo):
    mock_repo.col.find_cards.side_effect = lambda *args: [1]
    mock_card = MagicMock()
    mock_card.nid = 100
    mock_card.lapses = 5
    mock_repo.col.get_card.return_value = mock_card

    mock_note = MagicMock()
    mock_note.note_type.return_value = {"name": "M", "flds": [{"name": "F"}]}
    # Fallback path: no _obsidian_source, use first field
    mock_note.fields = ["First Field Value"]
    mock_repo.col.get_note.return_value = mock_note

    stats = await adapter.get_learning_insights(lapse_threshold=3)

    assert len(stats.problematic_notes) == 1
    assert stats.problematic_notes[0].note_name == "First Field Value"
