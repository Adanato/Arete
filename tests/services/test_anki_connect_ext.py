from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from arete.domain.types import AnkiNote, WorkItem
from arete.services.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter("http://localhost:8765")


@pytest.mark.asyncio
@respx.mock
async def test_anki_connect_update_existing_with_tags_and_move(adapter):
    with patch.object(adapter, "ensure_deck", return_value=True):
        # Calls:
        # 1. notesInfo (existence check)
        # 2. updateNoteFields
        # 3. addTags
        # 4. removeTags
        # 5. notesInfo (for cards move check)
        # 6. changeDeck
        respx.post("http://localhost:8765").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "result": [{"noteId": 123, "tags": ["old"], "cards": [456]}],
                        "error": None,
                    },
                ),
                httpx.Response(200, json={"result": None, "error": None}),
                httpx.Response(200, json={"result": None, "error": None}),  # addTags
                httpx.Response(200, json={"result": None, "error": None}),  # removeTags
                httpx.Response(
                    200, json={"result": [{"cards": [456]}], "error": None}
                ),  # cards move check
                httpx.Response(200, json={"result": None, "error": None}),  # changeDeck
            ]
        )

        note = AnkiNote(
            model="Basic",
            deck="NewDeck",
            fields={"Front": "val"},
            tags=["new"],
            start_line=1,
            end_line=2,
            source_file=Path("test.md"),
            source_index=0,
            nid="123",
        )
        item = WorkItem(note=note, source_file=Path("test.md"), source_index=0)

        res = await adapter.sync_notes([item])
        assert res[0].ok is True
        assert res[0].new_nid == "123"


@pytest.mark.asyncio
@respx.mock
async def test_anki_connect_notes_info_missing_cards(adapter):
    with patch.object(adapter, "ensure_deck", return_value=True):
        respx.post("http://localhost:8765").mock(
            side_effect=[
                httpx.Response(
                    200, json={"result": [{"noteId": 123, "tags": [], "cards": []}], "error": None}
                ),
                httpx.Response(200, json={"result": None, "error": None}),  # updateNoteFields
                httpx.Response(
                    200, json={"result": [{"something_else": 1}], "error": None}
                ),  # cards move check (info missing cards)
            ]
        )

        note = AnkiNote(
            model="Basic",
            deck="NewDeck",
            fields={"Front": "val"},
            tags=[],
            start_line=1,
            end_line=2,
            source_file=Path("test.md"),
            source_index=0,
            nid="123",
        )
        item = WorkItem(note=note, source_file=Path("test.md"), source_index=0)

        res = await adapter.sync_notes([item])
        assert res[0].ok is True


@pytest.mark.asyncio
@respx.mock
async def test_anki_connect_invoke_connection_error(adapter):
    # Mock httpx to raise ConnectError
    respx.post("http://localhost:8765").mock(side_effect=httpx.ConnectError("Connection refused"))

    with pytest.raises(Exception) as excinfo:
        await adapter.get_deck_names()
    assert "Connection refused" in str(excinfo.value)
