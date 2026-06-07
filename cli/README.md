# timps-swarm CLI

> **160 AI specialists — code, security, DevOps, AI/ML, infra, India-stack,
> health, research, content, voice, robotics, and more.**
> One `npm install` puts every one of them into your AI coding tool as
> parallel sub-agents. Works with just Node — no Python required.

[![npm](https://img.shields.io/badge/npm-timps--swarm-CB3837?style=flat-square&logo=npm&logoColor=white)](https://www.npmjs.com/package/timps-swarm)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Node 18+](https://img.shields.io/badge/Node-18%2B-339933?style=flat-square&logo=node.js&logoColor=white)](https://nodejs.org)
[![MCP Protocol](https://img.shields.io/badge/Protocol-MCP-7C3AED?style=flat-square)](https://modelcontextprotocol.io)
[![v2.2.0](https://img.shields.io/badge/version-2.2.0-FF6B35?style=flat-square)](https://github.com/Sandeeprdy1729/timps-swarm/releases)

## Install

```bash
npm install -g timps-swarm
# or run without installing:
npx timps-swarm <command>
```

The postinstall hook auto-detects every AI tool on your machine and:

1. Writes the `timps-swarm` MCP server entry into each IDE config file,
   including an explicit `env:` block that forwards your API keys
   (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
   `GROQ_API_KEY`, `TIMPS_API_URL`, `OLLAMA_HOST`, `REDIS_URL`).
2. Writes one sub-agent `.md` file per agent (160 total) into
   `~/.claude/agents/`, `./.claude/agents/`, and `~/.codex/agents/`
   so Claude Code, Cursor, and Codex can dispatch them in parallel
   via `Task(subagent_type="timps_kubernetes_navigator")`.

Restart your tool — 160 agents appear as MCP tools **and** as parallel sub-agents.

```bash
# Zero-setup, no install required:
npx timps-swarm audit ./          # security scan any repo
```

## Run without the Python backend

`npm install -g timps-swarm` works **without** the Python repo. The CLI
ships `cli/lib/mcp-proxy.js`, a Node.js JSON-RPC 2.0 stdio proxy that
forwards every MCP tool call to a running FastAPI server (local or
remote via `TIMPS_API_URL`). The full Python server is only needed for
MCP sampling (using the host's LLM) and for tools that have to run
locally; everything else works through the proxy.

```bash
# Point at a remote API
TIMPS_API_URL=https://timps.example.com npx timps-swarm mcp

# Run the Python server yourself (only if you want the full experience)
git clone https://github.com/Sandeeprdy1729/timps-swarm
cd timps-swarm
pip install -e ".[dev]"
make up-local                       # starts FastAPI on :8000
```

## Commands

### `audit` — security scan (works offline)

```bash
npx timps-swarm audit ./                       # scan CWD
npx timps-swarm audit ./src --ecosystem python # Python focus
npx timps-swarm audit requirements.txt
npx timps-swarm audit package.json --ecosystem node
```

### `fix` — run the full 10-agent SDLC pipeline

```bash
npx timps-swarm fix "build a REST API for a todo app"
npx timps-swarm fix ./src --language typescript
```

### `health` — diagnose your machine (12 specialist agents)

```bash
npx timps-swarm health
```

### Research, design, scaffolding

```bash
npx timps-swarm research "best practices for distributed tracing in 2026" --depth deep
npx timps-swarm api-design "billing API with metered usage and Stripe webhooks"
npx timps-swarm db-design "multi-tenant SaaS with usage-based billing" --engine postgresql
npx timps-swarm n8n "when GitHub issue is labeled bug, post to Slack and create Jira ticket"
```

### `providers` — show LLM provider status

```bash
npx timps-swarm providers
```

### `mcp` — start the MCP stdio server

```bash
npx timps-swarm mcp                            # auto-detect Python repo
npx timps-swarm mcp --repo /path/to/repo       # explicit
TIMPS_API_URL=https://... npx timps-swarm mcp  # use remote API
```

For use in `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "timps-swarm": {
      "command": "npx",
      "args": ["timps-swarm", "mcp"],
      "env": {
        "GEMINI_API_KEY": "...",
        "ANTHROPIC_API_KEY": "..."
      }
    }
  }
}
```

### `start` — start the FastAPI server (Python repo required)

```bash
npx timps-swarm start                # start in foreground on :8000
npx timps-swarm start --repo ./..    # start with explicit repo path
```

### `install-mcp` / `uninstall-mcp` — wire up (or remove) every IDE

```bash
npx timps-swarm install-mcp              # all detected tools + 160 sub-agents
npx timps-swarm install-mcp --tool cursor          # one tool only
npx timps-swarm install-mcp --no-sub-agents        # MCP config only, no .md files
npx timps-swarm install-mcp --dry-run              # preview without writing
npx timps-swarm uninstall-mcp           # remove the MCP config and 160 sub-agents
```

By default `install-mcp` writes:

- **MCP server entries** into 9 IDE config files (one per IDE, all
  pointing at `npx timps-swarm mcp`).
- **160 sub-agent `.md` files** into `~/.claude/agents/`,
  `./.claude/agents/`, `~/.codex/agents/` (one per MCP tool) so
  Claude Code's `Task(subagent_type="timps_kubernetes_navigator")`,
  Cursor Composer, and Codex can dispatch them in parallel.

All writes are **idempotent** (re-running updates the existing file) and
**reversible** via `uninstall-mcp` (only removes the `timps-swarm` key
and the `timps-*.md` files — your other config is untouched).

## Flags

```
FLAGS (install-mcp)
  --tool <id>            Configure one IDE only
                         (claude-code, cursor, codex-cli, windsurf, vscode, …)
  --no-sub-agents        Skip writing 160 sub-agent .md files (MCP config only)
  --dry-run              Preview without writing
  --silent               Suppress output (postinstall)

FLAGS (start / mcp)
  --repo <path>          Explicit path to the Python repo (skip auto-detection)
```

## Environment Variables

| Variable | Description |
| :--- | :--- |
| `TIMPS_API_URL` | TIMPS server URL — default `http://localhost:8000`. The Node.js MCP proxy, `install-mcp`, and `providers` all honour this. |
| `TIMPS_REPO` | Explicit path to the Python repo. Skips `findRepoPython()` auto-detection (priority: `$TIMPS_REPO` → walk up CWD → `~/timps-swarm` → `~/Desktop/timps-swarm` → `/opt/timps-swarm` → npm global prefix). |
| `GEMINI_API_KEY` | Google Gemini — free tier, recommended. |
| `ANTHROPIC_API_KEY` | Anthropic Claude. |
| `OPENAI_API_KEY` | OpenAI GPT-4o. |
| `GROQ_API_KEY` | Groq (fast Llama 3.3 70B). |
| `OLLAMA_HOST` | Ollama server URL — default `http://localhost:11434`. |
| `REDIS_URL` | Redis server URL — default `redis://localhost:6379/0`. Falls back to in-memory dict silently when Redis is down. |
| `LOG_LEVEL` | Default `INFO`. |

## The 160 agents

9 categories. Every one is callable as an MCP tool **and** registered as a
native Claude Code / Cursor / Codex sub-agent.

| Category | Count | Highlights |
|----------|------:|------------|
| **Priority** | 68 | research_agent, ab_testing_agent, abdm_agent, browser_automation, churn_predictor, deep_research_agent, digilocker_agent, dpdp_act_auditor, federated_learning, finetuning_agent, fssai_compliance_agent, gst_compliance, indiehacker_agent, model_evaluator, model_perf_monitor, prompt_injection_scanner, quantum_ready, rag_designer, rag_evaluator, red_team_agent, sbom_generator, service_mesh_configurator, storybook_story_generator, upi_agent, voice_agent_designer, wearable_health_coach, web3_agent, win_loss_analyst, … |
| **Expert Diagnostics** | 51 | kubernetes_navigator, docker_compose_architect, pipeline_healer, mcp_server_generator, observability_cost_optimizer, accessibility_tester, license_compliance_scanner, iac_drift_detector, disaster_recovery, contract_reviewer, court_case_summarizer, data_pipeline, db_migration_pilot, game_day_facilitator, git_workflow_automator, graphql_agent, load_testing, local_rag_builder, log_pattern_analyzer, phishing_simulator, postmortem_agent, test_intelligence, visual_regression_detective, web_scraping, web_search, … |
| **Computer Health** | 12 | system_optimizer, file_organizer, environment_doctor, security_guard, network_medic, battery_analyst, update_manager, log_interpreter, privacy_cleaner, media_librarian, backup_sentinel, context_switcher |
| **Developer Workflow** | 12 | issue_triager, boilerplate_architect, pr_reviewer, dependency_sentinel, unit_test_writer, docstring_generator, log_detective, sql_optimizer, sprint_reporter, flaky_test_hunter, api_contract_auditor, content_multiplier |
| **Knowledge Worker** | 7 | inbox_gatekeeper, meeting_condenser, research_scout, trend_monitor, data_wrangler, competitor_tracker, agri_commodity_forecaster |
| **Meta** | 6 | list_agents, dispatch, full_checkup, list_providers, connect_tools, tool_status |
| **Context / Kernel** | 3 | context_briefing, delegate, kernel_status |
| **SDLC Pipeline** | 1 | run_task — the 10-node LangGraph orchestrator: PM → Architect → Code → Review → QA → Security → Perf → Docs → DevOps |

```bash
# Trigger the full SDLC pipeline
python3 give_work.py "Build a rate-limited REST API for user authentication"

# Run a computer health checkup
npx timps-swarm health
python3 give_work.py "My laptop fan is always running"

# Delegate a multi-step goal
npx timps-swarm delegate "fix the auth bug and ensure 80% test coverage"
```

## Requirements

- **Node.js 18+**
- One of: a running FastAPI server (Python repo OR `TIMPS_API_URL` set),
  or just the Node.js fallback proxy (calls any reachable API).

## License

MIT
