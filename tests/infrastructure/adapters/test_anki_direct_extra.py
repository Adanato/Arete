from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arete.infrastructure.adapters.anki_direct import AnkiDirectAdapter


@pytest.fixture
def adapter():
    return AnkiDirectAdapter(anki_base=Path("/mock/anki"))


@pytest.fixture
def mock_repo():
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        repo_instance = MockRepo.return_value.__enter__.return_value
        repo_instance.col = MagicMock()
        yield repo_instance


@pytest.mark.asyncio
async def test_suspend_cards(adapter, mock_repo):
    mock_repo.col.sched.suspend_cards = MagicMock()
    res = await adapter.suspend_cards([1, 2])
    assert res is True
    mock_repo.col.sched.suspend_cards.assert_called_with([1, 2])


@pytest.mark.asyncio
async def test_unsuspend_cards(adapter, mock_repo):
    mock_repo.col.sched.unsuspend_cards = MagicMock()
    res = await adapter.unsuspend_cards([1, 2])
    assert res is True
    mock_repo.col.sched.unsuspend_cards.assert_called_with([1, 2])


@pytest.mark.asyncio
async def test_get_model_styling(adapter, mock_repo):
    mock_model = {"css": "body { background: #fff; }"}
    mock_repo.col.models.by_name.return_value = mock_model
    res = await adapter.get_model_styling("Basic")
    assert res == "body { background: #fff; }"


@pytest.mark.asyncio
async def test_get_model_templates(adapter, mock_repo):
    mock_model = {
        "tmpls": [
            {"name": "Card 1", "qfmt": "Q1", "afmt": "A1"},
            {"name": "Card 2", "qfmt": "Q2", "afmt": "A2"},
        ]
    }
    mock_repo.col.models.by_name.return_value = mock_model
    res = await adapter.get_model_templates("Basic")
    assert len(res) == 2
    assert res["Card 1"]["Front"] == "Q1"


@pytest.mark.asyncio
async def test_gui_browse_polling(adapter):
    from unittest.mock import AsyncMock

    # Mock subprocess.run for 'open'
    with patch("subprocess.run") as mock_run:
        # Let's mock the whole httpx behavior
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": True, "error": None}

        # Async mock for the client context manager
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with (
            patch(
                "httpx.AsyncClient",
                return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_client)),
            ),
            patch("os.startfile", create=True) as mock_startfile,
        ):
            import sys

            res = await adapter.gui_browse("test query")
            assert res is True
            if sys.platform == "win32":
                mock_startfile.assert_called()
            else:
                mock_run.assert_called()


@pytest.mark.asyncio
async def test_get_learning_insights_empty(adapter, mock_repo):
    mock_repo.col.find_cards.return_value = []
    res = await adapter.get_learning_insights()
    assert res.total_cards == 0
    assert len(res.problematic_notes) == 0


@pytest.mark.asyncio
async def test_get_card_stats_missing_nid(adapter, mock_repo):
    mock_repo.col.find_cards.side_effect = Exception("Card fail")
    res = await adapter.get_card_stats([999])
    assert res == []
