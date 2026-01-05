from unittest.mock import mock_open, patch

from arete.services.anki_connect import AnkiConnectAdapter


def test_wsl_detection_active():
    """Verify that we replace localhost with nameserver IP when on WSL."""

    mock_uname = "Linux 5.10.16.3-microsoft-standard-WSL2"
    mock_resolv = "nameserver 172.17.0.1\n"

    with patch("platform.uname") as mock_platform:
        mock_platform.return_value.release = mock_uname

        with patch("shutil.which", return_value=None):
            with patch("builtins.open", mock_open(read_data=mock_resolv)):
                adapter = AnkiConnectAdapter(url="http://localhost:8765")

            # Should have replaced localhost with 172.17.0.1
            assert adapter.url == "http://172.17.0.1:8765"


def test_wsl_detection_non_wsl():
    """Verify no change if not on WSL."""

    mock_uname = "Darwin 21.6.0"

    with patch("platform.uname") as mock_platform:
        mock_platform.return_value.release = mock_uname

        # open shouldn't even be called, but safe to mock just in case
        with patch("builtins.open", mock_open(read_data="")) as m_open:
            adapter = AnkiConnectAdapter(url="http://localhost:8765")

            assert adapter.url == "http://localhost:8765"
            m_open.assert_not_called()


def test_wsl_detection_failed_read():
    """Verify safeguard if /etc/resolv.conf is unreadable or malformed."""

    mock_uname = "Linux 5.10.16.3-microsoft-standard-WSL2"

    with patch("platform.uname") as mock_platform:
        mock_platform.return_value.release = mock_uname

        # Mock open raising exception
        with patch("builtins.open", side_effect=OSError("Read error")):
            adapter = AnkiConnectAdapter(url="http://localhost:8765")

            # Should fall back to original
            # Note: On Windows/WSL, httpx or other logic might normalize localhost to 127.0.0.1
            assert adapter.url in ("http://localhost:8765", "http://127.0.0.1:8765")
