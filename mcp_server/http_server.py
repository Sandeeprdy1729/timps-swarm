"""Streamable-HTTP MCP server for TIMPS Swarm.

Wraps the existing 161-tool stdio servers (`mcp_server/server.py` TOOLS /
_TOOL_HANDLERS) behind the official MCP streamable-HTTP transport, so clients
that only support *remote* MCP servers (e.g. opencode `type: "remote"`) can
reach every tool without spawning a stdio child process per session.

Run:
    python3 -m mcp_server.http_server            # default http://0.0.0.0:8123/mcp
    PORT=9000 python3 -m mcp_server.http_server

Client config (opencode):
    "mcp": { "timps-swarm": { "type": "remote", "url": "http://localhost:8123/mcp" } }
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

import contextlib

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from mcp.server.streamable_http_manager import (
    StreamableHTTPSessionManager,
)
from mcp.server.lowlevel.server import Server as MCPServer
from mcp.types import TextContent, Tool

# ── Allow running from repo root without installing ──────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [timps-http] %(message)s",
)
logger = logging.getLogger("timps-http")

# Reuse the 161-tool catalogue and the synchronous tool handlers from the
# stdio server. Importing this module registers observer/auto-spawner wiring.
from mcp_server.server import TOOLS, _TOOL_HANDLERS  # noqa: E402


def _build_tools() -> List[Tool]:
    """Convert the TOOLS dict catalogue into mcp.types.Tool objects."""
    tools: List[Tool] = []
    for t in TOOLS:
        tools.append(
            Tool(
                name=t["name"],
                description=t.get("description") or "",
                inputSchema=t.get("inputSchema") or {"type": "object", "properties": {}},
            )
        )
    return tools


def _invoke_handler(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Run the existing synchronous agent handler to string output."""
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    return handler(arguments)


def build_mcp_app() -> Starlette:
    """Assemble the Starlette ASGI app exposing all TIMPS tools over streamable HTTP."""
    server = MCPServer(name="timps-swarm", version="2.2.3")
    manager = StreamableHTTPSessionManager(app=server)

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return _build_tools()

    @server.call_tool()
    async def call_tool(
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> List[TextContent]:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _invoke_handler, tool_name, arguments or {})
        return [TextContent(type="text", text=text)]

    async def mcp_asgi(scope, receive, send):
        await manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(starlette_app):
        async with manager.run():
            yield

    starlette = Starlette(
        lifespan=lifespan,
        routes=[
            Mount("/mcp", app=mcp_asgi),
            Mount("/", app=mcp_asgi),
        ],
    )
    return starlette


def main() -> None:
    port = int(os.getenv("PORT", "8123"))
    host = os.getenv("HOST", "0.0.0.0")
    app = build_mcp_app()
    logger.info("TIMPS Swarm MCP (streamable HTTP) listening on %s:%s/mcp", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
