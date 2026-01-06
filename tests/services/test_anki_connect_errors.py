
import json
import os
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from arete.domain.types import AnkiNote, WorkItem
from arete.services.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://mock-anki:8765")


@pytest.fixture
def sample_note():
    return AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "Front", "Back": "Back"},
        tags=["tag1"],
        start_line=1,
        end_line=10,
        source_file=Path("test.md"),
        source_index=1,
    )


def test_env_host_override():
    with patch.dict(os.environ, {"ANKI_CONNECT_HOST": "1.2.3.4"}):
        ac = AnkiConnectAdapter()
        assert ac.url == "http://1.2.3.4:8765"


@pytest.mark.asyncio
@respx.mock
async def test_is_responsive_failure(adapter):
    respx.post("http://mock-anki:8765").mock(side_effect=Exception("Connection refused"))
    assert await adapter.is_responsive() is False


@pytest.mark.asyncio
@respx.mock
async def test_ensure_deck_failure(adapter):
    respx.post("http://mock-anki:8765").mock(
        return_value=Response(200, json={"result": None, "error": "Something bad"})
    )
    result = await adapter.ensure_deck("NewDeck")
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_healing_failure(adapter, sample_note):
    """
    Simulate "addNote" failing with "duplicate".
    Then "findNotes" returns empty list (healing fails).
    """

    def side_effect(request):
        data = json.loads(request.content)
        action = data["action"]
        if action == "createDeck":
            return Response(200, json={"result": 1, "error": None})
        if action == "addNote":
            return Response(200, json={"result": None, "error": "cannot create note because it is a duplicate"})
        if action == "findNotes":
            # Return empty list -> healing fails
            return Response(200, json={"result": [], "error": None})
        return Response(200, json={"result": None, "error": None})

    respx.post("http://mock-anki:8765").mock(side_effect=side_effect)

    item = WorkItem(note=sample_note, source_file=Path("test.md"), source_index=1)
    results = await adapter.sync_notes([item])

    assert len(results) == 1
    assert results[0].ok is False
    assert "duplicate" in results[0].error


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_healing_success(adapter, sample_note):
    """
    Simulate "addNote" failing with "duplicate".
    Then "findNotes" returns a valid ID (healing success).
    """

    def side_effect(request):
        data = json.loads(request.content)
        action = data["action"]
        if action == "createDeck":
            return Response(200, json={"result": 1, "error": None})
        if action == "addNote":
            return Response(200, json={"result": None, "error": "cannot create note because it is a duplicate"})
        if action == "findNotes":
            # Return valid ID -> healing works
            return Response(200, json={"result": [123999], "error": None})
        if action == "notesInfo":
            return Response(200, json={"result": [{"cards": [999]}], "error": None})
        return Response(200, json={"result": None, "error": None})

    respx.post("http://mock-anki:8765").mock(side_effect=side_effect)

    item = WorkItem(note=sample_note, source_file=Path("test.md"), source_index=1)
    results = await adapter.sync_notes([item])

    assert len(results) == 1
    assert results[0].ok is True
    assert results[0].new_nid == "123999"


@pytest.mark.asyncio
@respx.mock
async def test_sync_notes_cid_failure(adapter, sample_note):
    """
    Simulate addNote success, but notesInfo (CID fetch) fails/returns empty.
    """
    def side_effect(request):
        data = json.loads(request.content)
        action = data["action"]
        if action == "createDeck":
            return Response(200, json={"result": 1, "error": None})
        if action == "addNote":
            return Response(200, json={"result": 123456, "error": None})
        if action == "notesInfo":
            # Simulate failure to get cards
            return Response(200, json={"result": [{"cards": []}], "error": None})
        return Response(200, json={"result": None, "error": None})

    respx.post("http://mock-anki:8765").mock(side_effect=side_effect)

    item = WorkItem(note=sample_note, source_file=Path("test.md"), source_index=1)
    results = await adapter.sync_notes([item])

    assert results[0].ok
    assert results[0].new_nid == "123456"
    assert results[0].new_cid is None


