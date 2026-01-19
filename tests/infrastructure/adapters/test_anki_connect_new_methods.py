import pytest
import respx
from httpx import Response

from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://mock-anki:8765")


@pytest.mark.asyncio
@respx.mock
async def test_get_due_cards(adapter):
    respx.post("http://mock-anki:8765").mock(
        return_value=Response(200, json={"result": [1, 2, 3], "error": None})
    )

    nids = await adapter.get_due_cards()
    assert nids == [1, 2, 3]

    # Check query with deck
    respx.post("http://mock-anki:8765").mock(
        return_value=Response(200, json={"result": [1], "error": None})
    )
    nids = await adapter.get_due_cards(deck_name="Test")
    assert nids == [1]


@pytest.mark.asyncio
@respx.mock
async def test_get_due_cards_error(adapter):
    respx.post("http://mock-anki:8765").mock(
        return_value=Response(200, json={"result": None, "error": "Anki error"})
    )
    nids = await adapter.get_due_cards()
    assert nids == []


@pytest.mark.asyncio
@respx.mock
async def test_map_nids_to_arete_ids(adapter):
    respx.post("http://mock-anki:8765").mock(
        return_value=Response(
            200,
            json={
                "result": [
                    {"tags": ["arete_123", "other"]},
                    {"tags": ["other"]},
                    {"tags": ["arete_456"]},
                ],
                "error": None,
            },
        )
    )

    arete_ids = await adapter.map_nids_to_arete_ids([1, 2, 3])
    assert arete_ids == ["arete_123", "arete_456"]


@pytest.mark.asyncio
@respx.mock
async def test_map_nids_to_arete_ids_empty(adapter):
    arete_ids = await adapter.map_nids_to_arete_ids([])
    assert arete_ids == []


@pytest.mark.asyncio
@respx.mock
async def test_map_nids_to_arete_ids_error(adapter):
    respx.post("http://mock-anki:8765").mock(
        return_value=Response(200, json={"result": None, "error": "Anki error"})
    )
    arete_ids = await adapter.map_nids_to_arete_ids([1])
    assert arete_ids == []
