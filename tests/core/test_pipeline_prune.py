import json
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response

from o2a.core.config import AppConfig
from o2a.core.pipeline import _prune_orphans
from o2a.logging_utils import RunRecorder
from o2a.services.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://mock:8765")


@pytest.fixture
def mock_config(tmp_path):
    # Use model_construct to bypass Pydantic's settings sources (TOML loading)
    return AppConfig.model_construct(
        root_input=tmp_path,
        vault_root=tmp_path,
        anki_media_dir=tmp_path,
        anki_base=None,
        apy_bin="apy",
        log_dir=tmp_path,
        run_apy=False,
        keep_going=True,
        no_move_deck=False,
        dry_run=False,
        workers=1,
        queue_size=10,
        verbose=1,
        show_config=False,
        prune=True,
        force=True,
        clear_cache=False,
        backend="auto",
        anki_connect_url="http://localhost:8765",
        open_logs=False,
        open_config=False,
    )


@pytest.mark.asyncio
@respx.mock
async def test_prune_protects_parents(adapter, mock_config):
    # Vault has: "Math::Algebra::Linear"
    # Anki has: "Math", "Math::Algebra", "Math::Algebra::Linear", "OrphanDeck"

    def side_effect(request):
        data = json.loads(request.content)
        action = data["action"]
        if action == "deckNames":
            return Response(
                200,
                json={
                    "result": ["Math", "Math::Algebra", "Math::Algebra::Linear", "OrphanDeck"],
                    "error": None,
                },
            )
        elif action == "findNotes":
            return Response(200, json={"result": [], "error": None})
        elif action == "deleteDecks":
            return Response(200, json={"result": None, "error": None})
        return Response(200, json={"result": None, "error": None})

    route = respx.post("http://mock:8765").mock(side_effect=side_effect)

    recorder = RunRecorder()
    recorder.add_inventory([{"nid": "1", "deck": "Math::Algebra::Linear"}])

    logger = MagicMock()
    await _prune_orphans(mock_config, recorder, adapter, logger)

    # Verify that deleteDecks was called ONLY for OrphanDeck
    delete_calls = [
        c for c in route.calls if json.loads(c.request.content).get("action") == "deleteDecks"
    ]
    assert len(delete_calls) > 0
    deleted = json.loads(delete_calls[0].request.content)["params"]["decks"]

    assert "OrphanDeck" in deleted
    assert "Math" not in deleted
    assert "Math::Algebra" not in deleted
    assert "Math::Algebra::Linear" not in deleted
