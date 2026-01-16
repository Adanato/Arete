from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter()


@pytest.mark.asyncio
async def test_is_responsive(adapter):
    with patch("httpx.AsyncClient") as mock_client_cls:
        # Mock the context manager return value
        mock_instance = mock_client_cls.return_value
        mock_client = AsyncMock()
        mock_instance.__aenter__.return_value = mock_client

        # Configure post response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": 6}

        # post is an async method
        mock_client.post.return_value = mock_resp

        assert await adapter.is_responsive() is True


@pytest.mark.asyncio
async def test_is_responsive_fail(adapter):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_client = AsyncMock()
        mock_instance.__aenter__.return_value = mock_client

        mock_client.post.side_effect = Exception("Conn Error")

        assert await adapter.is_responsive() is False


@pytest.mark.asyncio
async def test_get_model_names(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = ["Basic", "Cloze"]
        names = await adapter.get_model_names()
        assert "Basic" in names
        mock_invoke.assert_called_with("modelNames")


@pytest.mark.asyncio
async def test_ensure_deck_new(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        res = await adapter.ensure_deck("New Deck")
        assert res is True
        mock_invoke.assert_called_with("createDeck", deck="New Deck")
        assert "New Deck" in adapter._known_decks


@pytest.mark.asyncio
async def test_ensure_deck_cached(adapter):
    adapter._known_decks.add("Cached Deck")
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        res = await adapter.ensure_deck("Cached Deck")
        assert res is True
        mock_invoke.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_model_has_source_field_existing(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = ["Front", "Back", "_obsidian_source"]

        res = await adapter.ensure_model_has_source_field("Basic")
        assert res is True
        # Should verify modelFieldAdd NOT called
        # mock_invoke called with modelFieldNames
        assert mock_invoke.call_count == 1
        assert mock_invoke.call_args[0][0] == "modelFieldNames"


@pytest.mark.asyncio
async def test_ensure_model_has_source_field_add(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        # First call returns fields without source, second call adds it
        mock_invoke.side_effect = [
            ["Front", "Back"],  # modelFieldNames
            None,  # modelFieldAdd result
        ]

        res = await adapter.ensure_model_has_source_field("Basic")
        assert res is True
        assert mock_invoke.call_count == 2
        assert mock_invoke.call_args_list[1][0][0] == "modelFieldAdd"


@pytest.mark.asyncio
async def test_get_model_styling(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = {"css": "body {}"}
        css = await adapter.get_model_styling("Basic")
        assert css == "body {}"


@pytest.mark.asyncio
async def test_get_model_templates(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = {"Default": {"qfmt": "Q", "afmt": "A"}}
        temps = await adapter.get_model_templates("Basic")
        assert "Default" in temps


@pytest.mark.asyncio
async def test_gui_browse(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = [123]  # guiBrowse returns selection?
        res = await adapter.gui_browse("nid:1")
        assert res is True


@pytest.mark.asyncio
async def test_get_card_stats_error(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.side_effect = Exception("Invoke Fail")
        res = await adapter.get_card_stats([123])
        assert res == []


@pytest.mark.asyncio
async def test_suspend_cards_fail(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.side_effect = Exception("Fail")
        with pytest.raises(Exception, match="Fail"):
            await adapter.suspend_cards([123])


@pytest.mark.asyncio
async def test_get_model_styling_error(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.side_effect = Exception("Fail")
        res = await adapter.get_model_styling("Basic")
        assert res == ""


@pytest.mark.asyncio
async def test_get_model_templates_error(adapter):
    with patch.object(adapter, "_invoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.side_effect = Exception("Fail")
        res = await adapter.get_model_templates("Basic")
        assert res == {}


@pytest.mark.asyncio
async def test_invoke_error_handling(adapter):
    with patch("httpx.AsyncClient") as mock_client_cls:
        # Mocking the client instance that is created in _invoke
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.post.side_effect = Exception("Network Error")

        with pytest.raises(Exception, match="Network Error"):
            await adapter._invoke("version")
