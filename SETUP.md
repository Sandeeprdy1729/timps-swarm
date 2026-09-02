# TIMPS Swarm — Universal Coding-Agent Setup

> **Read this file as an instruction set, not just documentation.**
> If you are an AI coding agent and the user has handed you this repo, follow
> the steps below **yourself** to install TIMPS Swarm on their machine, wire it
> into whatever coding tool you are running inside, and start dispatching the
> 161 specialist agents — in parallel.

When a user clones this repo and points their coding agent at it (e.g.
"read SETUP.md and set me up", "install timps-swarm"), the agent should:

1. **Detect** which coding tool it is running in.
2. **Install** TIMPS Swarm (Node + Python backend — both are cheap).
3. **Register** the `timps-swarm` MCP server for that tool (this file, `mcp.json`,
   and `.claude/`, `.cursor/`, `.vscode/`, `.codex/` already carry the configs).
4. **Verify** it works (`npx timps-swarm providers`, `curl /health`).
5. **Use it** — dispatch the swarm's specialist agents **in parallel**.

---

## 1. What this repo gives you

- **161 specialist AI agents** across 9 categories (code, security, DevOps,
  AI/ML, infra, India-stack, computer health, developer workflow, meta/SDLC).
- A **full 10-agent SDLC pipeline** (`timps_run_task`) that resolves a task end
  to end: Product Manager → Architect → Code Generator → Reviewer → QA →
  Security → Performance → Docs → DevOps, with a self-critique loop.
- **Parallel execution** — agents are dispatched concurrently via
  `ThreadPoolExecutor` + `asyncio.gather()` (`src/graph.py`), plus a
  parallel `timps_batch` delegator.
- **Local-first, BYOK**: runs on Ollama with zero API cost, or uses
  Gemini / Anthropic / OpenAI / Groq when keys are present.

Three transports converge on one dispatch table:

| Path | When used |
|------|-----------|
| **Python MCP stdio** (`python3 -m mcp_server.server`) | Full in-process server, MCP sampling, all 161 tools |
| **Node.js MCP stdio proxy** (`npx timps-swarm mcp`) | npm-only; proxies to a local or remote FastAPI server |
| **FastAPI REST + WebSocket** (`src/main.py`, port 8000) | `/swarm/run`, `/agents/*`, `/mcp/tools`, `/mcp/tools/call`, `/health`, `/ws` |

---

## 2. The one command that does everything: `install-mcp`

```bash
npm i -g timps-swarm
npx timps-swarm install-mcp
```

`install-mcp` auto-detects every AI tool on the machine and:

1. Writes the `timps-swarm` MCP server entry into every detected IDE config
   (Claude Code, Cursor, Windsurf, Continue, Zed, Aider, Goose, Gemini CLI,
   Codex CLI, Amp, Warp, VS Code / Cline / Copilot), with an explicit `env:`
   block forwarding `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`,
   `GROQ_API_KEY`, `TIMPS_API_URL`, `OLLAMA_HOST`, `REDIS_URL`.
2. Writes **one sub-agent `.md` file per TIMPS tool (161 files)** into
   `~/.claude/agents/`, `./.claude/agents/`, and `~/.codex/agents/` so
   Claude Code, Cursor Composer, and Codex can dispatch them in parallel via
   `Task(subagent_type="timps_kubernetes_navigator")`.

```bash
npx timps-swarm install-mcp                  # configure all detected tools
npx timps-swarm install-mcp --tool cursor    # one tool only
npx timps-swarm install-mcp --no-sub-agents  # MCP config only, skip .md files
npx timps-swarm install-mcp --dry-run        # preview without writing
npx timps-swarm uninstall-mcp                # remove everything
```

All writes are **idempotent** and **reversible** — your other config is untouched.

---

## 3. The setup a coding agent should run, step by step

Run these in order. They are safe to run more than once.

### 3.0 Prerequisites

