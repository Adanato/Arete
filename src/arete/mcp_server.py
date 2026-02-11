"""Arete MCP Server

Exposes Arete sync capabilities via the Model Context Protocol (MCP),
enabling AI agents (Claude, Gemini, etc.) to interact with Anki flashcard sync.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from arete.application.config import resolve_config
from arete.consts import VERSION
from arete.main import execute_sync

logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = Server("arete")


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="sync_vault",
            description="Sync Obsidian vault to Anki. Returns sync statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "vault_path": {
                        "type": "string",
                        "description": "Path to vault (optional, uses config default)",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force sync all notes, ignoring cache",
                        "default": False,
                    },
                    "prune": {
                        "type": "boolean",
                        "description": "Remove orphaned Anki notes",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="sync_file",
            description="Sync a specific Markdown file to Anki.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the Markdown file to sync",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force sync, ignoring cache",
                        "default": False,
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="get_stats",
            description="Get learning statistics and identify problematic notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "lapse_threshold": {
                        "type": "integer",
                        "description": "Threshold for lapsing cards (leeches)",
                        "default": 3,
                    }
                },
                "required": [],
            },
        ),
    ]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "sync_vault":
            return await _sync_vault(arguments)
        elif name == "sync_file":
            return await _sync_file(arguments)
        elif name == "get_status":
            return await _get_status()
        elif name == "get_stats":
            return await _get_stats(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {e}")]


async def _sync_vault(args: dict[str, Any]) -> list[TextContent]:
    """Execute vault sync."""
    vault_path = args.get("vault_path")
    force = args.get("force", False)
    prune = args.get("prune", False)

    # Resolve config with overrides
    overrides: dict[str, Any] = {}
    if vault_path:
        overrides["vault_root"] = vault_path
    if force:
        overrides["force"] = True
        overrides["clear_cache"] = True
    if prune:
        overrides["prune"] = True

    config = resolve_config(cli_overrides=overrides if overrides else None)

    # Run sync
    stats = await execute_sync(config)

    result = {
        "success": stats.total_errors == 0,
        "total_generated": stats.total_generated,
        "total_imported": stats.total_imported,
        "total_errors": stats.total_errors,
    }

    import json

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _sync_file(args: dict[str, Any]) -> list[TextContent]:
    """Execute single file sync."""
    file_path = args.get("file_path")
    force = args.get("force", False)

    if not file_path:
        return [TextContent(type="text", text="Error: file_path is required")]

    path = Path(file_path)
    if not path.exists():
        return [TextContent(type="text", text=f"Error: File not found: {file_path}")]

    # Resolve config with file path
    overrides: dict[str, Any] = {"root_input": path}
    if force:
        overrides["force"] = True
        overrides["clear_cache"] = True

    config = resolve_config(cli_overrides=overrides)

    # Run sync
    stats = await execute_sync(config)

    result = {
        "success": stats.total_errors == 0,
        "file": str(path),
        "total_imported": stats.total_imported,
        "total_errors": stats.total_errors,
    }

    import json

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_status() -> list[TextContent]:
    """Get server status."""
    import json

    result = {
        "status": "running",
        "version": VERSION,
        "server": "arete-mcp",
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _get_stats(args: dict[str, Any]) -> list[TextContent]:
    """Fetch learning insights from Anki."""
    import dataclasses

    from arete.application.config import resolve_config
    from arete.application.factory import get_anki_bridge
    from arete.application.stats_service import StatsService

    lapse_threshold = args.get("lapse_threshold", 3)

    try:
        config = resolve_config()
        anki = await get_anki_bridge(config)
        service = StatsService(anki)
        insights = await service.get_learning_insights(lapse_threshold=lapse_threshold)

        import json

        return [TextContent(type="text", text=json.dumps(dataclasses.asdict(insights), indent=2))]
    except Exception as e:
        logger.exception("Failed to get stats in MCP")
        return [TextContent(type="text", text=f"Error retrieving stats: {e}")]


@mcp.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    from pydantic import AnyUrl

    return [
        Resource(
            uri=AnyUrl("arete://status"),
            name="Arete Status",
            description="Current Arete server status and version",
            mimeType="application/json",
        ),
    ]


@mcp.read_resource()  # type: ignore
async def read_resource(uri: str) -> str:
    """Read a resource."""
    import json

    if uri == "arete://status" or str(uri) == "arete://status":
        return json.dumps(
            {
                "status": "running",
                "version": VERSION,
            }
        )

    raise ValueError(f"Unknown resource: {uri}")


async def run_server():
    """Run the MCP server using stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options(),
        )


def main():
    """Entry point for MCP server."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
