from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from arete.mcp_server import (
    _get_status,
    _sync_file,
    _sync_vault,
    call_tool,
    read_resource,
)


@pytest.mark.asyncio
async def test_call_tool_dispatch():
    with patch("arete.mcp_server._sync_vault", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = [TextContent(type="text", text="Sync OK")]

        result = await call_tool("sync_vault", {"force": True})

        mock_sync.assert_awaited_once_with({"force": True})
        assert result[0].text == "Sync OK"


@pytest.mark.asyncio
async def test_call_tool_unknown():
    result = await call_tool("unknown_tool", {})
    assert "Unknown tool" in result[0].text


@pytest.mark.asyncio
async def test_sync_vault_success():
    with patch("arete.mcp_server.execute_sync", new_callable=AsyncMock) as mock_exec:
        # Mock successful stats
        mock_exec.return_value.total_errors = 0
        mock_exec.return_value.total_imported = 10
        mock_exec.return_value.total_generated = 5

        # Patch resolve_config used inside _sync_vault (top-level import in mcp_server)
        with patch("arete.mcp_server.resolve_config"):
            result = await _sync_vault({"force": True})

            mock_exec.assert_awaited_once()
            assert '"success": true' in result[0].text


@pytest.mark.asyncio
async def test_sync_file_success():
    with patch("arete.mcp_server.execute_sync", new_callable=AsyncMock) as mock_exec:
        with patch("arete.mcp_server.Path") as mock_path:
            # Patch resolve_config used inside _sync_file (top-level import in mcp_server)
            with patch("arete.mcp_server.resolve_config"):
                mock_path.return_value.exists.return_value = True

                mock_exec.return_value.total_errors = 0
                mock_exec.return_value.total_imported = 1

                result = await _sync_file({"file_path": "test.md"})

                mock_exec.assert_awaited_once()
                assert '"success": true' in result[0].text


@pytest.mark.asyncio
async def test_sync_file_missing_arg():
    result = await _sync_file({})
    assert "Error: file_path is required" in result[0].text


@pytest.mark.asyncio
async def test_sync_file_not_found():
    with patch("arete.mcp_server.Path") as mock_path:
        mock_path.return_value.exists.return_value = False
        result = await _sync_file({"file_path": "missing.md"})
        assert "Error: File not found" in result[0].text


@pytest.mark.asyncio
async def test_get_status():
    result = await _get_status()
    assert "arete-mcp" in result[0].text


# Stats logic test removed - covered by StatsService unit tests


@pytest.mark.asyncio
async def test_read_resource_status():
    result = await read_resource("arete://status")
    assert '"status": "running"' in result


@pytest.mark.asyncio
async def test_read_resource_unknown():
    with pytest.raises(ValueError):
        await read_resource("arete://unknown")
