from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from arete.domain.types import AnkiNote, WorkItem
from arete.services.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    a = AnkiConnectAdapter("http://localhost:8765")
    # Use setattr to bypass strict type checks on assignment
    setattr(a, "_invoke", AsyncMock())  # noqa: B010
    setattr(a, "ensure_deck", AsyncMock(return_value=True))  # noqa: B010
    return a


@pytest.mark.asyncio
async def test_healing_search_sanitization(adapter):
    """
    Verify that when a duplicate error occurs, the search query used to find the existing note
    is properly sanitized (newlines removed, quotes escaped).
    """
    note = AnkiNote(
        model="Basic",
        deck="TestDeck",
        fields={"Front": 'Line 1\nLine 2\rLine 3 "Quotes"', "Back": "Answer"},
        tags=[],
        start_line=1,
        end_line=5,
        source_file=Path("test.md"),
        source_index=1,
    )
    work_item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    # 2. Mock _invoke behaviors
    async def side_effect(action, **kwargs):
        if action == "addNote":
            raise Exception("cannot create note because it is a duplicate")
        if action == "findNotes":
            return [12345]
        if action == "notesInfo":
            return [{"noteId": 12345, "cards": [98765]}]
        return None

    adapter._invoke.side_effect = side_effect

    # 3. Run sync_notes
    await adapter.sync_notes([work_item])

    found_query = None
    for c in adapter._invoke.call_args_list:
        if c[0][0] == "findNotes":
            found_query = c[1]["query"]
            break

    assert found_query is not None, "findNotes was never called"

    # Verify sanitization
    assert "\n" not in found_query
    assert "\r" not in found_query
    assert '\\"' in found_query
    assert 'Line 1 Line 2 Line 3 \\"Quotes\\"' in found_query


@pytest.mark.asyncio
async def test_healing_search_robustness(adapter):
    """
    Verify handling of vertical tabs and literal backslashes (common in MathJax).
    """
    note = AnkiNote(
        model="Basic",
        deck="TestDeck",
        fields={"Front": "Math: \\rho and \\v space\vhere", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x"), 1)

    async def side_effect(action, **kwargs):
        if action == "addNote":
            raise Exception("duplicate")
        if action == "findNotes":
            return [1]
        if action == "notesInfo":
            return [{"noteId": 1, "cards": [1]}]

    adapter._invoke.side_effect = side_effect
    await adapter.sync_notes([work_item])

    found_query = None
    for c in adapter._invoke.call_args_list:
        if c[0][0] == "findNotes":
            found_query = c[1]["query"]
            break

    assert found_query is not None
    assert "\v" not in found_query
    assert "\\\\rho" in found_query or "\\rho" in found_query
    assert "space here" in found_query


@pytest.mark.asyncio
async def test_healing_search_query_limit(adapter):
    """
    Verify that very long fields are truncated in the search query.
    """
    long_text = "A" * 200
    note = AnkiNote(
        model="Basic",
        deck="TestDeck",
        fields={"Front": long_text, "Back": "A"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x"), 1)

    async def side_effect(action, **kwargs):
        if action == "addNote":
            raise Exception("duplicate")
        if action == "findNotes":
            return [1]
        if action == "notesInfo":
            return [{"noteId": 1, "cards": [1]}]

    adapter._invoke.side_effect = side_effect
    await adapter.sync_notes([work_item])

    found_query = None
    for c in adapter._invoke.call_args_list:
        if c[0][0] == "findNotes":
            found_query = c[1]["query"]
            break

    assert found_query is not None

    assert len(found_query) < 200
    # Field part truncated to 100 chars
    assert "A" * 80 in found_query
    assert "A" * 150 not in found_query


@pytest.mark.asyncio
async def test_healing_search_quote_hell(adapter):
    """
    Verify handling of mixed double quotes and literal backslashes typical in code blocks.
    """
    raw = 'print("Hello \\"World\\"") \n path = "C:\\\\User"'
    note = AnkiNote(
        model="Basic",
        deck="TestDeck",
        fields={"Front": raw, "Back": "A"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x"), 1)

    async def side_effect(action, **kwargs):
        if action == "addNote":
            raise Exception("duplicate")
        if action == "findNotes":
            return [1]
        if action == "notesInfo":
            return [{"noteId": 1, "cards": [1]}]

    adapter._invoke.side_effect = side_effect
    await adapter.sync_notes([work_item])

    found_query = None
    for c in adapter._invoke.call_args_list:
        if c[0][0] == "findNotes":
            found_query = c[1]["query"]
            break

    assert found_query is not None
    assert '\\"Hello' in found_query
    assert "C:\\\\\\\\User" in found_query or "C:\\\\User" in found_query


@pytest.mark.asyncio
async def test_healing_failure_propagates_error(adapter):
    """
    Verify that if the search fails to find a candidate, original Duplicate error is raised.
    """
    note = AnkiNote(
        model="Basic",
        deck="TestDeck",
        fields={"Front": "Q", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x"), 1)

    async def side_effect(action, **kwargs):
        if action == "addNote":
            raise Exception("cannot create note because it is a duplicate")
        if action == "findNotes":
            return []
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    assert results[0].ok is False
    assert "duplicate" in results[0].error


@pytest.mark.asyncio
async def test_cid_fetching_on_create(adapter):
    """
    Verify that after a successful addNote, we fetch the CID.
    """
    note = AnkiNote(
        model="Basic",
        deck="TestDeck",
        fields={"Front": "Q", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x"), 1)

    async def side_effect(action, **kwargs):
        if action == "addNote":
            return 1001
        if action == "notesInfo":
            if kwargs.get("notes") == [1001]:
                return [{"noteId": 1001, "cards": [2002]}]
            return []
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    res = results[0]

    assert res.ok is True
    assert res.new_nid == "1001"
    assert res.new_cid == "2002"


@pytest.mark.asyncio
async def test_cid_fetching_on_heal(adapter):
    """
    Verify that after healing, we also fetch the CID.
    """
    note = AnkiNote(
        model="Basic",
        deck="TestDeck",
        fields={"Front": "DuplicateQ", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x"), 1)

    async def side_effect(action, **kwargs):
        if action == "addNote":
            raise Exception("duplicate message")
        if action == "findNotes":
            return [5555]
        if action == "notesInfo":
            if kwargs.get("notes") == [5555]:
                return [{"noteId": 5555, "cards": [6666]}]
            return []
        return None

    adapter._invoke.side_effect = side_effect
    results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    res = results[0]

    assert res.ok is True
    assert res.new_nid == "5555"
    assert res.new_cid == "6666"
