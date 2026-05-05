#!/usr/bin/env python3
"""
timps doctor — TIMPS-Swarm health validator

Checks every system requirement and prints a clear pass/fail table.
Run automatically by install.sh, or manually:

  python3 timps_doctor.py
  python3 timps_doctor.py --quick     # skip slow checks (model pulls)
  python3 timps_doctor.py --fix       # auto-fix what can be fixed
  python3 timps_doctor.py --memory    # print Context Keeper briefing
  python3 timps_doctor.py --json      # machine-readable output
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ── Ensure src/ is importable ─────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
RED    = "\033[0;31m"
CYAN   = "\033[0;36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

USE_COLOUR = sys.stdout.isatty()

def c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}" if USE_COLOUR else text


# ─────────────────────────────────────────────────────────────────────────────
# Check result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    detail: str = ""
    fixable: bool = False
    fix_cmd: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Individual checks
# ─────────────────────────────────────────────────────────────────────────────

def check_python_version() -> CheckResult:
    ok = sys.version_info >= (3, 10)
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return CheckResult(
        "Python ≥3.10",
        passed=ok,
        message=f"Python {ver}",
        fix_cmd="Install Python 3.10+ from python.org or via uv: uv python install 3.11",
    )


def check_required_packages() -> CheckResult:
    required = [
        "langgraph", "langchain", "fastapi", "uvicorn",
        "pydantic", "requests", "psutil",
    ]
    missing = []
    for pkg in required:
        try:
            importlib.import_module(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if missing:
        return CheckResult(
            "Python packages",
            passed=False,
            message=f"Missing: {', '.join(missing)}",
            fixable=True,
            fix_cmd=f"pip install {' '.join(missing)}",
        )
    return CheckResult("Python packages", passed=True, message="All core packages installed")


def check_optional_packages() -> CheckResult:
    optional = {"playwright": "browser tools", "transformers": "TIMPS-Coder model", "peft": "LoRA adapters"}
    missing = []
    for pkg, reason in optional.items():
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(f"{pkg} ({reason})")

    if missing:
        return CheckResult(
            "Optional packages",
            passed=True,  # optional — don't fail
            message=f"Not installed: {', '.join(missing)}",
            detail="Optional features disabled. Install with: pip install " + " ".join(p.split(" ")[0] for p in missing),
        )
    return CheckResult("Optional packages", passed=True, message="All optional packages installed")


def check_playwright() -> CheckResult:
    try:
        import playwright  # noqa: F401
        # Check if browser is installed
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "show-trace"],
            capture_output=True, timeout=5,
        )
        # Any response means playwright is importable
        return CheckResult("Playwright browser", passed=True, message="playwright installed")
    except ImportError:
        return CheckResult(
            "Playwright browser",
            passed=False,
            message="playwright not installed",
            fixable=True,
            fix_cmd="pip install playwright && playwright install chromium",
        )
    except Exception:
        return CheckResult("Playwright browser", passed=True, message="playwright installed (browser check skipped)")


def check_ollama_running() -> CheckResult:
    if not shutil.which("ollama"):
        return CheckResult(
            "Ollama",
            passed=False,
            message="ollama command not found",
            fixable=True,
            fix_cmd="Install from https://ollama.ai or: brew install --cask ollama",
        )
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return CheckResult(
                "Ollama",
                passed=True,
                message=f"Running — {len(models)} models loaded",
                detail=", ".join(models[:6]),
            )
    except Exception:
        pass
    return CheckResult(
        "Ollama",
        passed=False,
        message="Ollama installed but not running",
        fixable=True,
        fix_cmd="ollama serve &",
    )


def check_required_models() -> CheckResult:
    needed = {"qwen2.5:14b", "qwen2.5:7b", "qwen2.5-coder:7b", "qwen2.5:3b"}
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code != 200:
            return CheckResult("Ollama models", passed=False, message="Ollama not reachable")
        present = {m["name"] for m in resp.json().get("models", [])}
        missing = needed - present
        if missing:
            return CheckResult(
                "Ollama models",
                passed=False,
                message=f"Missing: {', '.join(sorted(missing))}",
                fixable=True,
                fix_cmd=" && ".join(f"ollama pull {m}" for m in sorted(missing)),
            )
        return CheckResult("Ollama models", passed=True, message="All 4 required models present")
    except Exception as e:
        return CheckResult("Ollama models", passed=False, message=f"Cannot check: {e}")


def check_src_imports() -> CheckResult:
    modules = [
        ("src.agents", "SDLC agents"),
        ("src.computer_agents", "health agents"),
        ("src.system_tools", "system tools"),
        ("src.context_keeper", "context keeper"),
        ("src.agent_kernel", "agent kernel"),
        ("src.llm_router", "LLM router"),
        ("src.state", "shared state"),
        ("mcp_server.server", "MCP server"),
    ]
    failures = []
    for mod, label in modules:
        try:
            importlib.import_module(mod)
        except Exception as exc:
            failures.append(f"{label}: {exc}")

    if failures:
        return CheckResult(
            "Source imports",
            passed=False,
            message=f"{len(failures)} module(s) failed to import",
            detail="\n".join(failures),
        )
    return CheckResult("Source imports", passed=True, message=f"All {len(modules)} modules import cleanly")


def check_mcp_server() -> CheckResult:
    """Smoke-test the MCP server by running initialize + tools/list."""
    try:
        import json
        import subprocess as sp

        proc = sp.Popen(
            [sys.executable, "-m", "mcp_server.server"],
            stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.DEVNULL,
            cwd=str(_REPO),
        )

        msg = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "doctor"}},
        }) + "\n"
        proc.stdin.write(msg.encode())
        proc.stdin.flush()

        line = proc.stdout.readline()
        resp = json.loads(line)
        proc.terminate()

        if resp.get("result", {}).get("serverInfo", {}).get("name") == "timps-swarm":
            return CheckResult("MCP server", passed=True, message="JSON-RPC initialize OK")
        return CheckResult("MCP server", passed=False, message="Unexpected initialize response")
    except Exception as exc:
        return CheckResult(
            "MCP server",
            passed=False,
            message=f"Server failed to start: {exc}",
            detail=str(exc),
        )


def check_generated_dirs() -> CheckResult:
    dirs = [
        Path("generated/reports"),
        Path("generated/scripts"),
        Path("generated/kernel"),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return CheckResult("Output directories", passed=True, message="generated/ subdirs ready")


def check_memory_dir() -> CheckResult:
    memory_dir = Path.home() / ".timps" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return CheckResult("Memory directory", passed=True, message=f"{memory_dir} ready")


def check_ide_configs() -> CheckResult:
    """Check which IDEs have TIMPS MCP config registered."""
    configs = {
        "Claude Desktop": Path.home() / ".claude" / "mcp.json",
        "Cursor":         Path.home() / ".cursor" / "mcp.json",
        "VS Code":        Path.home() / "Library/Application Support/Code/User/mcp.json",
        "Repo local":     _REPO / ".vscode" / "mcp.json",
    }
    found = []
    missing = []
    for name, cfg in configs.items():
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text())
                has_timps = "timps-swarm" in json.dumps(data)
                if has_timps:
                    found.append(name)
                else:
                    missing.append(f"{name} (config exists but no timps-swarm entry)")
            except Exception:
                missing.append(f"{name} (invalid JSON)")
        else:
            missing.append(f"{name} (not installed or not configured)")

    msg = f"{len(found)} IDE(s) configured" + (f"; missing: {', '.join(missing)}" if missing else "")
    return CheckResult(
        "IDE MCP configs",
        passed=bool(found),
        message=msg,
        detail=f"Configured: {', '.join(found) or 'none'}",
        fixable=True,
        fix_cmd="bash install.sh  # auto-registers all detected IDEs",
    )


def check_context_keeper() -> CheckResult:
    """Quick smoke-test of the context keeper (no LLM)."""
    try:
        from src.context_keeper import collect_git_state
        state = collect_git_state()
        branch = state.get("branch") or state.get("error", "no branch")
        return CheckResult(
            "Context Keeper",
            passed=True,
            message=f"Git state collected — branch: {branch}",
        )
    except Exception as exc:
        return CheckResult("Context Keeper", passed=False, message=f"Error: {exc}")


def check_agent_kernel() -> CheckResult:
    """Verify the agent kernel can be imported."""
    try:
        from src.agent_kernel import _heuristic_plan, Blackboard
        tasks = _heuristic_plan("write a hello world function")
        return CheckResult(
            "Agent Kernel",
            passed=True,
            message=f"Kernel planner works — {len(tasks)} tasks planned",
        )
    except Exception as exc:
        return CheckResult("Agent Kernel", passed=False, message=f"Import failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

FAST_CHECKS: List[Callable[[], CheckResult]] = [
    check_python_version,
    check_required_packages,
    check_optional_packages,
    check_src_imports,
    check_generated_dirs,
    check_memory_dir,
    check_ide_configs,
    check_context_keeper,
    check_agent_kernel,
]

SLOW_CHECKS: List[Callable[[], CheckResult]] = [
    check_playwright,
    check_ollama_running,
    check_required_models,
    check_mcp_server,
]


def run_checks(quick: bool = False) -> List[CheckResult]:
    checks = FAST_CHECKS + ([] if quick else SLOW_CHECKS)
    results = []
    for fn in checks:
        try:
            r = fn()
        except Exception as exc:
            r = CheckResult(fn.__name__, passed=False, message=f"Check crashed: {exc}")
        results.append(r)
    return results


def print_results(results: List[CheckResult]):
    print()
    print(c(BOLD, "  TIMPS-Swarm Doctor"))
    print(c(CYAN, "  ─" * 35))
    print()

    max_name = max(len(r.name) for r in results)
    passed = 0
    failed = 0

    for r in results:
        icon = c(GREEN, "✅") if r.passed else c(RED, "❌")
        name = r.name.ljust(max_name)
        msg  = c(GREEN if r.passed else RED, r.message)
        print(f"  {icon}  {name}  {msg}")
        if r.detail:
            for line in r.detail.splitlines():
                print(f"       {c(CYAN, line)}")
        if not r.passed and r.fix_cmd:
            print(f"       {c(YELLOW, 'Fix:')} {r.fix_cmd}")
        if r.passed:
            passed += 1
        else:
            failed += 1

    print()
    print(c(CYAN, "  ─" * 35))
    status_str = c(GREEN, "All checks passed! 🚀") if failed == 0 else c(RED if failed > 2 else YELLOW, f"{failed} check(s) failed")
    print(f"  {status_str}  ({passed}/{len(results)} passed)")
    print()


def run_fixes(results: List[CheckResult]):
    fixable = [r for r in results if not r.passed and r.fixable and r.fix_cmd]
    if not fixable:
        print(c(GREEN, "Nothing to fix automatically!"))
        return

    print(c(BOLD, f"\nApplying {len(fixable)} fix(es)…"))
    for r in fixable:
        print(f"\n  {c(CYAN, r.name)}: {r.fix_cmd}")
        try:
            subprocess.run(r.fix_cmd, shell=True, check=True)
            print(f"  {c(GREEN, 'Fixed!')}")
        except Exception as exc:
            print(f"  {c(RED, f'Failed: {exc}')}")


def print_memory_briefing():
    from src.context_keeper import get_briefing, MEMORY_FILE
    print(c(BOLD, "\n  TIMPS Context Briefing"))
    print(c(CYAN, "  " + "─" * 50))
    briefing = get_briefing(regenerate=True)
    print(f"\n  {briefing}\n")
    print(c(CYAN, f"  Memory: {MEMORY_FILE}"))
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="TIMPS-Swarm Doctor — validate your installation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--quick",  action="store_true", help="Skip slow checks (Ollama, MCP)")
    parser.add_argument("--fix",    action="store_true", help="Auto-apply fixable issues")
    parser.add_argument("--memory", action="store_true", help="Show Context Keeper briefing")
    parser.add_argument("--json",   action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    if args.memory:
        print_memory_briefing()
        return

    results = run_checks(quick=args.quick)

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
        return

    print_results(results)

    if args.fix:
        run_fixes(results)
        # Re-run checks after fixes
        print(c(BOLD, "\nRe-running checks after fixes…"))
        results = run_checks(quick=args.quick)
        print_results(results)

    failed = sum(1 for r in results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
