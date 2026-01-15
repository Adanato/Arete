from pathlib import Path

import pytest
import respx
from httpx import Response

from arete.domain.models import AnkiNote, WorkItem
from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://mock-anki:8765")


@pytest.fixture
def sample_note():
    return AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": r"**bold** and math \(\frac{1}{2}\)", "Back": "A"},
        tags=["tag1"],
        start_line=1,
        end_line=10,
        source_file=Path("test.md"),
        source_index=1,
    )


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_create_new(adapter, sample_note):
    # Setup mock for addNote
    def side_effect(request):
        import json

        data = json.loads(request.content)
        action = data["action"]
        if action == "addNote":
            return Response(200, json={"result": 123456, "error": None})
        if action == "notesInfo":
            return Response(
                200, json={"result": [{"noteId": 123456, "cards": [23456]}], "error": None}
            )
        return Response(200, json={"result": None, "error": None})

    route = respx.post("http://mock-anki:8765").mock(side_effect=side_effect)

    item = WorkItem(note=sample_note, source_file=Path("test.md"), source_index=1)

    results = await adapter.sync_notes([item])

    assert len(results) == 1
    res = results[0]
    assert res.ok
    assert res.new_nid == "123456"

    assert route.called
    # Extract the addNote call
    add_note_call = None
    for call in route.calls:
        import json

        payload = json.loads(call.request.content)
        if payload.get("action") == "addNote":
            add_note_call = payload
            break

    assert add_note_call is not None
    data = add_note_call

    # 1. Bold works (HTML)
    # The adapter receives PRE-RENDERED HTML from the parser.
    # So we expect the mocked parser to have sent HTML.
    # WAIT: This test constructs 'sample_note' manually with RAW fields in the fixture.
    # In the REAL pipeline, parser converts it.
    # In this UNIT TEST, we pass raw fields.
    # If the adapter NO LONGER converts, then the output params will match input fields exactly.

    assert "**bold**" in data["params"]["note"]["fields"]["Front"]
    assert r"\(\frac{1}{2}\)" in data["params"]["note"]["fields"]["Front"]

    # NOTE: In v1.3.1, the Adapter is NOT responsible for conversion.
    # So passing "**bold**" means it sends "**bold**".
    # This verifies the Adapter is a dumb passthrough.


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_update_existing(adapter, sample_note):
    sample_note.nid = "999"

    def side_effect(request):
        import json

        data = json.loads(request.content)
        action = data["action"]
        if action == "notesInfo":
            return Response(200, json={"result": [{"noteId": 999}], "error": None})
        elif action == "updateNoteFields" or action == "createDeck":
            return Response(200, json={"result": None, "error": None})
        elif action == "changeDeck":
            return Response(200, json={"result": None, "error": None})
        return Response(200, json={"result": None, "error": "Unknown action"})

    respx.post("http://mock-anki:8765").mock(side_effect=side_effect)

    item = WorkItem(note=sample_note, source_file=Path("test.md"), source_index=1)
    results = await adapter.sync_notes([item])

    assert len(results) == 1
    res = results[0]
    assert res.ok
    assert res.new_nid == "999"


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_nid_not_found(adapter, sample_note):
    sample_note.nid = "888"  # Dead ID

    def side_effect(request):
        import json

        data = json.loads(request.content)
        action = data["action"]
        if action == "createDeck":
            return Response(200, json={"result": None, "error": None})
        elif action == "notesInfo":
            return Response(200, json={"result": [{}], "error": None})
        elif action == "addNote":
            return Response(200, json={"result": 555, "error": None})
        return Response(200, json={"result": None, "error": f"Unexpected {action}"})

    respx.post("http://mock-anki:8765").mock(side_effect=side_effect)

    item = WorkItem(note=sample_note, source_file=Path("test.md"), source_index=1)
    results = await adapter.sync_notes([item])

    assert len(results) == 1
    res = results[0]
    assert res.ok
    assert res.new_nid == "555"  # Re-created
