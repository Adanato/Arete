from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter


@pytest.mark.asyncio
async def test_curl_bridge_active():
    """Verify that we use curl.exe when available on WSL."""

    mock_uname = "Linux 5.10.16.3-microsoft-standard-WSL2"

    with (
        patch("platform.uname") as mock_platform,
        patch("shutil.which") as mock_which,
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_platform.return_value.release = mock_uname
        mock_which.side_effect = (
            lambda cmd: "/mnt/c/Windows/System32/curl.exe" if cmd == "curl.exe" else None
        )

        # Mock subprocess output
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b'{"result": 6, "error": null}', b""))
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        adapter = AnkiConnectAdapter(url="http://localhost:8765")

        assert adapter.use_windows_curl is True
        assert adapter.url == "http://127.0.0.1:8765"  # Should normalize to IP

        # Test invocation
        res = await adapter._invoke("version")
        assert res == 6

        # Verify call args
        mock_exec.assert_called()
        cmd = mock_exec.call_args[0]
        assert cmd[0] == "curl.exe"
        assert cmd[4] == "http://127.0.0.1:8765"


@pytest.mark.asyncio
async def test_curl_bridge_fallback():
    """Verify fallback to standard logic if curl.exe is missing."""

    mock_uname = "Linux 5.10.16.3-microsoft-standard-WSL2"

    with (
        patch("platform.uname") as mock_platform,
        patch("shutil.which") as mock_which,
        patch("builtins.open"),
    ):  # Mock open for IP detection fallback
        mock_platform.return_value.release = mock_uname
        mock_which.return_value = None  # curl.exe not found

        adapter = AnkiConnectAdapter(url="http://localhost:8765")

        assert adapter.use_windows_curl is False
