from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from arete.domain.models import AnkiNote, WorkItem
from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    a = AnkiConnectAdapter("http://localhost:8765")
    setattr(a, "_invoke", AsyncMock())  # noqa: B010
    setattr(a, "ensure_deck", AsyncMock(return_value=True))  # noqa: B010
    return a


def _make_work_item(fields, model="Basic", deck="TestDeck"):
    note = AnkiNote(
        model=model,
        deck=deck,
        fields=fields,
        tags=[],
        start_line=1,
        end_line=5,
        source_file=Path("test.md"),
        source_index=1,
    )
    return WorkItem(note=note, source_file=Path("test.md"), source_index=1)


@pytest.mark.asyncio
async def test_healing_via_dict_comparison(adapter):
    """Verify that healing finds an existing note by comparing field values."""
    work_item = _make_work_item({"Front": "What is a claim?", "Back": "Answer"})

    async def side_effect(action, **kwargs):
        if action == "findNotes":
            return [100, 200, 300]
        if action == "notesInfo":
            return [
                {"noteId": 100, "fields": {"Front": {"value": "Unrelated"}, "Back": {"value": "X"}}},
                {"noteId": 200, "fields": {"Front": {"value": "What is a claim?"}, "Back": {"value": "Old"}}},
                {"noteId": 300, "fields": {"Front": {"value": "Other"}, "Back": {"value": "Y"}}},
            ]
        if action == "updateNoteFields":
            return None
        if action == "cardsInfo":
            return [{"cardId": 999}]
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    assert results[0].ok is True
    assert results[0].new_nid == "200"


@pytest.mark.asyncio
async def test_healing_cloze_normalization(adapter):
    """Verify that cloze markers are stripped during comparison."""
    work_item = _make_work_item(
        {"Text": "The {{c1::sun}} rises in the {{c2::east}}.", "Back Extra": ""},
        model="Cloze",
    )

    async def side_effect(action, **kwargs):
        if action == "findNotes":
            return [500]
        if action == "notesInfo":
            # Anki stores the cloze syntax in the field
            return [
                {
                    "noteId": 500,
                    "fields": {
                        "Text": {"value": "<!-- arete markdown -->\n<p>The {{c1::sun}} rises in the {{c2::east}}.</p>"},
                        "Back Extra": {"value": ""},
                    },
                    "cards": [501],
                }
            ]
        if action == "updateNoteFields":
            return None
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    assert results[0].ok is True
    assert results[0].new_nid == "500"


@pytest.mark.asyncio
async def test_healing_html_normalization(adapter):
    """Verify that HTML tags are stripped during comparison."""
    work_item = _make_work_item({"Front": "<b>Bold</b> question?", "Back": "A"})

    async def side_effect(action, **kwargs):
        if action == "findNotes":
            return [700]
        if action == "notesInfo":
            return [
                {
                    "noteId": 700,
                    "fields": {
                        "Front": {"value": "<div><b>Bold</b> question?</div>"},
                        "Back": {"value": "A"},
                    },
                    "cards": [701],
                }
            ]
        if action == "updateNoteFields":
            return None
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert results[0].ok is True
    assert results[0].new_nid == "700"


@pytest.mark.asyncio
async def test_healing_no_match_falls_through_to_add(adapter):
    """When no existing note matches, addNote is called."""
    work_item = _make_work_item({"Front": "Brand new card", "Back": "A"})

    call_log = []

    async def side_effect(action, **kwargs):
        call_log.append(action)
        if action == "findNotes":
            return [800]
        if action == "notesInfo":
            if 800 in kwargs.get("notes", []):
                return [
                    {"noteId": 800, "fields": {"Front": {"value": "Different card"}, "Back": {"value": "B"}}}
                ]
            if 900 in kwargs.get("notes", []):
                return [{"noteId": 900, "cards": [901]}]
            return []
        if action == "addNote":
            return 900
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert results[0].ok is True
    assert results[0].new_nid == "900"
    assert "addNote" in call_log


@pytest.mark.asyncio
async def test_healing_empty_candidates(adapter):
    """When findNotes returns empty, addNote is called."""
    work_item = _make_work_item({"Front": "Q", "Back": "A"})

    async def side_effect(action, **kwargs):
        if action == "findNotes":
            return []
        if action == "addNote":
            return 1001
        if action == "notesInfo":
            return [{"noteId": 1001, "cards": [2002]}]
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert results[0].ok is True
    assert results[0].new_nid == "1001"
    assert results[0].new_cid == "2002"


@pytest.mark.asyncio
async def test_healing_query_failure_falls_through(adapter):
    """If findNotes raises, we still try addNote."""
    work_item = _make_work_item({"Front": "Q", "Back": "A"})

    call_log = []

    async def side_effect(action, **kwargs):
        call_log.append(action)
        if action == "findNotes":
            raise Exception("search broken")
        if action == "addNote":
            return 1001
        if action == "notesInfo":
            return [{"noteId": 1001, "cards": [2002]}]
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert results[0].ok is True
    assert "addNote" in call_log


@pytest.mark.asyncio
async def test_healing_duplicate_error_propagates_when_no_match(adapter):
    """If addNote says duplicate but healing can't find the note, error propagates."""
    work_item = _make_work_item({"Front": "Q", "Back": "A"})

    async def side_effect(action, **kwargs):
        if action == "findNotes":
            return []  # No candidates found
        if action == "addNote":
            raise Exception("cannot create note because it is a duplicate")
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert results[0].ok is False
    assert "duplicate" in results[0].error


@pytest.mark.asyncio
async def test_normalize_field():
    """Verify _normalize_field strips HTML, cloze markers, and normalizes whitespace."""
    norm = AnkiConnectAdapter._normalize_field

    assert norm("Hello World") == "hello world"
    assert norm("<b>Bold</b>") == "bold"
    assert norm("{{c1::answer}} is {{c2::correct}}") == "answer is correct"
    assert norm("<!-- comment -->\n<p>Text</p>") == "text"
    assert norm("  lots   of    spaces  ") == "lots of spaces"
    assert norm("Mixed: {{c1::cloze}} and <em>html</em>") == "mixed: cloze and html"


@pytest.mark.asyncio
async def test_cid_fetching_on_create(adapter):
    """Verify that after a successful addNote, we fetch the CID."""
    work_item = _make_work_item({"Front": "Q", "Back": "A"})

    async def side_effect(action, **kwargs):
        if action == "findNotes":
            return []
        if action == "addNote":
            return 1001
        if action == "notesInfo":
            if kwargs.get("notes") == [1001]:
                return [{"noteId": 1001, "cards": [2002]}]
            return []
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert results[0].ok is True
    assert results[0].new_nid == "1001"
    assert results[0].new_cid == "2002"


@pytest.mark.asyncio
async def test_cid_fetching_on_heal(adapter):
    """Verify that after healing, we also fetch the CID."""
    work_item = _make_work_item({"Front": "DuplicateQ", "Back": "A"})

    async def side_effect(action, **kwargs):
        if action == "findNotes":
            return [5555]
        if action == "notesInfo":
            if kwargs.get("notes") == [5555]:
                return [
                    {
                        "noteId": 5555,
                        "fields": {"Front": {"value": "DuplicateQ"}, "Back": {"value": "old"}},
                        "cards": [6666],
                    }
                ]
            return []
        if action == "updateNoteFields":
            return None
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert results[0].ok is True
    assert results[0].new_nid == "5555"
    assert results[0].new_cid == "6666"