```bash
# Node 18+ (for the npm CLI / Node MCP proxy)
node -v

# Python 3.10+ (for the full backend server)
python3 --version

# Optional but recommended: Ollama for fully-local mode
#   macOS: brew install --cask ollama
#   Linux: curl -fsSL https://ollama.ai/install.sh | sh
```

### 3.1 Install the Python backend (recommended for full features)

```bash
cd <this repo>
python3 -m pip install -e ".[dev]"
# start the FastAPI server in the background
python3 -m src.main &        # or: make up-local
curl http://localhost:8000/health   # expect {"status":"ok",...}
```

### 3.2 Install the npm CLI + register with all detected tools

```bash
npm i -g timps-swarm
npx timps-swarm install-mcp
npx timps-swarm install-mcp --dry-run   # preview what will be written
```

### 3.3 Manually register for your specific tool

If `install-mcp` didn't detect your tool (or you want to be explicit), write
the matching snippet below into the file shown. Use `npx timps-swarm mcp`
for the node proxy, or point `command` at the Python repo with `-m
mcp_server.server` + `cwd` for the full server.

#### Claude Code — `~/.claude/mcp.json`
```json
{ "mcpServers": { "timps-swarm": {
    "command": "npx", "args": ["timps-swarm", "mcp"] } } }
```

#### opencode — `.opencode/mcp.json` (project) or `~/.config/opencode/opencode.json` (global)
```json
{ "mcp": { "timps-swarm": { "type": "stdio",
    "command": "npx", "args": ["timps-swarm", "mcp"] } } }
```

#### Codex CLI — `~/.codex/config.json`
```json
{ "mcpServers": { "timps-swarm": {
    "command": "npx", "args": ["timps-swarm", "mcp"] } } }
```

#### Cursor — `~/.cursor/mcp.json`
```json
{ "mcpServers": { "timps-swarm": {
    "command": "npx", "args": ["timps-swarm", "mcp"] } } }
```

#### Windsurf — `~/.windsurf/mcp.json`
```json
{ "mcpServers": { "timps-swarm": {
    "command": "npx", "args": ["timps-swarm", "mcp"] } } }
```

#### VS Code / Cline / Roo Code / GitHub Copilot — `.vscode/mcp.json`
```json
{ "mcp": { "servers": { "timps-swarm": {
    "type": "stdio", "command": "npx", "args": ["timps-swarm", "mcp"] } } } }
```

#### Continue — `~/.continue/config.json`
```json
{ "mcpServers": [{ "name": "timps-swarm",
    "command": "npx", "args": ["timps-swarm", "mcp"] }] }
```

#### Zed — `~/.config/zed/settings.json`
```json
{ "assistant": { "mcp_servers": { "timps-swarm": {
    "command": "npx", "args": ["timps-swarm", "mcp"] } } } }
```

#### Aider — `~/.aider.conf.yml`
```yaml
mcp-servers:
  timps-swarm:
    command: npx
    args: [timps-swarm, mcp]
    type: stdio
```

#### Goose — `~/.config/goose/config.yaml`
```yaml
extensions:
  - name: timps-swarm
    type: stdio
    cmd: npx timps-swarm mcp
    enabled: true
```

#### Amp — `~/.amp/mcp.json`
```json
{ "mcpServers": { "timps-swarm": {
    "command": "npx", "args": ["timps-swarm", "mcp"] } } }
```

#### Warp — `~/.warp/mcp_servers.json`
```json
{ "timps-swarm": { "command": "npx", "args": ["timps-swarm", "mcp"] } }
```

> **Config files already shipped in this repo** (import if your tool reads them):
> - `.claude/mcp.json` — Claude Code
> - `.cursor/mcp.json` — Cursor
> - `.vscode/mcp.json` — VS Code / Cline / Copilot
> - `.codex/` — Codex
> - `mcp.json`, `server.json` — reference `/ MCP server registry`
>
> For tools **not** in the list above (antigravity, zcode, kimicode, qwencode,
> hermes, openclaw, etc.) the pattern is the same: find that tool's MCP config
> location and add a `timps-swarm` stdio server entry with
> `command: npx, args: ["timps-swarm", "mcp"]`. If the tool instead exposes a
> **project `.mcp.json` or `mcp.json`**, add it there and it will pick it up.

