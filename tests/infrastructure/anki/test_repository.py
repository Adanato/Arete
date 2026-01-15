from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arete.domain.models import AnkiNote
from arete.infrastructure.anki.repository import AnkiRepository


@pytest.fixture
def mock_col():
    """Mock the Anki Collection object"""
    col = MagicMock()
    col.close = MagicMock()
    return col


@pytest.fixture
def mock_anki_import():
    """Ensure Anki module mocks are in place via conftest, but catch any local import issues"""
    import anki

    return anki


@pytest.fixture
def mock_repo_cls(mock_col):
    with (
        patch("arete.infrastructure.anki.repository.Collection", return_value=mock_col),
        patch.object(
            AnkiRepository,
            "_resolve_collection_path",
            return_value=Path("/tmp/anki/collection.anki2"),
        ),
    ):
        yield


def test_repo_context_manager(mock_col, mock_repo_cls):
    with AnkiRepository(Path("/tmp/anki")) as repo:
        assert repo.col is mock_col
    mock_col.close.assert_called()


def test_add_note(mock_col, mock_repo_cls):
    # Setup
    note_data = AnkiNote(
        model="Basic",
        deck="D",
        fields={"Front": "F", "Back": "B"},
        tags=["t"],
        source_file=Path("f.md"),
        source_index=0,
        start_line=1,
        end_line=2,
    )

    # Mocks
    mock_model = {"id": 1, "name": "Basic", "flds": [{"name": "Front"}, {"name": "Back"}]}
    mock_col.models.by_name.return_value = mock_model
    mock_col.decks.id.return_value = 101

    mock_note_instance = MagicMock()
    mock_note_instance.id = 0
    mock_col.new_note.return_value = mock_note_instance

    with AnkiRepository(Path("/tmp")) as repo:
        repo.add_note(note_data)

        # Verify interactions
        mock_col.decks.id.assert_called_with("D")
        mock_col.new_note.assert_called()
        mock_col.add_note.assert_called_with(mock_note_instance, 101)
        # Verify fields set
        mock_note_instance.__setitem__.assert_any_call("Front", "F")


def test_update_note_success(mock_col, mock_repo_cls):
    note_data = AnkiNote(
        model="Basic",
        deck="D",
        fields={"Front": "F"},
        tags=[],
        nid="123",
        source_file=Path("f.md"),
        source_index=0,
        start_line=1,
        end_line=2,
    )

    # Mock get_note
    mock_existing_note = MagicMock()
    mock_existing_note.note_type = MagicMock(
        return_value={"name": "Basic", "flds": [{"name": "Front"}]}
    )
    mock_existing_note.cards = MagicMock(return_value=[MagicMock(did=101)])
    mock_existing_note.tags = []

    # Configure __getitem__ to return current value for comparison check
    # But repo logic: if note[f_name] != new_html: ...
    # So we need __getitem__ to return DIFFERENT value initially to trigger update.
    # Or same value to NOT trigger update.
    # Logic: line 195: if note[f_name] != new_html:
    # MagicMock() != "F" is True. So it sets it.

    mock_col.get_note.return_value = mock_existing_note
    mock_col.decks.id.return_value = 101

    with AnkiRepository(Path("/tmp")) as repo:
        res = repo.update_note(123, note_data)

        assert res is True
        mock_col.get_note.assert_called_with(123)
        # Verify update
        mock_existing_note.__setitem__.assert_any_call("Front", "F")
        mock_col.update_note.assert_called_with(mock_existing_note)


def test_update_note_not_found(mock_col, mock_repo_cls):
    # Mock NotFound exception
    from anki.errors import NotFound

    mock_col.get_note.side_effect = NotFound

    note_data = AnkiNote(
        model="B",
        deck="D",
        fields={},
        tags=[],
        nid="999",
        source_file=Path("f.md"),
        source_index=0,
        start_line=1,
        end_line=1,
    )

    with AnkiRepository(Path("/tmp")) as repo:
        res = repo.update_note(999, note_data)
        assert res is False


def test_find_notes(mock_col, mock_repo_cls):
    mock_col.find_notes.return_value = [1, 2, 3]
    with AnkiRepository(Path("/tmp")) as repo:
        res = repo.find_notes("query")
        assert res == [1, 2, 3]
        mock_col.find_notes.assert_called_with("query")


def test_access_col_methods(mock_col, mock_repo_cls):
    """Verify repo exposes col for delete operations used by adapter"""
    with AnkiRepository(Path("/tmp")) as repo:
        repo.col.remove_notes = MagicMock()
        repo.col.decks.remove = MagicMock()

        # Simulate adapter logic
        repo.col.remove_notes([1, 2])
        repo.col.decks.remove([3])

        repo.col.remove_notes.assert_called_with([1, 2])
        repo.col.decks.remove.assert_called_with([3])
