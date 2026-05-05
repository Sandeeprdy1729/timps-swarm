#!/usr/bin/env python3
"""
Quick self-test for the MCP server.
Sends real JSON-RPC messages via subprocess and validates responses.

Run: python3 mcp_server/test_server.py
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def send_message(proc, msg: dict) -> dict:
    line = json.dumps(msg) + "\n"
    proc.stdin.write(line.encode())
    proc.stdin.flush()
    response_line = proc.stdout.readline()
    return json.loads(response_line)


def main():
    print("Starting TIMPS MCP server for testing…")
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        cwd=str(REPO),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    tests_passed = 0
    tests_failed = 0

    def check(label: str, condition: bool):
        nonlocal tests_passed, tests_failed
        if condition:
            print(f"  ✅  {label}")
            tests_passed += 1
        else:
            print(f"  ❌  {label}")
            tests_failed += 1

    # ── 1. initialize ─────────────────────────────────────────────────────────
    print("\n[1] initialize")
    resp = send_message(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test"}},
    })
    check("has result", "result" in resp)
    check("serverInfo.name == timps-swarm", resp.get("result", {}).get("serverInfo", {}).get("name") == "timps-swarm")
    check("protocolVersion present", "protocolVersion" in resp.get("result", {}))

    # ── 2. tools/list ────────────────────────────────────────────────────────
    print("\n[2] tools/list")
    resp = send_message(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = resp.get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}
    check("returns 31 tools", len(tools) == 31)
    check("timps_dispatch present", "timps_dispatch" in tool_names)
    check("timps_environment_doctor present", "timps_environment_doctor" in tool_names)
    check("timps_run_task present", "timps_run_task" in tool_names)
    check("timps_full_checkup present", "timps_full_checkup" in tool_names)
    check("all tools have inputSchema", all("inputSchema" in t for t in tools))

    # ── 3. timps_list_agents ─────────────────────────────────────────────────
    print("\n[3] timps_list_agents")
    resp = send_message(proc, {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "timps_list_agents", "arguments": {}},
    })
    content = resp.get("result", {}).get("content", [{}])[0].get("text", "")
    check("returns text content", bool(content))
    check("mentions system_optimizer", "system_optimizer" in content)
    check("mentions code_generator",   "code_generator"   in content)

    # ── 4. timps_environment_doctor (real system data) ───────────────────────
    print("\n[4] timps_environment_doctor (real execution)")
    resp = send_message(proc, {
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "timps_environment_doctor", "arguments": {}},
    })
    content = resp.get("result", {}).get("content", [{}])[0].get("text", "")
    check("returns text content", bool(content))
    check("not an error response", not resp.get("result", {}).get("isError", False))
    check("report saved (path mentioned)", "report" in content.lower())

    # ── 5. unknown tool ──────────────────────────────────────────────────────
    print("\n[5] unknown tool → error")
    resp = send_message(proc, {
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "timps_does_not_exist", "arguments": {}},
    })
    check("returns error for unknown tool", "error" in resp)

    # ── 6. ping ──────────────────────────────────────────────────────────────
    print("\n[6] ping")
    resp = send_message(proc, {"jsonrpc": "2.0", "id": 6, "method": "ping", "params": {}})
    check("responds to ping", "result" in resp)

    proc.terminate()

    print(f"\n{'='*50}")
    print(f"Results: {tests_passed} passed, {tests_failed} failed")
    sys.exit(0 if tests_failed == 0 else 1)


if __name__ == "__main__":
    main()
