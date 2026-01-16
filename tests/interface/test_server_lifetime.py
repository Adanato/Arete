from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from arete.server import app, lifespan

client = TestClient(app)


@pytest.mark.asyncio
async def test_lifespan():
    app_mock = MagicMock()
    async with lifespan(app_mock):
        pass


@patch("os.kill")
@patch("time.sleep")
def test_shutdown_endpoint(mock_sleep, mock_kill):
    with patch("threading.Thread") as mock_thread:
        mock_thread.side_effect = lambda target: MagicMock(start=lambda: target())
        # The shutdown endpoint is tested via test_shutdown_api below
        pass


def test_shutdown_api():
    with patch("threading.Thread") as mock_thread:
        response = client.post("/shutdown")
        assert response.status_code == 200
        mock_thread.return_value.start.assert_called_once()
