#!/usr/bin/env python3
"""
Give work to TIMPS Swarm agents.

SDLC pipeline (code tasks):
  python3 give_work.py "Write a REST API for user auth"

Computer Health pipeline (system/environment tasks):
  python3 give_work.py "my wifi keeps dropping"
  python3 give_work.py "why is my laptop so slow"
  python3 give_work.py "broken python environment"
  python3 give_work.py --health                    # full checkup
  python3 give_work.py --health "fix my battery"  # targeted

Context Keeper & Agent Kernel:
  python3 give_work.py --brief                     # "what was I doing?" briefing
  python3 give_work.py --brief --refresh           # force-refresh the briefing
  python3 give_work.py --delegate "fix auth bug and add tests"
  python3 give_work.py --daemon                    # start background memory daemon
  python3 give_work.py --daemon --interval 120     # refresh every 2 minutes

SDLC with specific agents:
  python3 give_work.py --spawn code_generator qa_tester "Write and test a sort function"
"""
import asyncio
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.layer2_swarm_bridge import get_swarm_bridge, AgentRole

# Keywords that indicate a computer-health request (not a code task)
_HEALTH_KEYWORDS = [
    "slow", "battery", "drain", "wifi", "network", "dns", "latency",
    "crash", "log", "stack trace", "error log", "broken", "not found",
    "python env", "node env", "docker", "permission", "camera", "microphone",
    "update", "upgrade", "outdated", "security scan", "port", "firewall",
    "privacy", "cookie", "tracker", "photo", "video", "screenshot",
    "backup", "time machine", "uncommitted", "focus", "distraction", "tab",
    "files", "downloads", "desktop clutter", "duplicate", "organiz",
    "thermal", "fan", "jet engine", "startup", "bloat",
    # Expert / deep-diagnostic agents — use short stems so natural-language
    # variants like "dependencies for conflicts" or "my disk will be full" match.
    "depend",          # dependency, dependencies, check my dependencies
    "conflict",        # merge conflict, dependency conflicts
    "npm audit", "pip check", "lockfile", "version conflict",
    "tech debt", "cyclomatic", "code smell", "debt score",
    "migrate", "migration", "breaking change",
    "flaky test", "flakey", "intermittent test",
    "onboarding", "new developer", "new team member",
    "incident", "outage", "production down", "service down",
    "cloud cost", "terraform waste", "idle resource",
    "certificate", "cert expir", "tls", "ssl expir",
    "terraform plan", "tf plan", "tfplan",
    "dotfile", "zshrc", "bashrc", "shell slow",
    "disk full", "no space", "disk space", "disk",  # 'disk' catches 'when my disk will be full'
]


def _is_health_task(request: str) -> bool:
    """Return True if the request should be handled by the health pipeline."""
    rl = request.lower()
    return any(kw in rl for kw in _HEALTH_KEYWORDS)


def run_health(request: str, multi_agent: bool = False):
    """Run the computer-health pipeline for a request."""
    from src.computer_health_graph import run_health_task

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║              TIMPS COMPUTER HEALTH AGENTS                      ║
╚══════════════════════════════════════════════════════════════════╝

Request: {request}
Mode: {"Full checkup (6 agents)" if multi_agent else "Smart dispatch"}
""")

    result = run_health_task(request, multi_agent=multi_agent)

    print(f"✅ Agents run: {', '.join(result['agents_run'])}")
    print(f"\n📊 Health Summary:\n{result.get('health_summary', '(no summary)')}")

    if result.get("action_scripts"):
        print(f"\n📝 Action scripts saved to:")
        for s in result["action_scripts"]:
            print(f"   {s}")

    if result.get("reports"):
        print(f"\n📄 Detailed reports saved to:")
        for r in result["reports"]:
            if r.get("report_path"):
                print(f"   {r['report_path']}")

    if result.get("errors"):
        print(f"\n⚠️  Errors:")
        for e in result["errors"]:
            print(f"   {e}")

    return result


async def give_work(request: str, language: str = "python", wait: bool = True):
    """Give a task to the swarm."""
    bridge = get_swarm_bridge()
    
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                    GIVING WORK TO SWARM                       ║
╚══════════════════════════════════════════════════════════════════╝

Task: {request}
Language: {language}
""")
    
    # Show available agents
    agents = bridge.computer_manager.list_agents()
    print(f"Available agents: {agents['total']}/{agents['max']}")
    
    print("\n⚡ Running swarm...\n")
    
    task = await bridge.run_swarm_task(
        request=request,
        language=language,
        max_iterations=10,
        wait_for_completion=wait
    )
    
    print(f"Status: {task.status}")
    
    if task.status == "completed":
        print("\n✅ RESULTS:")
        if task.results.get("requirements"):
            print(f"\n📋 Requirements:\n{task.results['requirements'][:500]}")
        if task.results.get("architecture_plan"):
            print(f"\n🏗️ Architecture:\n{task.results['architecture_plan'][:500]}")
        if task.results.get("code_artifacts"):
            print(f"\n💻 Generated {len(task.results['code_artifacts'])} files:")
            for f in task.results['code_artifacts']:
                print(f"   - {f}")
        if task.results.get("test_results"):
            print(f"\n🧪 Tests:\n{task.results['test_results'][:500]}")
        if task.results.get("security_report"):
            print(f"\n🔒 Security:\n{task.results['security_report'][:500]}")
        if task.results.get("documentation"):
            print(f"\n📝 Docs:\n{task.results['documentation'][:500]}")
    else:
        print(f"\n❌ Error: {task.error}")
    
    return task