### 3.4 Forward API keys (optional but recommended)

Set any of these in the tool's `env:` block or your shell. Priority order:
**MCP sampler → Gemini → Anthropic → OpenAI → Groq → Ollama → TIMPS-Coder**.

```bash
export GEMINI_API_KEY=...       # recommended — fast, free tier
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export GROQ_API_KEY=...
export OLLAMA_HOST=http://localhost:11434
export TIMPS_API_URL=http://localhost:8000   # for the Node proxy/remote server
```

### 3.5 Verify

```bash
npx timps-swarm providers              # list active LLM providers
curl http://localhost:8000/health/full # deep health + provider status
curl http://localhost:8000/mcp/tools   # list all 161 tools
```

Then **restart / reload your coding tool** and the 161 tools + sub-agents appear.

---

## 4. Using it — parallel agent dispatch

Once wired in, call TIMPS tools directly, or **dispatch specialists in
parallel** the way your tool supports sub-agents:

```
# Full SDLC pipeline (10 agents orchestrated end-to-end)
timps_run_task: "Build a rate-limited REST API for user authentication"

# Dispatch N specialists concurrently (example — 4 in parallel)
Task(subagent_type="timps_security_guard")     # if your tool supports it
Task(subagent_type="timps_battery_analyst")
Task(subagent_type="timps_network_medic")
Task(subagent_type="timps_backup_sentinel")

# Or use the parallel big-batch delegator
timps_batch: "add tests for all handlers"
```

> Your tool may surface TIMPS tools either as `timps_*` MCP tools or as the
> `Timps-<Name>` parallel sub-agents. Either way the 161 capabilities are:
> `research_agent`, `deep_research_agent`, `security_guard`, `system_optimizer`,
> `kubernetes_navigator`, `dependency_agent`, `red_team_agent`, `pr_reviewer`,
> `unit_test_writer`, `api_design_agent`, `db_agent`, `monitoring_agent`,
> `cloud_cost_auditor`, `gst_compliance`, `upi_agent`, `web3_agent`,
> `rag_designer`, `finetuning_agent`, `voice_agent_designer`, `self_critic_agent`
> … and 140 more. Run `timps_list_agents` to see every one in your tool.

---

## 5. What one agent should avoid

- Do **not** run `git clean -dfx` — `dashboard/node_modules/`, `cli/node_modules/`,
  and `dist/` are sometimes tracked depending on history.
- Do **not** hand-edit `generated/` or `dist/` — they are build/runtime artefacts.
- If you regenerate the tool manifest after editing `mcp_server/server.py`,
  run `node cli/tools/generate-manifest.js` then `npx timps-swarm install-mcp`.

---

## 6. Tailoring per user

If the user only wants *some* agents, prefer quality over breadth:

- **Code / SDLC**: `timps_run_task`, `timps_unit_test_writer`, `timps_pr_reviewer`, `timps_refactoring_agent`
- **Security**: `timps_security_guard`, `timps_dependency_agent`, `timps_red_team_agent`, `timps_secrets_management`
- **Health / ops**: `timps_full_checkup`, `timps_system_optimizer`, `timps_backup_sentinel`, `timps_network_medic`
- **AI/ML**: `timps_finetuning_agent`, `timps_rag_designer`, `timps_model_evaluator`
- **India stack**: `timps_gst_compliance`, `timps_upi_agent`, `timps_abdm_agent`, `timps_adr_writer`

Ask the user what they care about, then register only the relevant sub-agent
`.md` files if writing them manually.

---

## One-line summary

```
clone → pip install -e . → npm i -g timps-swarm → npx timps-swarm install-mcp
     → python3 -m src.main & → restart tool → dispatch 161 agents in parallel
```
