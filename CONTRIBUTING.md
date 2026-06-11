# Contributing to TIMPS Swarm

## Quick Start

1. Fork the repo
2. `git clone` your fork
3. `pip install -e ".[dev]"`
4. `python3 -m src.main` to start the API

## Code Style

- Python: `ruff check .` (line-length 100, target py310, configured in `pyproject.toml`)
- JavaScript (cli/): ESM (no CommonJS)
- Commits: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`)

## Adding a New Agent

1. Add your tool definition to `mcp_server/server.py:TOOLS`
2. Add the handler to `_TOOL_HANDLERS`
3. Regenerate the manifest: `node cli/tools/generate-manifest.js`
4. Run `ruff check .` before committing
5. Update the agent count in README.md if it changes

## PR Process

- PRs against `main` only
- Include a description of what changed and why
- One logical change per PR
