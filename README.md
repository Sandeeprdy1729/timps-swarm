# TIMPS Swarm

A local, open-source multi-agent system built on Ollama and LangGraph. Twenty-two specialized agents handle two domains: a ten-agent SDLC pipeline that takes a task from requirements all the way to deployed infrastructure, and twelve computer health agents that diagnose and fix everyday Mac problems.

No cloud API keys. No subscriptions. Everything runs on your machine.

Built on [TIMPS-Coder](https://github.com/Sandeeprdy1729/timps-coder) — a 0.5B model fine-tuned with 20 LoRA adapters for specific bug patterns.

---

## Quick start

**Docker (easiest)**

```bash
git clone https://github.com/Sandeeprdy1729/timps-swarm
cd timps-swarm
make all
open http://localhost:3000
```

**Local**

```bash
make install

# Pull models once (~16 GB)
ollama serve &
ollama pull qwen2.5:14b && ollama pull qwen2.5:7b
ollama pull qwen2.5-coder:7b && ollama pull qwen2.5:3b

make up-local
make ui   # dashboard in a separate terminal
```

---

## What it does

**SDLC pipeline.** Give it a task and ten agents sequence through the work automatically. A Product Manager writes the requirements, an Architect designs the system, a Code Generator implements it using TIMPS-Coder, a Reviewer checks the output, a QA Tester writes the test suite, a Security Auditor scans for OWASP issues, a Performance Optimizer profiles the code, a Docs Writer generates the README, and a DevOps agent produces the Dockerfile and CI/CD config. The whole thing runs as a LangGraph DAG with dependency tracking and automatic retries.

**Computer health agents.** Ask "why is my laptop slow?" or "my Python environment is broken" and the swarm routes the request to the right expert. Each health agent pulls real data — CPU stats from `psutil`, port listings from `lsof`, WiFi info from `networksetup`, crash logs from `~/Library/Logs` — and returns a diagnosis plus the exact commands to fix it. Twelve agents total, each with a specific focus.

**MCP plugin.** All 31 tools are available over MCP so every agent is accessible directly in Claude Code, GitHub Copilot, Cursor, Windsurf, and any other MCP-compatible editor. See the [MCP setup](#mcp-setup) section below.

---

## Architecture

Three layers sit between a user request and the agents doing the work.

**Layer 1 — Computer Manager** (`src/layer1_computer_manager.py`) allocates an isolated working directory and resource quota to every agent that spins up. Each agent lives at `~/.timps/agents/<agent_id>/` with its own CPU cap, memory limit, and disk quota. When an agent finishes or fails, its computer is cleaned up.

**Layer 2 — Swarm Bridge** (`src/layer2_swarm_bridge.py`) handles agent lifecycle: spawning sub-agents, forming teams, and running the full pipeline. It connects directly to the LangGraph DAG that sequences the SDLC workflow.

**Layer 3 — CLI** (`src/layer3_swarm_cli.py`) exposes everything through `give_work.py` and the `timps` shell shim installed by `install.sh`.

```
User request
      │
      ▼
 give_work.py ──── SDLC task?   ──▶ LangGraph 10-agent DAG
      │
      └──────────── Health task? ──▶ computer_health_graph
                                          └─▶ keyword routing
                                          └─▶ 12 expert agents
```

---

## The 22 agents

### SDLC pipeline

| # | Agent | Model | What it does |
|---|-------|-------|--------------|
| 1 | Orchestrator | qwen2.5:14b | Decomposes requests into a task DAG, routes work, handles retries |
| 2 | Product Manager | qwen2.5:7b | Writes PRDs and acceptance criteria |
| 3 | Architect | qwen2.5:14b | System design, API contracts, data models, scalability planning |
| 4 | Code Generator | TIMPS-Coder + qwen2.5-coder:7b | Implementation and bug fixes using 20 LoRA adapters |
| 5 | Code Reviewer | qwen2.5:7b | Reviews for bugs, anti-patterns, and architecture drift |
| 6 | QA Tester | qwen2.5-coder:7b | Writes pytest and integration tests, runs them in a sandbox |
| 7 | Security Auditor | qwen2.5:7b | OWASP scan, bandit SAST, secrets detection, CVE lookup |
| 8 | Performance Optimizer | qwen2.5:7b | Big-O analysis, N+1 detection, caching and async recommendations |
| 9 | Docs Writer | qwen2.5:3b | README, API reference, deployment guide, contributing guide |
| 10 | DevOps | qwen2.5:7b | Multi-stage Dockerfile, docker-compose, GitHub Actions CI/CD |

### Computer health agents

| # | Agent | What it diagnoses and fixes |
|---|-------|-----------------------------|
| 11 | System Optimizer | CPU hogs, startup bloat, thermal throttling, memory pressure |
| 12 | File Organizer | Downloads folder chaos, duplicates, large junk files |
| 13 | Environment Doctor | Broken Python/Node/Docker/PATH — generates exact fix commands |
| 14 | Security Guard | Open ports, camera and mic permissions, suspicious background processes |
| 15 | Network Medic | WiFi drops, DNS failures, high latency, DNS resolution issues |
| 16 | Battery Analyst | Energy vampire processes, battery health, cycle count, wakeup reasons |
| 17 | Update Manager | Pending OS/brew/pip/npm updates — produces a safe, ordered update script |
| 18 | Log Interpreter | Reads crash logs and system logs, explains them in plain English |
| 19 | Privacy Cleaner | Browser cookie audit, macOS app permission review |
| 20 | Media Librarian | Photo and screenshot rename plan, ffmpeg compression suggestions |
| 21 | Backup Sentinel | Time Machine gaps, uncommitted git changes, at-risk files |
| 22 | Context Switcher | Tab overload triage, focus-mode script, distraction app blocking |

---

## What's new

### Agent memory (`src/memory.py`)

Every agent run is appended to `~/.timps/memory/runs.jsonl`. Before each LLM call, the agent queries that log for past runs with overlapping keywords and prepends the relevant ones to the prompt. Over time the agents get better at the things you ask most — if System Optimizer fixed your `WindowServer` problem last month, it knows that context going into the next run.

```bash
# See what the agents have learned
python3 give_work.py --memory
```

### API key auth (`src/auth.py`)

Optional authentication for team use. Auth is off by default (nothing breaks if you don't configure it). To enable it, set `TIMPS_AUTH=1` in your environment.

```bash
# Generate a key
python3 give_work.py --keygen "my-laptop"
# → timps-sk-a9073c90b94...  (shown once, never stored raw)

# List active keys
python3 give_work.py --keys

# Revoke a key by its hash prefix
python3 give_work.py --revoke timps-sk-a907

# Pass a key in MCP tool calls
{ "_api_key": "timps-sk-...", "request": "..." }
```

Keys are stored as SHA-256 hashes in `~/.timps/.secrets` (chmod 600). The raw key is shown exactly once at generation time.

### Install improvements (`install.sh`)

The installer now checks available disk space before prompting to pull models — it needs roughly 16 GB free and will warn you before starting a download that would run out of space mid-way. At the end of the install, a new step starts the TIMPS daemon and confirms it's running.

---

## CLI reference

```bash
# SDLC pipeline — runs all 10 agents in sequence
python3 give_work.py "Write a REST API for user authentication"

# Specify a language
python3 give_work.py "Create a background job queue" -l python

# Spawn specific agents only
python3 give_work.py --spawn code_generator qa_tester "Write code and test it"

# Health task — auto-routes to the right expert
python3 give_work.py "My laptop fan is always running"
python3 give_work.py "My virtualenv is broken"
python3 give_work.py "Why is my WiFi dropping?"

# Full 6-agent health scan
python3 give_work.py --health

# Memory and auth
python3 give_work.py --memory
python3 give_work.py --keygen "team-key"
python3 give_work.py --keys
python3 give_work.py --revoke timps-sk-xxxx
```

---

## MCP setup

Install the package so the `timps-mcp` command is available:

```bash
pip install -e .
```

Then add it to your editor's MCP config. The exact file location varies:

**Claude Code or Claude Desktop** — `~/.claude/mcp.json`

```json
{
  "mcpServers": {
    "timps-swarm": { "command": "timps-mcp" }
  }
}
```

**GitHub Copilot in VS Code** — `.vscode/mcp.json` (already in this repo)

```json
{
  "mcp": {
    "servers": {
      "timps-swarm": { "type": "stdio", "command": "timps-mcp" }
    }
  }
}
```

**Cursor / Windsurf** — same JSON format in `~/.cursor/mcp.json` or the equivalent Windsurf config directory.

Once configured, all 31 tools show up automatically. A few examples of what you can ask:

```
"My Mac is slow — why?"
→ System Optimizer scans CPU, RAM, and startup items, returns a cleanup script

"Fix my Python environment"
→ Environment Doctor diagnoses the issue and gives you the exact commands to run

"Write a REST API"
→ Full 10-agent SDLC pipeline runs: PRD → design → code → review → tests → security → docs → Docker
```

---

## Training your own adapters

The Code Generator uses TIMPS-Coder: a 0.5B model fine-tuned with 20 LoRA adapters, one per bug class. You can add examples and GitHub Actions will train new adapters automatically.

**Create a dataset file:**

```jsonl
// datasets/custom/my_bugs.jsonl
{"buggy_code": "...", "fixed_code": "...", "explanation": "The issue was..."}
{"instruction": "Fix the NPE in...", "output": "Root cause: ...\nFixed:\n```java\n...```"}
```

**Push to trigger training:**

```bash
cp my_bugs.jsonl datasets/custom/
git add datasets/custom/my_bugs.jsonl
git commit -m "feat: add 40 new Python async bug examples"
git push origin main
```

The Actions pipeline merges your data with the base dataset, trains 20 adapters in parallel on Apple Silicon (MLX), runs benchmarks, and publishes the adapter bundle to HuggingFace and GitHub Releases.

Add `HF_TOKEN` and `HF_REPO_ID` to your repo's Secrets to enable the publish step.

**To train locally:**

```bash
make dataset   # merge all custom files
make train     # train all 20 adapters (requires Apple Silicon + MLX)

# Or train a single adapter
BASE_MODEL=Qwen/Qwen2.5-Coder-0.5B-Instruct ITERS=1000 bash retrain-specialized.sh
```

---

## The 20 TIMPS-Coder adapters

Each LoRA adapter is trained for one bug class:

`java_npe` · `java_ioob` · `java_concurrent` · `python_keyerror` · `python_typeerror` · `python_recursion` · `python_async` · `python_logic` · `javascript_null` · `javascript_scope` · `javascript_async` · `cpp_memory` · `cpp_bounds` · `go_routine` · `rust_borrow` · `sql_injection` · `xss_vuln` · `auth_bypass` · `performance_slow` · `api_design`

---

## API

```bash
# Health check
curl http://localhost:8000/health

# Run a swarm task
curl -X POST http://localhost:8000/swarm/run \
  -H "Content-Type: application/json" \
  -d '{"request": "Fix SQL injection in my FastAPI endpoint", "language": "python"}'

# Poll status
curl http://localhost:8000/swarm/status?run_id=abc12345

# Real-time updates
wscat -c ws://localhost:8000/ws
```

---

## Hardware requirements

| Setup | RAM | Notes |
|-------|-----|-------|
| Minimum | 8 GB | One Ollama model loaded at a time |
| Recommended | 16 GB | All models loaded simultaneously |
| Training | 8 GB Apple Silicon | MLX fine-tuning on M1/M2/M3 |
| Scale | 64 GB server | Multiple Ollama instances behind a load balancer |

To scale to 300+ parallel agents, edit `MAX_PARALLEL_AGENTS` in `.env` and use the sharding pattern from `src/layer2_swarm_bridge.py`.

---

## License

MIT. See the [TIMPS-Coder repo](https://github.com/Sandeeprdy1729/timps-coder) for model license details.