async def spawn_and_work(roles: list, task: str):
    """Spawn specific agents, write work files, and actively invoke each agent."""
    bridge = get_swarm_bridge()

    print(f"🚀 Spawning {len(roles)} agents...")
    agents = await bridge.spawn_agent_team(roles)

    for a in agents:
        print(f"  - {a.role.value} ({a.id})")

    print(f"\n💼 Giving task: {task}")

    results = []
    for agent in agents:
        print(f"\n📤 {agent.role.value}: starting work...")

        # Write the task file
        task_file = os.path.join(agent.computer.working_dir, "task.txt")
        with open(task_file, "w") as f:
            f.write(task)

        # Actually run the swarm task so the agent works rather than just getting a file
        sub_task = await bridge.run_swarm_task(
            request=task,
            language="python",
            max_iterations=5,
            wait_for_completion=True,
        )
        status_icon = "✅" if sub_task.status == "completed" else "❌"
        print(f"   {status_icon} {agent.role.value} → {sub_task.status}")

        # Also write the result back to the agent's directory
        result_path = os.path.join(agent.computer.working_dir, "result.json")
        import json
        with open(result_path, "w") as f:
            json.dump({
                "task": task,
                "status": sub_task.status,
                "artifacts": sub_task.artifacts,
                "error": sub_task.error,
            }, f, indent=2)

        results.append(sub_task)

    return results


