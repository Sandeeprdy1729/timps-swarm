#!/usr/bin/env bash
# TIMPS Swarm — streamable-HTTP MCP server launcher.
# Serves all 161 tools over the MCP streamable-HTTP transport for
# remote-capable clients (opencode type: "remote").
#
# Usage:
#   scripts/serve-mcp-http.sh              # foreground, port 8123
#   PORT=9000 scripts/serve-mcp-http.sh    # custom port
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8123}"
HOST="${HOST:-127.0.0.1}"

PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3}"

cd "$REPO_DIR"

if ! "$PYTHON_BIN" -c "import mcp_server.http_server" 2>/dev/null; then
  echo "[timps-mcp-http] repo-python fallback required; using python3 from PATH" >&2
  PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" -m mcp_server.http_server
