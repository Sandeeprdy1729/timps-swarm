"""
Context Keeper Agent
════════════════════
Background daemon + working memory for "What was I doing?" resumption.

Monitors:
  - Git state: current branch, recent commits, uncommitted changes
  - Open VS Code workspaces (via recents JSON)
  - Recent terminal commands (shell history)
  - Failed test runs in generated/reports/
  - Active processes that look like dev servers

Saves a compact Working Memory Graph to ~/.timps/memory/
On task resumption, generates a 3-sentence briefing the MCP host can inject.

Usage as agent node:
  from src.context_keeper import context_keeper_node, get_briefing

Usage as daemon:
  python3 -m src.context_keeper --daemon   # runs every 5 minutes
  python3 -m src.context_keeper --brief    # print current briefing and exit
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(os.getenv("TIMPS_MEMORY_DIR", Path.home() / ".timps" / "memory"))
MEMORY_FILE = MEMORY_DIR / "working_memory.json"
BRIEFING_FILE = MEMORY_DIR / "last_briefing.md"
MAX_HISTORY_COMMANDS = 50
MAX_RECENT_COMMITS = 10


# ─────────────────────────────────────────────────────────────────────────────
# Data collectors (all read-only, no side effects)
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 5) -> str:
    """Run a shell command safely; return stdout or empty string on failure."""
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, cwd=cwd, timeout=timeout)
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def collect_git_state(cwd: Optional[str] = None) -> Dict:
    """Collect complete git context from the current working directory."""
    state: Dict[str, Any] = {}

    # Find git root
    git_root = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if not git_root:
        return {"error": "not a git repo"}

    state["repo_root"] = git_root
    state["branch"] = _run(["git", "branch", "--show-current"], cwd=git_root)
    state["remote"] = _run(["git", "remote", "get-url", "origin"], cwd=git_root)

    # Recent commits (short log)
    log_raw = _run(
        ["git", "log", f"-{MAX_RECENT_COMMITS}", "--oneline", "--no-decorate"],
        cwd=git_root
    )
    state["recent_commits"] = log_raw.splitlines()

    # Uncommitted changes
    status_raw = _run(["git", "status", "--short"], cwd=git_root)
    state["uncommitted_files"] = [l.strip() for l in status_raw.splitlines() if l.strip()]
    state["uncommitted_count"] = len(state["uncommitted_files"])

    # Last commit message and timestamp
    last_commit = _run(["git", "log", "-1", "--format=%h %s (%ar)"], cwd=git_root)
    state["last_commit"] = last_commit

    # Stashes
    stash_list = _run(["git", "stash", "list"], cwd=git_root)
    state["stashes"] = stash_list.splitlines() if stash_list else []

    # Unpushed commits
    unpushed = _run(["git", "log", "@{u}..", "--oneline"], cwd=git_root)
    state["unpushed_commits"] = unpushed.splitlines() if unpushed else []

    return state


def collect_shell_history() -> List[str]:
    """Read recent terminal history from common shell history files."""
    commands: List[str] = []

    history_files = [
        Path.home() / ".zsh_history",
        Path.home() / ".bash_history",
        Path.home() / ".local/share/fish/fish_history",
    ]

    for hf in history_files:
        if not hf.exists():
            continue
        try:
            raw = hf.read_text(errors="replace")
            if hf.name == "fish_history":
                # Fish history format: "- cmd: <command>"
                cmds = re.findall(r"^- cmd: (.+)$", raw, re.MULTILINE)
            elif "zsh_history" in hf.name:
                # Zsh extended history: ": <timestamp>:<elapsed>;<command>"
                cmds = re.findall(r";\s*(.+)$", raw, re.MULTILINE)
            else:
                cmds = raw.splitlines()

            # Deduplicate, strip, take last N
            seen = set()
            for cmd in reversed(cmds):
                cmd = cmd.strip()
                if cmd and cmd not in seen:
                    seen.add(cmd)
                    commands.append(cmd)
                if len(commands) >= MAX_HISTORY_COMMANDS:
                    break
        except Exception:
            continue

    return list(reversed(commands))  # oldest first


def collect_vscode_workspaces() -> List[str]:
    """Find recently opened VS Code workspaces from the storage DB."""
    recent_dirs: List[str] = []

    # VS Code stores recently opened in different places per OS
    candidates = [
        Path.home() / "Library/Application Support/Code/storage.json",
        Path.home() / ".config/Code/storage.json",
        Path.home() / "Library/Application Support/Code/User/globalStorage/storage.json",
    ]

    for storage_file in candidates:
        if storage_file.exists():
            try:
                data = json.loads(storage_file.read_text(errors="replace"))
                # Different VS Code versions use different keys
                for key in ["openedPathsList", "lastKnownMenubarData"]:
                    if key in data:
                        workspaces = data[key].get("workspaces3", []) or \
                                     data[key].get("workspaces", [])
                        for ws in workspaces[:10]:
                            path = ws if isinstance(ws, str) else ws.get("folderUri", "")
                            path = path.replace("file://", "")
                            if path and Path(path).exists():
                                recent_dirs.append(path)
            except Exception:
                continue

    return list(dict.fromkeys(recent_dirs))  # deduplicate, preserve order


def collect_dev_servers() -> List[Dict]:
    """Detect running dev servers by scanning process names and ports."""
    servers: List[Dict] = []
    try:
        import psutil
        dev_patterns = [
            "uvicorn", "flask", "django", "fastapi", "node", "npm", "yarn",
            "webpack", "vite", "next", "nuxt", "react-scripts", "ng serve",
            "ruby", "rails", "go run", "cargo run", "python -m",
        ]
        for proc in psutil.process_iter(["pid", "name", "cmdline", "connections"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
                if any(p in cmd for p in dev_patterns):
                    conns = proc.info.get("connections") or []
                    ports = [c.laddr.port for c in conns if c.status == "LISTEN"] if conns else []
                    if ports or any(p in cmd for p in dev_patterns[:6]):
                        servers.append({
                            "pid": proc.info["pid"],
                            "name": proc.info["name"],
                            "cmd_snippet": cmd[:120],
                            "ports": ports[:3],
                        })
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
    except ImportError:
        pass
    return servers[:8]


def collect_recent_test_results() -> List[Dict]:
    """Read the most recent test/report files from generated/reports/."""
    reports: List[Dict] = []
    report_dir = Path("generated/reports")
    if not report_dir.exists():
        return reports
    report_files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    for rf in report_files:
        try:
            content = rf.read_text(errors="replace")
            # Extract first 3 lines as summary
            summary = "\n".join(content.splitlines()[:3])
            reports.append({
                "file": str(rf),
                "modified": datetime.datetime.fromtimestamp(rf.stat().st_mtime).isoformat(),
                "summary": summary,
            })
        except Exception:
            continue
    return reports


# ─────────────────────────────────────────────────────────────────────────────
# Working Memory Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_working_memory(cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Gather all context signals and return a structured working memory snapshot.
    This is the raw data layer — not yet LLM-analysed.
    """
    now = datetime.datetime.now().isoformat()

    memory: Dict[str, Any] = {
        "captured_at": now,
        "cwd": cwd or str(Path.cwd()),
        "git": collect_git_state(cwd),
        "shell_history_recent": collect_shell_history()[-20:],  # last 20 commands
        "vscode_workspaces": collect_vscode_workspaces(),
        "dev_servers": collect_dev_servers(),
        "recent_reports": collect_recent_test_results(),
    }

    return memory


