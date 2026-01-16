from pathlib import Path

import pytest
import respx
from httpx import Response

from arete.domain.models import AnkiNote, WorkItem
from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://127.0.0.1:8765")


@pytest.mark.asyncio
@respx.mock
async def test_get_model_styling_error(adapter):
    respx.post("http://127.0.0.1:8765").mock(
        return_value=Response(200, json={"result": None, "error": "Model not found"})
    )
    # Checks that it doesn't raise exception but returns empty string
    styling = await adapter.get_model_styling("NonExistent")
    assert styling == ""


@pytest.mark.asyncio
@respx.mock
async def test_get_model_templates_error(adapter):
    respx.post("http://127.0.0.1:8765").mock(
        return_value=Response(200, json={"result": None, "error": "Model not found"})
    )
    # Checks that it doesn't raise exception but returns empty dict (or None check implementation)
    # Current implementation usually returns {} or logs error.
    # Let's verify return type.
    templates = await adapter.get_model_templates("NonExistent")
    assert templates == {}


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_add_fail(adapter):
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "Q", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=Path("test.md"),
        source_index=1,
    )
    item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    # Mock sequence: deck (ok), model (ok), findNotes (empty), addNote (error)
    respx.post("http://127.0.0.1:8765").mock(
        side_effect=[
            Response(200, json={"result": None, "error": None}),  # createDeck
            Response(
                200, json={"result": ["Front", "Back", "_obsidian_source"], "error": None}
            ),  # modelFieldNames
            Response(200, json={"result": [], "error": None}),  # findNotes
            Response(200, json={"result": None, "error": "Creation failed"}),  # addNote
        ]
    )

    # Should not raise, but return UpdateItem with error
    updates = await adapter.sync_notes([item])
    assert len(updates) == 1
    assert updates[0].ok is False
    assert "Creation failed" in (updates[0].error or "")
