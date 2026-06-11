"""
TIMPS Swarm MCP Server

Exposes all agents as MCP tools so any MCP-compatible IDE/CLI
(Claude Code, GitHub Copilot, Cursor, Windsurf, Kimi Code, etc.)
can invoke them with a single tool call.

Install:
    pip install timps-swarm-mcp

Run standalone:
    python -m mcp_server.server

Or with the CLI shortcut:
    timps-mcp
"""

__version__ = "1.0.0"
__all__ = ["server"]