@pytest.mark.asyncio
async def test_invoke_windows_curl_failure():
    """
    Test the WSL curl execution path.
    1. Force use_windows_curl = True
    2. Mock subprocess to return error.
    """
    import asyncio

    # Create adapter, force flag
    ac = AnkiConnectAdapter()
    ac.use_windows_curl = True
    ac.url = "http://127.0.0.1:8765"

    # Mock subprocess.create_subprocess_exec
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        process_mock = MagicMock()
        process_mock.communicate = MagicMock(return_value=asyncio.Future())
        process_mock.communicate.return_value.set_result((b"{}", b"curl not found"))
        process_mock.returncode = 1  # Fail

        mock_exec.return_value = process_mock

        with pytest.raises(Exception) as exc:
            await ac._invoke("version")

        assert "curl.exe failed" in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_invoke_invalid_response(adapter):
    # Case 1: missing all fields (rare but possible w/ bad proxy)
    respx.post("http://mock-anki:8765").mock(return_value=Response(200, json={}))
    with pytest.raises(ValueError, match="unexpected number of fields"):
        await adapter._invoke("version")

    # Case 2: missing error
    respx.post("http://mock-anki:8765").mock(return_value=Response(200, json={"result": 1, "foo": "bar"}))
    with pytest.raises(ValueError, match="missing required error field"):
        await adapter._invoke("version")

    # Case 3: missing result
    respx.post("http://mock-anki:8765").mock(return_value=Response(200, json={"error": None, "foo": "bar"}))
    with pytest.raises(ValueError, match="missing required result field"):
        await adapter._invoke("version")


@pytest.mark.asyncio
@respx.mock
async def test_get_notes_in_deck_html_strip(adapter):
    """
    Verify that <p>123</p> is stripped to 123 for NID.
    """
    respx.post("http://mock-anki:8765").mock(side_effect=[
        # findNotes
        Response(200, json={"result": [100], "error": None}),
        # notesInfo
        Response(200, json={"result": [
             {"noteId": 100, "fields": {"nid": {"value": "<p> 999 </p>"}}}
        ], "error": None})
    ])

    mapping = await adapter.get_notes_in_deck("test_deck")
    # Should get "999" mapped to 100
    assert "999" in mapping
    assert mapping["999"] == 100


@pytest.mark.asyncio
@respx.mock
async def test_get_notes_in_deck_empty(adapter):
    # findNotes returns []
    respx.post("http://mock-anki:8765").mock(return_value=Response(200, json={"result": [], "error": None}))
    mapping = await adapter.get_notes_in_deck("empty_deck")
    assert mapping == {}


@pytest.mark.asyncio
async def test_wsl_detection_resolv_conf():
    # Mock platform and shutil.which to simulate WSL with no curl.exe
    with patch("platform.uname") as mock_uname:
        mock_uname.return_value.release = "microsoft-standard-WSL2"
        with patch("shutil.which", return_value=None):
            # Mock open for /etc/resolv.conf
            with patch("builtins.open", unittest.mock.mock_open(read_data="nameserver 172.16.0.1\n")):
                 ac = AnkiConnectAdapter(url="http://localhost:8765")
                 assert ac.url == "http://172.16.0.1:8765"


@pytest.mark.asyncio
async def test_wsl_detection_curl_found():
    # Mock platform and shutil.which to simulate WSL WITH curl.exe
    with patch("platform.uname") as mock_uname:
        mock_uname.return_value.release = "microsoft-standard-WSL2"
        with patch("shutil.which", return_value="/mnt/c/Windows/System32/curl.exe"):
             ac = AnkiConnectAdapter(url="http://localhost:8765")
             assert ac.use_windows_curl is True
             assert ac.url == "http://127.0.0.1:8765"
