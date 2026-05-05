#!/usr/bin/env python3
"""
TIMPS Swarm MCP Server
======================

Implements the Model Context Protocol (MCP) so any MCP-aware client
(Claude Code, GitHub Copilot in VS Code, Cursor, Windsurf, Kimi Code,
Codex CLI, Continue.dev, …) can call the full TIMPS agent swarm as tools.

Protocol: JSON-RPC 2.0 over stdio (the MCP standard transport).

Tools exposed
─────────────
  Code / SDLC pipeline:
    timps_run_task          — full 10-agent SDLC pipeline

  Computer health (12 agents):
    timps_system_optimizer   — slow laptop / startup bloat / thermal
    timps_file_organizer     — downloads chaos / duplicates / large files
    timps_environment_doctor — broken Python/Node/Docker/PATH
    timps_security_guard     — open ports / camera-mic permissions
    timps_network_medic      — WiFi drops / DNS / latency
    timps_battery_analyst    — energy drainers / battery health
    timps_update_manager     — OS / brew / pip / npm updates
    timps_log_interpreter    — crash logs → plain English
    timps_privacy_cleaner    — browser cookies / app permissions
    timps_media_librarian    — photos / videos / screenshots
    timps_backup_sentinel    — Time Machine / git uncommitted
    timps_context_switcher   — tabs / focus / distractions

  Meta:
    timps_dispatch           — auto-routes any request to the right agent
    timps_full_checkup       — run 6 agents for a comprehensive health scan
    timps_list_agents        — list all available agents + status
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Allow running from repo root without installing ──────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("timps-mcp")

# ── Lazy imports so the server starts even if heavy deps are missing ──────────

def _import_agents():
    from src.computer_agents import (
        system_optimizer_node, file_organizer_node, environment_doctor_node,
        security_guard_node, network_medic_node, battery_analyst_node,
        update_manager_node, log_interpreter_node, privacy_cleaner_node,
        media_librarian_node, backup_sentinel_node, context_switcher_node,
    )
    return {
        "system_optimizer":   system_optimizer_node,
        "file_organizer":     file_organizer_node,
        "environment_doctor": environment_doctor_node,
        "security_guard":     security_guard_node,
        "network_medic":      network_medic_node,
        "battery_analyst":    battery_analyst_node,
        "update_manager":     update_manager_node,
        "log_interpreter":    log_interpreter_node,
        "privacy_cleaner":    privacy_cleaner_node,
        "media_librarian":    media_librarian_node,
        "backup_sentinel":    backup_sentinel_node,
        "context_switcher":   context_switcher_node,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────────────────────────────────────────

TOOLS: List[Dict[str, Any]] = [
    # ── Meta ──────────────────────────────────────────────────────────────────
    {
        "name": "timps_list_agents",
        "description": (
            "List all 22 TIMPS Swarm agents with their purpose, "
            "so you can choose the right one for the user's request."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "timps_dispatch",
        "description": (
            "Auto-detect the best TIMPS agent for any plain-English request "
            "and run it immediately. Use this when unsure which agent to pick. "
            "Examples: 'my wifi keeps dropping', 'why is my laptop slow', "
            "'broken python environment', 'organize my downloads'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The user's plain-English request or complaint.",
                },
            },
            "required": ["request"],
        },
    },
    {
        "name": "timps_full_checkup",
        "description": (
            "Run a comprehensive computer health scan across 6 agents: "
            "system optimizer, battery analyst, security guard, network medic, "
            "backup sentinel, and update manager. Returns a combined health score "
            "and prioritised action list."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "Optional hint to customise the checkup (e.g. 'focus on performance').",
                },
            },
            "required": [],
        },
    },
    # ── SDLC pipeline ─────────────────────────────────────────────────────────
    {
        "name": "timps_run_task",
        "description": (
            "Run the full 10-agent SDLC pipeline (product manager → architect → "
            "code generator → reviewer → QA → security → performance → devops → docs). "
            "Use for software development tasks: writing code, fixing bugs, building APIs, etc."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The development task, e.g. 'Write a REST API for user auth in Python'.",
                },
                "language": {
                    "type": "string",
                    "description": "Programming language (default: python).",
                    "default": "python",
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum pipeline iterations (default: 10).",
                    "default": 10,
                },
            },
            "required": ["request"],
        },
    },
    # ── 12 Computer Health agents ─────────────────────────────────────────────
    {
        "name": "timps_system_optimizer",
        "description": (
            "Diagnose why a computer is slow. Scans: top CPU/RAM processes, "
            "startup items, thermal throttling, memory pressure. "
            "Returns a report with specific processes to kill and startup items to disable. "
            "Generates a dry-run cleanup shell script."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Optional: extra context like 'laptop fan running loudly since update'.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "timps_file_organizer",
        "description": (
            "Scan Downloads and Desktop for clutter: duplicates, large files, "
            "unnamed junk. Generates a folder organisation plan and a move script "
            "(dry-run — no files moved until user approves)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional: custom directory to scan (default: ~/Downloads and ~/Desktop).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "timps_environment_doctor",
        "description": (
            "Diagnose broken development environments. Checks Python, Node.js, "
            "Docker, Git, PATH integrity, shell config conflicts. "
            "Returns exact terminal commands to fix each issue."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "Optional: 'python', 'node', 'docker', 'git', or 'all' (default: all).",
                    "default": "all",
                },
            },
            "required": [],
        },
    },
    {
        "name": "timps_security_guard",
        "description": (
            "Security scan: open network ports, running process anomalies, "
            "app camera/microphone/location permissions (macOS TCC). "
            "Returns CVSS-rated findings and mitigation commands."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "timps_network_medic",
        "description": (
            "Diagnose network problems: ping internet/Cloudflare, DNS resolution, "
            "WiFi signal, traceroute, open ports. Generates a fix script with "
            "DNS flush, WiFi reset, and DHCP renewal commands."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Hostname or IP to ping/trace (default: 8.8.8.8).",
                    "default": "8.8.8.8",
                },
            },
            "required": [],
        },
    },
    {
        "name": "timps_battery_analyst",
        "description": (
            "Identify battery drainers. Reads battery %, health cycle count, "
            "and ranks processes by CPU usage (proxy for energy drain). "
            "Generates kill commands for the top energy vampires."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "timps_update_manager",
        "description": (
            "Check for pending updates: macOS/Linux OS, Homebrew packages, "
            "global npm packages, pip packages. Returns a prioritised update plan "
            "(security first) with a safe ordered shell script."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "timps_log_interpreter",
        "description": (
            "Read crash logs and system logs, extract stack traces, and explain "
            "each crash in plain English. Classifies as app bug / OS bug / hardware / user error. "
            "Pass a log file path to analyse a specific log."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_path": {
                    "type": "string",
                    "description": "Optional: absolute path to a specific log file to analyse.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "timps_privacy_cleaner",
        "description": (
            "Privacy audit: count cookies per browser (Chrome, Firefox, Edge, Brave), "
            "list macOS app permissions (camera, mic, location, contacts). "
            "Returns a cleanup manifest — no data is deleted until user reviews."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "timps_media_librarian",
        "description": (
            "Scan Photos, Downloads, Desktop for media chaos: unnamed photos, "
            "screenshot backlog, oversized videos. Suggests a date-based rename plan "
            "and generates ffmpeg compression commands (dry-run)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional: directory to scan (default: ~/Pictures, ~/Downloads, ~/Desktop).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "timps_backup_sentinel",
        "description": (
            "Audit backup health: Time Machine last backup time, all local git repos "
            "with uncommitted/unpushed changes, large files on Desktop/Documents "
            "not tracked by git or cloud. Returns a risk score and backup script."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "timps_context_switcher",
        "description": (
            "Analyse current work context: active apps, estimated browser tabs, "
            "current git branch and recent commits. Identifies distraction apps "
            "and generates a focus-mode script to quit them."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # ── Context Keeper & Agent Kernel ─────────────────────────────────────────
    {
        "name": "timps_context_briefing",
        "description": (
            "Get a 3-sentence resumption briefing from the Context Keeper: what you were working on, "
            "current state (uncommitted changes, broken tests), and recommended next step. "
            "Use when the user says 'what was I doing' or 'catch me up'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "refresh": {
                    "type": "boolean",
                    "description": "Force refresh even if cache is fresh (default: false).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "timps_delegate",
        "description": (
            "Delegate a multi-step goal to the TIMPS Agent Kernel. The kernel plans, "
            "routes to specialist agents, and returns a structured result. "
            "Use for complex goals like 'fix the auth bug and ensure 80% test coverage'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The high-level goal to accomplish.",
                },
                "context": {
                    "type": "object",
                    "description": "Optional metadata: repo_path, branch, language, etc.",
                },
            },
            "required": ["goal"],
        },
    },
    {
        "name": "timps_kernel_status",
        "description": "Check the status of a previously delegated kernel run by its run_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "The run_id returned by timps_delegate.",
                },
            },
            "required": ["run_id"],
        },
    },
    # ── Expert / Deep-Diagnostic agents ──────────────────────────────────────
    {
        "name": "timps_dependency_rebel",
        "description": "Detect dependency conflicts, vulnerabilities, and outdated packages across Python and Node. Returns a fix plan and remediation script.",
        "inputSchema": {"type": "object", "properties": {"repo_path": {"type": "string", "description": "Path to repo (defaults to cwd)"}}, "required": []},
    },
    {
        "name": "timps_merge_conflict_predictor",
        "description": "Predict merge conflicts between two branches before merging, with file-level and line-level overlap analysis.",
        "inputSchema": {"type": "object", "properties": {"branch_a": {"type": "string"}, "branch_b": {"type": "string"}, "repo_path": {"type": "string"}}, "required": []},
    },
    {
        "name": "timps_tech_debt_quantifier",
        "description": "Scan codebase for TODO/FIXME density, cyclomatic complexity hotspots, and deprecated patterns. Returns a prioritised debt repayment plan.",
        "inputSchema": {"type": "object", "properties": {"repo_path": {"type": "string"}}, "required": []},
    },
    {
        "name": "timps_migration_pilot",
        "description": "Analyse a codebase for breaking-change APIs given a target library/framework upgrade. Returns a step-by-step migration checklist.",
        "inputSchema": {"type": "object", "properties": {"goal": {"type": "string", "description": "e.g. 'migrate from React 17 to React 18'"}, "repo_path": {"type": "string"}}, "required": ["goal"]},
    },
    {
        "name": "timps_flaky_test_detective",
        "description": "Identify flaky tests by scanning for timing dependencies, random data, and external HTTP calls. Reads pytest failure cache for history.",
        "inputSchema": {"type": "object", "properties": {"repo_path": {"type": "string"}}, "required": []},
    },
    {
        "name": "timps_onboarding_mentor",
        "description": "Generate a customised onboarding guide: most-touched files, architecture overview, key modules, recent PR walkthroughs.",
        "inputSchema": {"type": "object", "properties": {"repo_path": {"type": "string"}}, "required": []},
    },
    {
        "name": "timps_incident_responder",
        "description": "Multi-source log correlation for production incidents. Gathers Docker + app logs, builds a timeline, and generates a triage report.",
        "inputSchema": {"type": "object", "properties": {"window_minutes": {"type": "integer", "description": "How many minutes back to look (default 30)"}, "repo_path": {"type": "string"}}, "required": []},
    },
    {
        "name": "timps_cloud_cost_auditor",
        "description": "Scan Terraform configs for waste (over-provisioned instances, missing deletion protection) and check AWS CLI for idle resources.",
        "inputSchema": {"type": "object", "properties": {"repo_path": {"type": "string"}}, "required": []},
    },
    {
        "name": "timps_certificate_rotator",
        "description": "Check TLS certificate expiry for all hosts found in config files. Warns 30 days before expiry and generates certbot renewal commands.",
        "inputSchema": {"type": "object", "properties": {"repo_path": {"type": "string"}, "hosts": {"type": "array", "items": {"type": "string"}}}, "required": []},
    },
    {
        "name": "timps_terraform_plan_reviewer",
        "description": "Review terraform plan output for destructive changes. Requires explicit approval before allowing apply on high-risk plans.",
        "inputSchema": {"type": "object", "properties": {"repo_path": {"type": "string"}, "plan_text": {"type": "string", "description": "Raw output of 'terraform plan' (optional — will run it if omitted)"}}, "required": []},
    },
    {
        "name": "timps_dotfile_doctor",
        "description": "Detect errors and performance issues in shell config files (.zshrc, .bashrc, .gitconfig). Finds slow evals, duplicate PATH entries, syntax errors.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "timps_disk_space_prophet",
        "description": "Predict disk usage trends, identify cache directories safe to prune, and warn before 'no space left on device' events.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Tool handlers
# ─────────────────────────────────────────────────────────────────────────────

AGENT_DESCRIPTIONS = {
    # SDLC
    "orchestrator":          "Routes and coordinates the 10-agent SDLC pipeline",
    "product_manager":       "Writes PRDs and breaks down requirements",
    "architect":             "Designs system architecture and tech stack",
    "code_generator":        "Writes production-quality code",
    "code_reviewer":         "Reviews code for correctness and style",
    "qa_tester":             "Writes and runs automated tests",
    "security_auditor":      "Audits code for OWASP vulnerabilities",
    "performance_optimizer": "Identifies and fixes performance bottlenecks",
    "documentation_writer":  "Writes README, docstrings, API docs",
    "devops":                "Creates Dockerfile, CI/CD, deployment configs",
    # Computer Health
    "system_optimizer":      "Diagnoses slow laptop — CPU hogs, startup bloat, thermal",
    "file_organizer":        "Organises Downloads/Desktop — duplicates, large files, junk",
    "environment_doctor":    "Fixes broken Python/Node/Docker/PATH environments",
    "security_guard":        "Scans open ports, camera/mic permissions, suspicious processes",
    "network_medic":         "Diagnoses WiFi drops, DNS failures, high latency",
    "battery_analyst":       "Identifies energy vampire processes, checks battery health",
    "update_manager":        "Lists pending OS/brew/pip/npm updates, generates safe update script",
    "log_interpreter":       "Reads crash logs and explains them in plain English",
    "privacy_cleaner":       "Audits browser cookies and macOS app permissions",
    "media_librarian":       "Organises photos/videos — rename plan, compression script",
    "backup_sentinel":       "Checks Time Machine, git uncommitted/unpushed, at-risk files",
    "context_switcher":      "Analyses open apps/tabs, generates focus-mode script",
}


def _format_result(result: Dict[str, Any]) -> str:
    """Format an agent result dict as a clean Markdown string for the LLM."""
    agent = result.get("agent", "unknown").replace("_", " ").title()
    report = result.get("report", "")
    report_path = result.get("report_path", "")
    script_path = result.get("script_path", "")
    raw = result.get("raw_data", {})

    lines = [f"# TIMPS {agent} Report\n"]
    lines.append(report)

    if raw:
        lines.append("\n---\n**Quick Stats:**")
        for k, v in raw.items():
            lines.append(f"- `{k}`: {v}")

    if report_path:
        lines.append(f"\n**Full report saved:** `{report_path}`")
    if script_path:
        lines.append(f"**Action script saved:** `{script_path}` (dry-run — review before executing)")

    return "\n".join(lines)


def _handle_list_agents(_args: Dict) -> str:
    lines = ["# TIMPS Swarm — Available Agents\n",
             "## SDLC Pipeline (10 agents) — use `timps_run_task`\n"]
    sdlc = [k for k in AGENT_DESCRIPTIONS if k in {
        "orchestrator", "product_manager", "architect", "code_generator",
        "code_reviewer", "qa_tester", "security_auditor",
        "performance_optimizer", "documentation_writer", "devops",
    }]
    for name in sdlc:
        lines.append(f"- **{name}**: {AGENT_DESCRIPTIONS[name]}")

    lines.append("\n## Computer Health Agents (12 agents)\n")
    health = [k for k in AGENT_DESCRIPTIONS if k not in sdlc]
    for name in health:
        lines.append(f"- **`timps_{name}`**: {AGENT_DESCRIPTIONS[name]}")

    return "\n".join(lines)


def _handle_dispatch(args: Dict) -> str:
    from src.computer_agents import dispatch
    request = args.get("request", "")
    result = dispatch(request, {"user_request": request})
    return _format_result(result)


def _handle_full_checkup(args: Dict) -> str:
    from src.computer_health_graph import run_health_task
    request = args.get("focus") or "full system checkup"
    result = run_health_task(request, multi_agent=True)

    lines = ["# TIMPS Full System Checkup\n"]
    if result.get("health_summary"):
        lines.append("## Overall Health Summary\n")
        lines.append(result["health_summary"])

    lines.append(f"\n## Agents Run: {', '.join(result.get('agents_run', []))}\n")

    for r in result.get("reports", []):
        agent = r.get("agent", "").replace("_", " ").title()
        report = (r.get("report") or "")[:600]
        lines.append(f"\n### {agent}\n{report}\n…")
        if r.get("report_path"):
            lines.append(f"_Full report: `{r['report_path']}`_")

    if result.get("action_scripts"):
        lines.append("\n## Action Scripts (dry-run, review before executing):")
        for s in result["action_scripts"]:
            lines.append(f"- `{s}`")

    if result.get("errors"):
        lines.append("\n## Errors:")
        for e in result["errors"]:
            lines.append(f"- {e}")

    return "\n".join(lines)


def _handle_run_task(args: Dict) -> str:
    import asyncio
    from src.layer2_swarm_bridge import get_swarm_bridge
    bridge = get_swarm_bridge()
    request = args.get("request", "")
    language = args.get("language", "python")
    max_iter = int(args.get("max_iterations", 10))

    async def _run():
        return await bridge.run_swarm_task(
            request=request, language=language,
            max_iterations=max_iter, wait_for_completion=True,
        )

    task = asyncio.run(_run())
    lines = [f"# TIMPS SDLC Task: {request}\n",
             f"**Status:** {task.status}\n"]
    for key in ["requirements", "architecture_plan", "test_results",
                "security_report", "documentation", "final_deliverable"]:
        val = task.results.get(key, "") if task.results else ""
        if val:
            lines.append(f"## {key.replace('_', ' ').title()}\n{val[:800]}\n")
    if task.artifacts:
        lines.append(f"## Artifacts\n" + "\n".join(f"- {a}" for a in task.artifacts))
    if task.error:
        lines.append(f"## Error\n{task.error}")
    return "\n".join(lines)


def _handle_context_briefing(args: Dict) -> str:
    from src.context_keeper import get_briefing
    refresh = bool(args.get("refresh", False))
    return get_briefing(regenerate=refresh)


def _handle_delegate(args: Dict) -> str:
    from src.agent_kernel import delegate
    goal = args.get("goal", "")
    context = args.get("context") or {}
    result = delegate(goal, context)
    lines = [
        f"# TIMPS Kernel Run: {result['run_id']}",
        f"**Status:** {result['status']}",
        f"**Tasks:** {result['tasks_done']}/{result['tasks_total']} done, {result['tasks_failed']} failed",
        "",
        result.get("final_report", ""),
    ]
    if result.get("artifacts"):
        lines.append("\n**Artifacts:** " + ", ".join(f"`{a}`" for a in result["artifacts"]))
    return "\n".join(lines)


def _handle_kernel_status(args: Dict) -> str:
    import json
    from pathlib import Path
    run_id = args.get("run_id", "")
    board_path = Path("generated/kernel") / f"run_{run_id}.json"
    if not board_path.exists():
        return f"No kernel run found with id: {run_id}"
    data = json.loads(board_path.read_text())
    done = sum(1 for t in data.get("tasks", []) if t["status"] == "done")
    total = len(data.get("tasks", []))
    report_snippet = (data.get("final_report") or "In progress…")[:1000]
    return f"Run `{run_id}`: status={data['status']}, tasks={done}/{total} done\n\n{report_snippet}"


def _handle_health_agent(agent_name: str, args: Dict) -> str:
    agents = _import_agents()
    node_fn = agents[agent_name]
    state: Dict[str, Any] = {"user_request": args.get("context") or args.get("focus") or ""}
    if args.get("log_path"):
        state["user_request"] = args["log_path"]
    if args.get("path"):
        # Override default scan path by injecting into state
        state["_scan_path"] = args["path"]
    result = node_fn(state)
    return _format_result(result)


def _handle_expert_agent(agent_name: str, args: Dict) -> str:
    from src.expert_agents import EXPERT_AGENT_MAP
    node_fn = EXPERT_AGENT_MAP[agent_name]
    state: Dict[str, Any] = {
        "user_request": args.get("goal") or args.get("context") or "",
        "repo_path": args.get("repo_path") or "",
        "plan_text": args.get("plan_text") or "",
        "window_minutes": args.get("window_minutes") or 30,
    }
    if args.get("hosts"):
        state["_extra_hosts"] = args["hosts"]
    if args.get("branch_a"):
        state["user_request"] = f"predict conflicts between {args['branch_a']} and {args.get('branch_b', 'main')}"
    result = node_fn(state)
    return _format_result(result)


# Map tool name → handler
_TOOL_HANDLERS: Dict[str, Any] = {
    "timps_list_agents":        lambda a: _handle_list_agents(a),
    "timps_dispatch":           lambda a: _handle_dispatch(a),
    "timps_full_checkup":       lambda a: _handle_full_checkup(a),
    "timps_run_task":           lambda a: _handle_run_task(a),
    "timps_system_optimizer":   lambda a: _handle_health_agent("system_optimizer",   a),
    "timps_file_organizer":     lambda a: _handle_health_agent("file_organizer",     a),
    "timps_environment_doctor": lambda a: _handle_health_agent("environment_doctor", a),
    "timps_security_guard":     lambda a: _handle_health_agent("security_guard",     a),
    "timps_network_medic":      lambda a: _handle_health_agent("network_medic",      a),
    "timps_battery_analyst":    lambda a: _handle_health_agent("battery_analyst",    a),
    "timps_update_manager":     lambda a: _handle_health_agent("update_manager",     a),
    "timps_log_interpreter":    lambda a: _handle_health_agent("log_interpreter",    a),
    "timps_privacy_cleaner":    lambda a: _handle_health_agent("privacy_cleaner",    a),
    "timps_media_librarian":    lambda a: _handle_health_agent("media_librarian",    a),
    "timps_backup_sentinel":    lambda a: _handle_health_agent("backup_sentinel",    a),
    "timps_context_switcher":   lambda a: _handle_health_agent("context_switcher",   a),
    "timps_context_briefing":   lambda a: _handle_context_briefing(a),
    "timps_delegate":            lambda a: _handle_delegate(a),
    "timps_kernel_status":       lambda a: _handle_kernel_status(a),
    # Expert agents
    "timps_dependency_rebel":         lambda a: _handle_expert_agent("dependency_rebel", a),
    "timps_merge_conflict_predictor": lambda a: _handle_expert_agent("merge_conflict_predictor", a),
    "timps_tech_debt_quantifier":     lambda a: _handle_expert_agent("tech_debt_quantifier", a),
    "timps_migration_pilot":          lambda a: _handle_expert_agent("migration_pilot", a),
    "timps_flaky_test_detective":     lambda a: _handle_expert_agent("flaky_test_detective", a),
    "timps_onboarding_mentor":        lambda a: _handle_expert_agent("onboarding_mentor", a),
    "timps_incident_responder":       lambda a: _handle_expert_agent("incident_responder", a),
    "timps_cloud_cost_auditor":       lambda a: _handle_expert_agent("cloud_cost_auditor", a),
    "timps_certificate_rotator":      lambda a: _handle_expert_agent("certificate_rotator", a),
    "timps_terraform_plan_reviewer":  lambda a: _handle_expert_agent("terraform_plan_reviewer", a),
    "timps_dotfile_doctor":           lambda a: _handle_expert_agent("dotfile_doctor", a),
    "timps_disk_space_prophet":       lambda a: _handle_expert_agent("disk_space_prophet", a),
}


# ─────────────────────────────────────────────────────────────────────────────
# MCP JSON-RPC 2.0 server (stdio transport)
# ─────────────────────────────────────────────────────────────────────────────

def _make_response(id_: Any, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "result": result})


def _make_error(id_: Any, code: int, message: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})


def _handle_request(msg: Dict) -> Optional[str]:
    """Process one JSON-RPC message and return a response string (or None for notifications)."""
    method = msg.get("method", "")
    id_ = msg.get("id")
    params = msg.get("params") or {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    if method == "initialize":
        return _make_response(id_, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "timps-swarm",
                "version": "1.0.0",
                "description": (
                    "TIMPS Swarm: 22 AI agents for software development (SDLC) "
                    "and computer health (slow laptop, broken envs, WiFi, battery, …)"
                ),
            },
        })

    if method == "notifications/initialized":
        return None   # notification — no response

    if method == "ping":
        return _make_response(id_, {})

    # ── Tool discovery ─────────────────────────────────────────────────────────
    if method == "tools/list":
        return _make_response(id_, {"tools": TOOLS})

    # ── Tool execution ─────────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}

        # ── API key authentication ─────────────────────────────────────────
        try:
            from src.auth import check_request_auth
            if not check_request_auth(arguments):
                return _make_error(id_, -32001, (
                    "Authentication required. Add '_api_key' to your tool arguments. "
                    "Generate a key with: python3 give_work.py --keygen \"your-name\""
                ))
        except ImportError:
            pass  # auth module not available — open access

        handler = _TOOL_HANDLERS.get(tool_name)
        if not handler:
            return _make_error(id_, -32601, f"Unknown tool: {tool_name}")

        try:
            text = handler(arguments)
            return _make_response(id_, {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            })
        except Exception as exc:
            err_text = f"Tool {tool_name} failed:\n{traceback.format_exc()}"
            logger.error(err_text)
            return _make_response(id_, {
                "content": [{"type": "text", "text": err_text}],
                "isError": True,
            })

    # ── Unknown method ─────────────────────────────────────────────────────────
    if id_ is not None:
        return _make_error(id_, -32601, f"Method not found: {method}")
    return None


def run_server():
    """Main loop: read JSON-RPC from stdin, write responses to stdout."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s [timps-mcp] %(message)s",
        stream=sys.stderr,   # MCP uses stderr for logs, stdout for protocol
    )
    logger.warning("TIMPS Swarm MCP server starting (stdio transport)…")

    # Use binary mode + manual newline split for cross-platform reliability
    stdin  = sys.stdin.buffer
    stdout = sys.stdout.buffer

    while True:
        try:
            line = stdin.readline()
            if not line:
                break   # EOF — client disconnected
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError as exc:
                response = _make_error(None, -32700, f"Parse error: {exc}")
                stdout.write((response + "\n").encode())
                stdout.flush()
                continue

            response = _handle_request(msg)
            if response is not None:
                stdout.write((response + "\n").encode())
                stdout.flush()

        except KeyboardInterrupt:
            break
        except Exception as exc:
            logger.error("Unhandled error: %s", exc, exc_info=True)


if __name__ == "__main__":
    run_server()
