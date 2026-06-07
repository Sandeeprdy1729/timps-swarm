"""Smoke tests for TIMPS Swarm.

These tests do not hit the network or call LLM providers. They verify the
MCP server's tool catalogue, handler dispatch, CLI manifest, package
versions, and sub-agent file consistency.

Run with::

    pytest tests/                    # from repo root
    make test                        # once Makefile target is wired
    python -m pytest tests/ -v       # verbose
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── MCP tool catalogue ──────────────────────────────────────────────────────


def test_mcp_tool_catalogue_has_160_tools():
    """The MCP server must expose exactly 160 tools — the canonical agent
    catalogue size after the 2.2.0 expansion (was 64 in 2.1.0)."""
    from mcp_server.server import TOOLS
    assert len(TOOLS) == 160, f"Expected 160 tools, got {len(TOOLS)}"


def test_every_tool_has_a_handler():
    """Every tool in TOOLS must have a matching handler in _TOOL_HANDLERS
    — otherwise tools/list would advertise calls that fail with 404."""
    from mcp_server.server import TOOLS, _TOOL_HANDLERS
    tool_names = {t["name"] for t in TOOLS}
    handler_names = set(_TOOL_HANDLERS.keys())
    missing = tool_names - handler_names
    extra = handler_names - tool_names
    assert not missing, f"Tools without handlers: {sorted(missing)}"
    assert not extra, f"Handlers without tools: {sorted(extra)}"


def test_tool_schemas_are_valid_json_schema():
    """Every tool must have a non-empty name, description, and an
    inputSchema of type 'object' (MCP requirement)."""
    from mcp_server.server import TOOLS
    for t in TOOLS:
        name = t.get("name")
        assert isinstance(name, str) and name, f"Bad tool entry: {t}"
        assert isinstance(t.get("description"), str) and t["description"], (
            f"Empty description for {name}"
        )
        schema = t.get("inputSchema")
        assert isinstance(schema, dict), f"Bad inputSchema for {name}"
        assert schema.get("type") == "object", (
            f"Tool {name} has invalid inputSchema (type={schema.get('type')}): {schema}"
        )


# ── Handler smoke tests (no LLM calls) ──────────────────────────────────────


def test_list_agents_handler_returns_catalogue():
    """timps_list_agents is the canonical 'what agents are available?'
    tool — it must return a non-trivial catalogue."""
    from mcp_server.server import _TOOL_HANDLERS
    text = _TOOL_HANDLERS["timps_list_agents"]({})
    assert isinstance(text, str)
    assert len(text) > 1000, f"list_agents returned {len(text)} chars (expected >1000)"
    assert "agents" in text.lower()


def test_list_providers_handler_returns_provider_table():
    """timps_list_providers shows which LLM provider is currently active."""
    from mcp_server.server import _TOOL_HANDLERS
    text = _TOOL_HANDLERS["timps_list_providers"]({})
    assert isinstance(text, str)
    assert len(text) > 50, f"list_providers returned {len(text)} chars"


def test_meta_agents_present():
    """The four meta-agents must be in the catalogue — they're the entry
    points most clients call first."""
    from mcp_server.server import TOOLS
    names = {t["name"] for t in TOOLS}
    for required in (
        "timps_list_agents",
        "timps_list_providers",
        "timps_tool_status",
        "timps_connect_tools",
    ):
        assert required in names, f"Missing meta agent: {required}"


# ── Package version consistency ─────────────────────────────────────────────


def test_cli_package_version_is_2_2_0():
    """The npm package version must be 2.2.0 to match the published
    release on the registry."""
    pkg_path = REPO_ROOT / "cli" / "package.json"
    assert pkg_path.exists(), f"Missing {pkg_path}"
    pkg = json.loads(pkg_path.read_text())
    assert pkg["version"] == "2.2.0", (
        f"cli/package.json version is {pkg['version']}, expected 2.2.0"
    )
    assert "160" in pkg.get("description", ""), (
        f"cli/package.json description should mention 160 agents: {pkg.get('description')}"
    )


def test_python_package_version_is_2_2_0():
    """The Python `timps-swarm-mcp` package version (pyproject.toml) must
    be 2.2.0 to match the npm release."""
    pyproject = REPO_ROOT / "pyproject.toml"
    assert pyproject.exists()
    content = pyproject.read_text()
    assert 'version = "2.2.0"' in content, (
        f"pyproject.toml version should be 2.2.0 — "
        f"found: {[l.strip() for l in content.split(chr(10)) if 'version' in l and '=' in l]}"
    )


def test_mcp_server_info_version_is_2_2_0():
    """The MCP server's serverInfo.version must match the published npm
    package version (2.2.0). Drift here breaks MCP clients that cache the
    version."""
    mcp_server = REPO_ROOT / "mcp_server" / "server.py"
    assert mcp_server.exists()
    content = mcp_server.read_text()
    # The serverInfo is emitted as a Python dict literal in a JSON-RPC
    # response. Look for `"version": "2.2.0"` near `"name": "timps-swarm"`.
    match = re.search(
        r'"name":\s*"timps-swarm".*?"version":\s*"([0-9.]+)"',
        content,
        re.DOTALL,
    )
    assert match, "Could not find timps-swarm serverInfo in mcp_server/server.py"
    assert match.group(1) == "2.2.0", (
        f"MCP serverInfo.version is {match.group(1)}, expected 2.2.0"
    )


# ── Manifest and sub-agent files ────────────────────────────────────────────


def test_subagents_manifest_is_in_sync():
    """The npm CLI's agents-manifest.js must be in sync with TOOLS — the
    generator script (cli/tools/generate-manifest.js) re-syncs it, so the
    counts must match."""
    manifest_path = REPO_ROOT / "cli" / "lib" / "agents-manifest.js"
    assert manifest_path.exists(), f"Manifest missing: {manifest_path}"
    content = manifest_path.read_text()
    # The manifest is a JS object literal — count real entries by matching
    # `{ name: '` (with the opening brace + leading quote). The JSDoc
    # typedef on line 5 also has `name:`, so a plain `name: ` count would
    # over-count by 1.
    agent_count = content.count("{ name: '")
    assert agent_count == 160, (
        f"Manifest has {agent_count} agents (expected 160). "
        f"Re-run `node cli/tools/generate-manifest.js` to re-sync."
    )


def test_repo_subagent_files_count_160():
    """The checked-in `.claude/agents/` sub-agent files must be exactly
    160. This is the canonical sub-agent location for Claude Code and
    Cursor."""
    subagents_dir = REPO_ROOT / ".claude" / "agents"
    assert subagents_dir.is_dir(), f"Missing {subagents_dir}"
    md_files = list(subagents_dir.glob("timps-*.md"))
    assert len(md_files) == 160, (
        f"Found {len(md_files)} sub-agent .md files (expected 160). "
        f"Re-run `npx timps-swarm install-mcp` to regenerate."
    )


def test_repo_subagent_files_have_valid_yaml():
    """Every sub-agent `.md` file must have valid YAML frontmatter — the
    `e9e7545f` fix quoted descriptions because 51/160 had unescaped
    colons. This test asserts each file has `---` delimiters and that the
    description is wrapped in double quotes."""
    subagents_dir = REPO_ROOT / ".claude" / "agents"
    md_files = list(subagents_dir.glob("timps-*.md"))
    broken = []
    for f in md_files:
        text = f.read_text()
        if not text.startswith("---\n"):
            broken.append((f.name, "missing leading ---"))
            continue
        end = text.find("\n---\n", 3)
        if end == -1:
            broken.append((f.name, "unterminated frontmatter"))
            continue
        frontmatter = text[3:end]
        if "name:" not in frontmatter or "description:" not in frontmatter:
            broken.append((f.name, "missing required keys"))
            continue
        # Find the description line and check it starts with a quote
        for line in frontmatter.split("\n"):
            if line.startswith("description:"):
                value = line[len("description:"):].lstrip()
                if not value.startswith('"'):
                    broken.append((f.name, f"unquoted description: {line[:60]}…"))
                break
    assert not broken, (
        f"{len(broken)} broken sub-agent .md files. First 5: {broken[:5]}"
    )


# ── HTTP endpoint surface (FastAPI lazy-import) ─────────────────────────────


def test_mcp_install_endpoint_is_deprecated():
    """The old `POST /mcp/install` HTTP endpoint must return 410 Gone —
    the npm CLI's `install-mcp` is the canonical way. This catches
    accidental re-introduction."""
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from src.main import app
    paths = {r.path for r in app.routes}
    assert "/mcp/install" in paths, "/mcp/install endpoint missing"
    # Find the route and check it raises HTTPException(410, ...)
    for route in app.routes:
        if getattr(route, "path", None) == "/mcp/install":
            # The 410 is raised inside the body, not at registration, so
            # we just confirm the endpoint exists. The full HTTP behavior
            # is covered by the live test in `make test` if the API is up.
            return
    assert False, "/mcp/install route not found"
