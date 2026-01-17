from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from arete.application.pipeline import WorkItem
from arete.domain.models import AnkiNote
from arete.infrastructure.adapters.anki_direct import AnkiDirectAdapter


@pytest.fixture
def adapter():
    return AnkiDirectAdapter(anki_base=Path("/tmp/anki"))


@pytest.mark.asyncio
async def test_get_model_names_empty(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = None
        res = await adapter.get_model_names()
        assert res == []


@pytest.mark.asyncio
async def test_ensure_deck_fail(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = None
        res = await adapter.ensure_deck("Default")
        assert res is False


@pytest.mark.asyncio
async def test_sync_notes_db_failure(adapter):
    with patch(
        "arete.infrastructure.adapters.anki_direct.AnkiRepository", side_effect=Exception("DB Lock")
    ):
        items = [WorkItem(source_file=Path("f.md"), source_index=1, note=MagicMock())]
        results = await adapter.sync_notes(items)
        assert len(results) == 1
        assert results[0].ok is False
        assert "DB Error" in results[0].error


@pytest.mark.asyncio
async def test_sync_notes_update_fail_then_add(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.update_note.side_effect = Exception("Update Failed")
        instance.add_note.return_value = 12345

        note = AnkiNote(
            model="B",
            deck="D",
            fields={},
            nid="1",
            tags=[],
            start_line=1,
            end_line=1,
            source_file=Path("f.md"),
            source_index=1,
        )
        items = [WorkItem(source_file=Path("f.md"), source_index=1, note=note)]
        results = await adapter.sync_notes(items)
        # Note: If update fails, it checks if success is False and error_msg is None.
        # But if update fails, it sets error_msg = str(e).
        # So it won't try add.
        assert results[0].ok is False
        assert results[0].error == "Update Failed"


@pytest.mark.asyncio
async def test_get_deck_names_empty(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = None
        res = await adapter.get_deck_names()
        assert res == []


@pytest.mark.asyncio
async def test_suspend_cards_error(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = MagicMock()
        instance.col.sched.suspend_cards.side_effect = Exception("Sched Error")
        res = await adapter.suspend_cards([1, 2])
        assert res is False


@pytest.mark.asyncio
async def test_gui_browse_timeout(adapter):
    # Mock platform and ankiconnect polling
    with patch("sys.platform", "linux"):
        with patch("subprocess.Popen") as mock_popen:
            # _try_ankiconnect always False
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post.side_effect = Exception(
                    "No AnkiConnect"
                )
                with patch("asyncio.sleep", AsyncMock()):  # Speed up test
                    res = await adapter.gui_browse("query")
                    assert res is False
                    mock_popen.assert_called()


@pytest.mark.asyncio
async def test_get_learning_insights_fail(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = None
        res = await adapter.get_learning_insights()
        assert res.total_cards == 0


@pytest.mark.asyncio
async def test_get_model_styling_missing(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = MagicMock()
        instance.col.models.by_name.return_value = None
        res = await adapter.get_model_styling("NonExistent")
        assert res == ""


@pytest.mark.asyncio
async def test_get_model_templates_missing(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = MagicMock()
        instance.col.models.by_name.return_value = None
        res = await adapter.get_model_templates("NonExistent")
        assert res == {}


@pytest.mark.asyncio
async def test_gui_browse_macos(adapter):
    with patch("sys.platform", "darwin"):
        with patch("subprocess.run") as mock_run:
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client_cls.return_value.__aenter__.return_value = mock_client
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"result": True, "error": None}
                mock_client.post.return_value = mock_resp

                with patch("asyncio.sleep", AsyncMock()):
                    res = await adapter.gui_browse("query")
                    assert res is True
                    mock_run.assert_called_with(
                        ["open", "-a", "Anki"], stdout=ANY, stderr=ANY
                    )


@pytest.mark.asyncio
async def test_gui_browse_windows(adapter):
    with patch("sys.platform", "win32"):
        # Mock Popen for success path
        with patch("subprocess.Popen") as mock_popen:
            with patch("os.path.exists", return_value=False): # Default fail path search
                # But if we mock subprocess.Popen to NOT raise, it simulates 'anki' command found
                # Or we can test fallback.
                # Let's test PATH success first (first try block)
                with patch("httpx.AsyncClient") as mock_client_cls:
                    mock_client = AsyncMock()
                    mock_client_cls.return_value.__aenter__.return_value = mock_client
                    mock_resp = MagicMock()
                    mock_resp.status_code = 200
                    mock_resp.json.return_value = {"result": True, "error": None}
                    mock_client.post.return_value = mock_resp

                    with patch("asyncio.sleep", AsyncMock()):
                        res = await adapter.gui_browse("query")
                        assert res is True
                        # Should call Popen(["anki"], ...)
                        mock_popen.assert_called()


@pytest.mark.asyncio
async def test_get_card_stats_exceptions(adapter):
    with patch("arete.infrastructure.adapters.anki_direct.AnkiRepository") as MockRepo:
        instance = MockRepo.return_value.__enter__.return_value
        instance.col = MagicMock()
        instance.col.get_card.side_effect = Exception("Card missing")
        res = await adapter.get_card_stats([1])
        assert res == []
