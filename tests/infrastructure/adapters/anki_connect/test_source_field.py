from pathlib import Path

import pytest
import respx
from httpx import Response

from arete.domain.models import AnkiNote, WorkItem
from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://mock-anki:8765")


@pytest.mark.asyncio
@respx.mock
async def test_ensure_model_has_source_field_adds_missing(adapter):
    # Mock modelFieldNames to return fields WITHOUT _obsidian_source
    # Mock modelFieldAdd to return success
    respx.post("http://mock-anki:8765").mock(
        side_effect=[
            Response(200, json={"result": ["Front", "Back"], "error": None}),  # modelFieldNames
            Response(200, json={"result": None, "error": None}),  # modelFieldAdd
        ]
    )

    success = await adapter.ensure_model_has_source_field("Basic")
    assert success is True
    assert len(respx.calls) == 2

    # Check if cache works - second call should not hit API
    success_cache = await adapter.ensure_model_has_source_field("Basic")
    assert success_cache is True
    assert len(respx.calls) == 2


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_calls_ensure_model(adapter):
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "Q", "Back": "A", "_obsidian_source": "v|p|1"},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=Path("test.md"),
        source_index=1,
    )
    item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    # Mock sequence:
    # 1. createDeck (ensure_deck)
    # 2. modelFieldNames (ensure_model_has_source_field)
    # 3. addNote (sync_notes)
    # 4. notesInfo (sync_notes cards check - for CID)
    respx.post("http://mock-anki:8765").mock(
        side_effect=[
            Response(200, json={"result": None, "error": None}),  # 1. createDeck
            Response(
                200, json={"result": ["Front", "Back", "_obsidian_source"], "error": None}
            ),  # 2. modelFieldNames
            Response(200, json={"result": 123, "error": None}),  # 3. addNote
            Response(
                200, json={"result": [{"noteId": 123, "cards": [456]}], "error": None}
            ),  # 4. notesInfo
        ]
    )

    results = await adapter.sync_notes([item])
    assert results[0].ok is True
    assert len(respx.calls) == 4
    assert "addNote" in respx.calls[2].request.content.decode()
    assert results[0].new_cid == "456"
