# Changelog

All notable changes to TIMPS Swarm are documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.2.0] — 2026-06-07

### Highlights
- **Sub-agents now cover all 160 MCP tools** (was 64). Each tool gets a
  native Claude Code / Cursor / Codex sub-agent file (480 `.md` files
  across 3 IDE directories).
- **Node.js MCP proxy** — `npx timps-swarm mcp` works for users who
  installed the npm CLI but haven't cloned the Python repo. The proxy
  forwards `tools/list` and `tools/call` to the FastAPI `/mcp/tools` and
  `/mcp/tools/call` endpoints.
- **YAML frontmatter fix** — 51/160 sub-agent `.md` files had unescaped
  colons in descriptions; descriptions are now properly quoted in
  `cli/lib/agent-files.js:renderAgentFile()`.

### Fixed
- `cli/bin/temps-swarm.js:157` — hardcoded version string bumped to 2.2.0
  ("56 AI agents" → "160 AI agents").
- `mcp_server/server.py:1863-1868` — `serverInfo` version bumped to 2.2.0,
  description updated to "TIMPS Swarm: 160 AI specialists across SDLC,
  computer health, developer workflow, knowledge worker, priority, expert
  diagnostics, context, kernel, and meta categories."
- `pyproject.toml` — version bumped to 2.2.0; description "64+ AI agents"
  → "160 AI agents".
- Generator script (`cli/tools/generate-manifest.js`) now extracts
  `ast.Starred → ast.ListComp` elements from `mcp_server/server.py:TOOLS`,
  capturing all 160 tools (was missing 96 because the original script only
  counted `ast.Dict` literals).
- Renderer (`cli/lib/agent-files.js`) wraps descriptions in double quotes
  and escapes `\`, `"`, `\n` to ensure valid YAML frontmatter.
- `findRepoPython()` priority order now checks `$TIMPS_REPO` first, then
  walks up CWD 6 levels, then `~/timps-swarm`, `~/Desktop/temps-swarm`,
  `/opt/temps-swarm`, then npm global install.
- `pythonBin()` helper probes `python3` first, falls back to `python`.
- `serverDownError(err)` helper detects ECONNREFUSED / fetch failed /
  ENOTFOUND and prints actionable hints.
- Env forwarding in MCP config (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GEMINI_API_KEY`, `GROQ_API_KEY`, `TIMPS_API_URL`, `OLLAMA_HOST`,
  `REDIS_URL`).
- `--repo <path>` flag for all subcommands to override the Python repo
  discovery.
- `uninstall-mcp` command reverses `install-mcp` (480 sub-agent files +
  7 IDE configs).

### Added
- `cli/lib/mcp-proxy.js` — Node.js JSON-RPC 2.0 stdio proxy that forwards
  to `${TIMPS_API_URL:-http://localhost:8000}/mcp/tools[/call]`.
- `cli/lib/local-audit.js` — offline security audit (secrets, deps,
  docker config).
- `cli/lib/agents-manifest.js` regenerated to 160 entries with category
  metadata (priority 68, expert 51, health 12, developer 12, knowledge 7,
  meta 6, kernel 2, sdlc 1, context 1).
- `tests/` directory with smoke tests for the MCP server, CLI manifest,
  Python package version, and sub-agent file consistency.
- `CHANGELOG.md` (this file).
- Git tag `v2.2.0` annotated at the release commit.

### Changed
- `cli/package.json` `2.1.0` → `2.2.0`; description "64+ AI agents" →
  "160 AI agents".
- `cli/README.md` rewritten for v2.2.0 (16 commands, 160-agent catalogue,
  Node.js fallback, env block, `--repo` flag).
- `README.md` updated throughout for the 160-agent count and new install
  flow.
- Sub-agent filenames: `timps-<agentBase>.md` (where
  `agentBase = name.replace(/^timps_/, '')`).

### Removed
- `POST /mcp/install` HTTP endpoint in `src/main.py` — replaced with a
  `410 Gone` stub pointing to `npx timps-swarm install-mcp`. The HTTP
  endpoint only covered 3 IDEs (claude-code, cursor, local-mcp), used a
  hardcoded `command: "python"` (broken on macOS without PATH alias), and
  had no env forwarding. The npm CLI's `install-mcp` covers 7 IDEs with
  proper env forwarding and `python3` / `python` probing.

## [2.1.0] — 2026-05-30
- 8 bug fixes for `install-mcp` / `mcp` after fresh install (see
  `8c398263` for the long-form bug list).
- New `cli/lib/mcp-proxy.js` for Node-only MCP fallback.
- 64 sub-agent `.md` files written (one per MCP tool, across
  Claude/Cursor/Codex dirs).
- Env forwarding for 7 API keys.
- `--repo <path>` flag on all commands.

## [2.0.1] — 2026-05-23
- Bug-fix release of the Python `timps-swarm-mcp` package on PyPI.

## [2.0.0] — 2026-05-21
- Initial public release of the npm `timps-swarm` CLI on the registry.
- 64 MCP tools exposed via stdio JSON-RPC 2.0.