def save_working_memory(memory: Dict) -> str:
    """Persist working memory snapshot to disk; return path."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(memory, indent=2, default=str), encoding="utf-8")
    # Also save a timestamped snapshot for history
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_path = MEMORY_DIR / f"snapshot_{ts}.json"
    snap_path.write_text(json.dumps(memory, indent=2, default=str), encoding="utf-8")
    # Keep only last 20 snapshots
    snapshots = sorted(MEMORY_DIR.glob("snapshot_*.json"))
    for old in snapshots[:-20]:
        old.unlink(missing_ok=True)
    return str(MEMORY_FILE)


def load_working_memory() -> Optional[Dict]:
    """Load the most recent working memory snapshot from disk."""
    if not MEMORY_FILE.exists():
        return None
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Briefing Generator (LLM-powered)
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm_briefing(memory: Dict) -> str:
    """Generate a 3-sentence resumption briefing from working memory."""
    try:
        from src.llm_router import LLMRouter
        router = LLMRouter()
    except Exception:
        return _fallback_briefing(memory)

    git = memory.get("git", {})
    history = memory.get("shell_history_recent", [])
    servers = memory.get("dev_servers", [])
    reports = memory.get("recent_reports", [])

    context_parts = []

    if git.get("branch"):
        context_parts.append(f"Git branch: {git['branch']}")
    if git.get("last_commit"):
        context_parts.append(f"Last commit: {git['last_commit']}")
    if git.get("uncommitted_count", 0) > 0:
        context_parts.append(f"Uncommitted changes ({git['uncommitted_count']} files): {', '.join(git['uncommitted_files'][:5])}")
    if git.get("unpushed_commits"):
        context_parts.append(f"Unpushed commits: {'; '.join(git['unpushed_commits'][:3])}")
    if history:
        context_parts.append(f"Recent commands: {'; '.join(history[-10:])}")
    if servers:
        srv = [f"{s['name']}:{s['ports']}" for s in servers[:3]]
        context_parts.append(f"Running dev servers: {', '.join(srv)}")
    if reports:
        context_parts.append(f"Recent agent reports: {', '.join(r['file'] for r in reports[:3])}")

    context = "\n".join(context_parts)
    captured_at = memory.get("captured_at", "recently")

    system_prompt = (
        "You are a developer assistant who helps programmers resume work after an interruption. "
        "Given a snapshot of a developer's working context (git state, recent commands, running servers), "
        "write exactly 3 concise sentences that tell the developer:\n"
        "1. What they were working on\n"
        "2. What the last state was (any errors, uncommitted changes, broken tests)\n"
        "3. The most logical next step to take\n"
        "Be specific, concrete, and use technical terms. No filler words."
    )

    user_msg = (
        f"Context snapshot taken {captured_at}:\n\n{context}\n\n"
        "Write a 3-sentence resumption briefing:"
    )

    try:
        return router.call("context_keeper", user_msg, system_prompt=system_prompt)
    except Exception as exc:
        logger.warning("LLM briefing failed: %s", exc)
        return _fallback_briefing(memory)


def _fallback_briefing(memory: Dict) -> str:
    """Generate a briefing without LLM (pure data summary)."""
    git = memory.get("git", {})
    lines = []
    branch = git.get("branch", "unknown branch")
    last_commit = git.get("last_commit", "no commits found")
    uncommitted = git.get("uncommitted_count", 0)

    lines.append(f"You were working on branch `{branch}` — last commit: {last_commit}.")
    if uncommitted > 0:
        files = ", ".join(git.get("uncommitted_files", [])[:3])
        lines.append(f"There are {uncommitted} uncommitted file(s): {files}.")
    else:
        lines.append("No uncommitted changes — working tree is clean.")

    history = memory.get("shell_history_recent", [])
    if history:
        last_cmd = history[-1]
        lines.append(f"Last terminal command was: `{last_cmd}`.")
    else:
        lines.append("No recent shell history found.")

    return " ".join(lines)


def get_briefing(cwd: Optional[str] = None, regenerate: bool = False) -> str:
    """
    Get the current resumption briefing.
    Uses cached memory if available and fresh (< 10 min), otherwise regenerates.
    """
    memory = load_working_memory() if not regenerate else None

    if memory is None:
        memory = build_working_memory(cwd)
        save_working_memory(memory)

    # Check freshness (10-minute window)
    elif not regenerate:
        try:
            captured = datetime.datetime.fromisoformat(memory.get("captured_at", "2000-01-01"))
            age = (datetime.datetime.now() - captured).total_seconds()
            if age > 600:  # 10 minutes
                memory = build_working_memory(cwd)
                save_working_memory(memory)
        except Exception:
            pass

    briefing = _call_llm_briefing(memory)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    BRIEFING_FILE.write_text(briefing, encoding="utf-8")
    return briefing


# ─────────────────────────────────────────────────────────────────────────────
# Agent node (LangGraph-compatible)
# ─────────────────────────────────────────────────────────────────────────────

def context_keeper_node(state: Dict) -> Dict:
    """
    LangGraph agent node.
    Captures a working memory snapshot and returns a briefing.
    """
    from src.computer_agents import _save_report

    cwd = state.get("_scan_path") or str(Path.cwd())
    user_request = state.get("user_request", "").strip()

    try:
        memory = build_working_memory(cwd)
        save_working_memory(memory)
        briefing = _call_llm_briefing(memory)

        # Build a detailed markdown report
        git = memory.get("git", {})
        history = memory.get("shell_history_recent", [])
        servers = memory.get("dev_servers", [])
        reports = memory.get("recent_reports", [])

        md_lines = [
            "# TIMPS Context Keeper Report\n",
            f"**Captured:** {memory['captured_at']}  ",
            f"**Directory:** `{memory['cwd']}`\n",
            "## Resumption Briefing\n",
            briefing,
            "\n---\n",
            "## Git State\n",
        ]

        if git.get("error"):
            md_lines.append(f"_{git['error']}_")
        else:
            md_lines.append(f"- **Branch:** `{git.get('branch', 'unknown')}`")
            md_lines.append(f"- **Last commit:** {git.get('last_commit', 'none')}")
            uc = git.get("uncommitted_count", 0)
            md_lines.append(f"- **Uncommitted:** {uc} file(s)")
            if git.get("uncommitted_files"):
                for f in git["uncommitted_files"][:10]:
                    md_lines.append(f"  - `{f}`")
            if git.get("unpushed_commits"):
                md_lines.append(f"- **Unpushed commits:** {len(git['unpushed_commits'])}")
                for c in git["unpushed_commits"][:5]:
                    md_lines.append(f"  - `{c}`")
            if git.get("stashes"):
                md_lines.append(f"- **Stashes:** {len(git['stashes'])}")

        if history:
            md_lines.append("\n## Recent Terminal Commands (last 10)\n")
            for cmd in history[-10:]:
                md_lines.append(f"- `{cmd}`")

        if servers:
            md_lines.append("\n## Running Dev Servers\n")
            for s in servers:
                ports = ", ".join(str(p) for p in s.get("ports", []))
                md_lines.append(f"- **{s['name']}** (pid {s['pid']}) — ports: {ports or 'unknown'}")
                md_lines.append(f"  `{s['cmd_snippet'][:80]}`")

        if reports:
            md_lines.append("\n## Recent Agent Reports\n")
            for r in reports:
                md_lines.append(f"- [{Path(r['file']).name}]({r['file']}) — {r['modified']}")

        report_content = "\n".join(md_lines)
        report_path = _save_report("context_keeper.md", report_content)

        return {
            "agent": "context_keeper",
            "report": briefing,
            "report_path": report_path,
            "raw_data": {
                "branch": git.get("branch", "unknown"),
                "uncommitted": git.get("uncommitted_count", 0),
                "last_commit": git.get("last_commit", "none"),
                "dev_servers_running": len(servers),
                "memory_file": str(MEMORY_FILE),
            },
        }

    except Exception as exc:
        logger.error("context_keeper_node failed: %s", exc, exc_info=True)
        return {
            "agent": "context_keeper",
            "report": f"Context collection error: {exc}",
            "raw_data": {},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Background daemon
# ─────────────────────────────────────────────────────────────────────────────

def run_daemon(interval_seconds: int = 300):
    """
    Run as a background daemon: refresh working memory every `interval_seconds`.
    Typically 5 minutes (300s) — keeps memory fresh for instant resumption.
    """
    logger.info("TIMPS Context Keeper daemon started (interval=%ds)", interval_seconds)
    while True:
        try:
            memory = build_working_memory()
            save_working_memory(memory)
            logger.debug("Working memory refreshed at %s", datetime.datetime.now().isoformat())
        except Exception as exc:
            logger.warning("Daemon refresh error: %s", exc)
        time.sleep(interval_seconds)


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="TIMPS Context Keeper")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument("--brief", action="store_true", help="Print briefing and exit")
    parser.add_argument("--refresh", action="store_true", help="Force refresh then print briefing")
    parser.add_argument("--interval", type=int, default=300, help="Daemon refresh interval (seconds)")
    parser.add_argument("--json", action="store_true", help="Output raw memory as JSON")
    args = parser.parse_args()

    if args.daemon:
        run_daemon(args.interval)
    elif args.json:
        mem = build_working_memory()
        save_working_memory(mem)
        print(json.dumps(mem, indent=2, default=str))
    else:
        briefing = get_briefing(regenerate=args.refresh)
        print("\n─── TIMPS Context Briefing ─────────────────────────────────────")
        print(briefing)
        print("────────────────────────────────────────────────────────────────\n")
        print(f"Full memory saved to: {MEMORY_FILE}")