def main():
    parser = argparse.ArgumentParser(description="Give work to TIMPS Swarm")
    parser.add_argument("task", nargs="?", help="Task to give to swarm")
    parser.add_argument("-l", "--language", default="python", help="Language (SDLC pipeline only)")
    parser.add_argument("--spawn", nargs="+", help="Spawn specific agents (e.g. code_generator qa_tester)")
    parser.add_argument(
        "--health", action="store_true",
        help="Force computer-health pipeline (multi-agent full checkup if no task specified)",
    )
    parser.add_argument("--brief", action="store_true", help="Print Context Keeper resumption briefing")
    parser.add_argument("--refresh", action="store_true", help="Force-refresh the Context Keeper cache (use with --brief)")
    parser.add_argument("--delegate", metavar="GOAL", help="Delegate a multi-step goal to the Agent Kernel")
    parser.add_argument("--daemon", action="store_true", help="Start Context Keeper background daemon")
    parser.add_argument("--interval", type=int, default=300, help="Daemon refresh interval in seconds (default: 300)")
    # ── Memory ────────────────────────────────────────────────────────────────
    parser.add_argument("--memory", action="store_true", help="Show agent memory summary (past runs + preferences)")
    # ── Auth / API key management ─────────────────────────────────────────────
    parser.add_argument("--keygen", metavar="LABEL", help="Generate a new API key with the given label")
    parser.add_argument("--keys", action="store_true", help="List all stored API keys")
    parser.add_argument("--revoke", metavar="HASH_PREFIX", help="Revoke a key by its hash prefix (from --keys)")
    args = parser.parse_args()

    task = args.task or ""

    # ── API key management ────────────────────────────────────────────────────
    if args.keygen:
        from src.auth import generate_key
        key = generate_key(label=args.keygen)
        print(f"\n✅ New API key generated for '{args.keygen}':")
        print(f"\n   {key}\n")
        print("⚠️  This is shown ONCE — save it now.\n")
        print("To use it, add to your MCP config (mcp.json) env section:")
        print(f'   "TIMPS_AUTH": "1",')
        print(f'   "TIMPS_API_KEY": "{key}"')
        print("\nOr pass it per tool call:  {{ \"_api_key\": \"<key>\", ... }}\n")
        return

    if args.keys:
        from src.auth import list_keys
        keys = list_keys()
        if not keys:
            print("No keys stored. Generate one with: python3 give_work.py --keygen \"your-name\"")
        else:
            print(f"\n{'Label':<20} {'Hash prefix':<16} {'Created':<22} {'Last used'}")
            print("-" * 76)
            for k in keys:
                print(f"{k['label']:<20} {k['hash_prefix']:<16} {k['created_at'][:19]:<22} {k['last_used_at']}")
            print()
        return

    if args.revoke:
        from src.auth import revoke_key
        if revoke_key(args.revoke):
            print(f"✅ Key with hash prefix '{args.revoke}' revoked.")
        else:
            print(f"❌ No key found with hash prefix '{args.revoke}'. Check: python3 give_work.py --keys")
        return

    # ── Memory summary ────────────────────────────────────────────────────────
    if args.memory:
        from src.memory import get_memory_summary
        print(get_memory_summary())
        return

    if args.daemon:
        from src.context_keeper import run_daemon
        print(f"🧠 Starting Context Keeper daemon (interval={args.interval}s) — Ctrl-C to stop")
        run_daemon(interval_seconds=args.interval)

    elif args.brief:
        from src.context_keeper import get_briefing
        import os
        briefing = get_briefing(cwd=os.getcwd(), regenerate=args.refresh)
        print(briefing)

    elif args.delegate:
        from src.agent_kernel import delegate
        import os, json as _json
        print(f"🤖 Delegating goal to Agent Kernel: {args.delegate}")
        result = delegate(args.delegate, context={"cwd": os.getcwd()})
        print(f"\n✅ Run ID  : {result['run_id']}")
        print(f"   Status  : {result['status']}")
        print(f"   Tasks   : {result['tasks_done']}/{result['tasks_total']} done, {result['tasks_failed']} failed")
        if result.get("final_report"):
            print(f"\n{result['final_report']}")
        if result.get("artifacts"):
            print("\n📎 Artifacts: " + ", ".join(result["artifacts"]))

    elif args.spawn:
        roles = [AgentRole(r.replace("-", "_")) for r in args.spawn]
        asyncio.run(spawn_and_work(roles, task or "do your work"))

    elif args.health or (task and _is_health_task(task)):
        multi = args.health and not task   # --health with no task = full checkup
        run_health(task or "full system checkup", multi_agent=multi)

    elif task:
        asyncio.run(give_work(task, args.language))

    else:
        print(
            "Usage:\n"
            "  # Code tasks (SDLC pipeline):\n"
            "  python3 give_work.py \"Write a hello function\"\n"
            "  python3 give_work.py \"Fix the auth bug\" -l javascript\n"
            "  python3 give_work.py --spawn code_generator qa_tester \"Write code and test it\"\n\n"
            "  # Computer health tasks (auto-detected or explicit):\n"
            "  python3 give_work.py \"why is my laptop so slow\"\n"
            "  python3 give_work.py \"my wifi keeps dropping\"\n"
            "  python3 give_work.py \"broken python environment\"\n"
            "  python3 give_work.py --health               # full checkup\n"
            "  python3 give_work.py --health \"fix my battery\"\n\n"
            "  # Context Keeper & Agent Kernel:\n"
            "  python3 give_work.py --brief                # what was I doing?\n"
            "  python3 give_work.py --brief --refresh      # force-refresh briefing\n"
            "  python3 give_work.py --delegate \"fix auth bug and add tests\"\n"
            "  python3 give_work.py --daemon               # start memory daemon\n"
            "  python3 give_work.py --daemon --interval 120\n\n"
            "  # Memory & Auth:\n"
            "  python3 give_work.py --memory               # show past runs + prefs\n"
            "  python3 give_work.py --keygen \"my-laptop\"   # generate API key\n"
            "  python3 give_work.py --keys                 # list stored keys\n"
            "  python3 give_work.py --revoke abc123        # revoke a key\n"
        )


if __name__ == "__main__":
    main()