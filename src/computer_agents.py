"""
TIMPS Swarm — Computer Health Agents

12 new agent nodes that diagnose and fix real daily computer problems.
Each agent:
  1. Gathers real system data via system_tools
  2. Sends it to the LLM for analysis and actionable recommendations
  3. Saves a Markdown report to generated/reports/
  4. Optionally generates a dry-run action script the user can review

Node functions are standalone — they do NOT require the 10-agent SDLC pipeline.
They operate on ComputerHealthState (see state.py).

Quick reference:
  system_optimizer_node   — slow laptop, startup bloat, thermal throttling
  file_organizer_node     — downloads chaos, duplicates, 40GB photos
  environment_doctor_node — broken npm/python/PATH/Docker
  security_guard_node     — camera/mic permissions, open ports
  network_medic_node      — WiFi drops, DNS issues, localhost refused
  battery_analyst_node    — zombie apps draining battery
  update_manager_node     — pending OS/app/library updates
  log_interpreter_node    — crash logs, stack traces
  privacy_cleaner_node    — browser trackers, app permissions
  media_librarian_node    — unnamed photos, oversized videos
  backup_sentinel_node    — unknown backup status, untracked files
  context_switcher_node   — 47 tabs, 5 projects, notification spam
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from src.system_tools import (
    SystemScanner, FileScanner, EnvironmentInspector, BatteryMonitor,
    NetworkDiagnostics, LogReader, PrivacyAuditor, BackupChecker,
    UpdateChecker, MediaScanner, ContextAnalyzer,
)

logger = logging.getLogger(__name__)

GENERATED_DIR = Path("generated/reports")
SCRIPTS_DIR   = Path("generated/scripts")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _router():
    """Lazy import to avoid circular deps."""
    from src.llm_router import LLMRouter
    return LLMRouter()


def _save_report(filename: str, content: str) -> str:
    """Persist a Markdown report and return its path."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path = GENERATED_DIR / filename
    path.write_text(content, encoding="utf-8")
    logger.info("[computer_agents] Report saved: %s", path)
    return str(path)


def _save_script(filename: str, content: str) -> str:
    """Persist a shell action script and return its path."""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / filename
    path.write_text(content, encoding="utf-8")
    os.chmod(str(path), 0o644)   # read-only until user reviews
    logger.info("[computer_agents] Script saved: %s", path)
    return str(path)


def _call_llm(agent_name: str, system_prompt: str, data_context: str) -> str:
    """Call the LLM router; return raw text or a fallback message."""
    try:
        return _router().call(agent_name, data_context, system_prompt=system_prompt)
    except Exception as exc:
        logger.warning("[computer_agents] LLM call failed for %s: %s", agent_name, exc)
        return f"[LLM unavailable — raw data follows]\n\n{data_context[:2000]}"


def _truncate(obj: Any, max_chars: int = 4000) -> str:
    s = json.dumps(obj, indent=2, default=str) if not isinstance(obj, str) else obj
    return s[:max_chars] + ("…" if len(s) > max_chars else "")


# ---------------------------------------------------------------------------
# 1. System Optimizer
# ---------------------------------------------------------------------------

def system_optimizer_node(state: Dict) -> Dict:
    """
    Diagnose slow-laptop symptoms: CPU hogs, excessive startup items,
    thermal throttling, memory pressure.
    """
    logger.info("[system_optimizer] Starting system scan…")
    scanner = SystemScanner()

    summary   = scanner.get_system_summary()
    processes = scanner.list_processes(top_n=20)
    startup   = scanner.get_startup_items()
    thermal   = scanner.get_thermal_info()

    context = (
        f"## System Summary\n{_truncate(summary, 800)}\n\n"
        f"## Top Processes by CPU\n{_truncate(processes, 1500)}\n\n"
        f"## Startup Items ({len(startup)} found)\n{_truncate(startup, 1000)}\n\n"
        f"## Thermal / Power\n{_truncate(thermal, 600)}\n"
    )

    system_prompt = (
        "You are a macOS/Linux system performance expert. "
        "Analyse the real system data provided and:\n"
        "1. Identify the top 3 performance bottlenecks\n"
        "2. Name specific processes/startup items to disable or kill\n"
        "3. Give exact terminal commands the user can run\n"
        "4. Explain in plain English why the laptop might feel slow\n"
        "Format as a clear Markdown report with ## headers."
    )

    report = _call_llm("system_optimizer", system_prompt, context)
    cleanup_script = scanner.generate_cleanup_script(startup)

    report_path = _save_report("system_optimizer_report.md", f"# System Optimizer Report\n\n{report}")
    script_path = _save_script("system_cleanup.sh", cleanup_script)

    return {
        "agent": "system_optimizer",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {"summary": summary, "process_count": len(processes), "startup_count": len(startup)},
    }


# ---------------------------------------------------------------------------
# 2. File Organizer
# ---------------------------------------------------------------------------

def file_organizer_node(state: Dict) -> Dict:
    """
    Scan Downloads + Desktop for chaos: duplicates, large files, junk.
    Generate an organiser plan (dry-run, no files moved).
    """
    logger.info("[file_organizer] Scanning Downloads and Desktop…")
    scanner = FileScanner()
    home = str(Path.home())

    targets = [
        str(Path.home() / "Downloads"),
        str(Path.home() / "Desktop"),
    ]

    summaries, large_files, plan_all = {}, [], {}
    for target in targets:
        label = Path(target).name
        summaries[label] = scanner.scan_directory_summary(target)
        large_files.extend(scanner.get_large_files(target, min_size_mb=25.0))
        plan_all.update(scanner.generate_organizer_preview(target))

    downloads_path = str(Path.home() / "Downloads")
    dupes = scanner.find_duplicates(downloads_path, min_size_kb=100)

    context = (
        f"## Directory Summaries\n{_truncate(summaries, 800)}\n\n"
        f"## Large Files (>25 MB, top 20)\n{_truncate(sorted(large_files, key=lambda x: x['size_mb'], reverse=True)[:20], 1200)}\n\n"
        f"## Duplicate Files Found: {len(dupes)} groups\n{_truncate(dict(list(dupes.items())[:10]), 800)}\n\n"
        f"## Organisation Plan Preview\n{_truncate(plan_all, 1000)}\n"
    )

    system_prompt = (
        "You are a file organisation expert. Given the real scan data:\n"
        "1. Summarise the clutter situation (e.g. '2.3 GB in Downloads, 47 duplicates')\n"
        "2. Highlight the top space wasters\n"
        "3. Explain the proposed folder structure from the plan\n"
        "4. Flag any files that look like they should be deleted vs kept\n"
        "5. Estimate how much space could be freed\n"
        "Format as a Markdown report. Do NOT suggest moving files yourself — the script handles that."
    )

    report = _call_llm("file_organizer", system_prompt, context)
    script_content = scanner.generate_move_script(plan_all, str(Path.home() / "Organised"))

    report_path = _save_report("file_organizer_report.md", f"# File Organizer Report\n\n{report}")
    script_path = _save_script("organize_files.sh", script_content)

    return {
        "agent": "file_organizer",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {"summaries": summaries, "large_file_count": len(large_files), "duplicate_groups": len(dupes)},
    }


# ---------------------------------------------------------------------------
# 3. Environment Doctor
# ---------------------------------------------------------------------------

def environment_doctor_node(state: Dict) -> Dict:
    """
    Diagnose broken dev environments: Python/Node/Docker/Git/PATH issues.
    """
    logger.info("[environment_doctor] Running full environment diagnosis…")
    inspector = EnvironmentInspector()

    diagnosis = inspector.full_diagnosis()
    fix_commands = inspector.generate_fix_commands(diagnosis)

    context = (
        f"## Full Environment Diagnosis\n{_truncate(diagnosis, 3500)}\n\n"
        f"## Detected Issues (auto-extracted)\n"
        + ("\n".join(f"- {c}" for c in fix_commands) or "No obvious issues detected")
    )

    system_prompt = (
        "You are a senior DevOps engineer and environment troubleshooter. "
        "Given the real environment diagnosis data:\n"
        "1. Identify every broken tool or misconfiguration\n"
        "2. Explain EXACTLY why each problem occurs (e.g. 'node version 14 is EOL')\n"
        "3. Give the exact commands to fix each issue, in order\n"
        "4. Warn about any PATH issues that could shadow the wrong binaries\n"
        "5. If Docker isn't running, explain how to start it\n"
        "Format as a Markdown report with a '## Fix Commands' section at the end."
    )

    report = _call_llm("environment_doctor", system_prompt, context)

    # Build a fix script from the extracted issues
    script_lines = [
        "#!/bin/bash",
        "# TIMPS Environment Doctor — Fix Script (DRY RUN)",
        "# Review and remove # prefix from lines you want to execute",
        "",
    ]
    for cmd in fix_commands:
        script_lines.append(f"# {cmd}")

    report_path = _save_report("environment_doctor_report.md", f"# Environment Doctor Report\n\n{report}")
    script_path = _save_script("fix_environment.sh", "\n".join(script_lines))

    return {
        "agent": "environment_doctor",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {"diagnosis": diagnosis, "issues_count": len(fix_commands)},
    }


# ---------------------------------------------------------------------------
# 4. Security Guard
# ---------------------------------------------------------------------------

def security_guard_node(state: Dict) -> Dict:
    """
    Deep security scan: open ports, process anomalies, app permissions,
    and camera/mic access.
    """
    logger.info("[security_guard] Running security scan…")
    scanner  = SystemScanner()
    net_diag = NetworkDiagnostics()
    privacy  = PrivacyAuditor()

    processes    = scanner.list_processes(top_n=30)
    open_ports   = net_diag.get_open_ports()
    permissions  = privacy.get_app_permissions()

    # Flag suspicious process names
    suspicious_keywords = ["miner", "keylog", "crypto", "backdoor", "exploit", "shell", "nc ", "ncat", "socat"]
    suspicious_procs = [
        p for p in processes
        if any(kw in (p.get("name") or "").lower() for kw in suspicious_keywords)
    ]

    context = (
        f"## Running Processes (top 30 by CPU)\n{_truncate(processes, 1500)}\n\n"
        f"## Open Listening Ports\n{_truncate(open_ports, 1000)}\n\n"
        f"## App Permissions (Camera/Mic/Location)\n{_truncate(permissions, 1200)}\n\n"
        f"## Suspicious Process Flags\n{_truncate(suspicious_procs, 500)}\n"
    )

    system_prompt = (
        "You are a macOS/Linux security analyst. Review the real system data and:\n"
        "1. Flag any open ports that should not be publicly listening\n"
        "2. Identify any apps with unexpected camera/mic/location access\n"
        "3. Note any suspicious processes\n"
        "4. Give CVSS-style severity ratings (Low/Medium/High/Critical)\n"
        "5. Provide exact mitigation commands\n"
        "Format as a security report with a risk summary table at the top."
    )

    report = _call_llm("security_guard", system_prompt, context)
    report_path = _save_report("security_guard_report.md", f"# Security Guard Report\n\n{report}")

    return {
        "agent": "security_guard",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "open_port_count": len(open_ports),
            "suspicious_process_count": len(suspicious_procs),
            "permission_services": list(permissions.keys()) if isinstance(permissions, dict) else [],
        },
    }


# ---------------------------------------------------------------------------
# 5. Network Medic
# ---------------------------------------------------------------------------

def network_medic_node(state: Dict) -> Dict:
    """
    Diagnose WiFi drops, DNS failures, high latency, refused connections.
    """
    logger.info("[network_medic] Running network diagnostics…")
    net = NetworkDiagnostics()

    internet_ping = net.ping("8.8.8.8")
    cloudflare    = net.ping("1.1.1.1")
    dns_check     = net.check_dns("google.com")
    wifi_info     = net.check_wifi_info()
    open_ports    = net.get_open_ports()[:15]

    # Traceroute only if internet is reachable (saves time)
    traceroute = ""
    if internet_ping.get("reachable"):
        traceroute = net.run_traceroute("8.8.8.8")

    context = (
        f"## Internet Ping (8.8.8.8)\n{_truncate(internet_ping, 400)}\n\n"
        f"## Cloudflare Ping (1.1.1.1)\n{_truncate(cloudflare, 400)}\n\n"
        f"## DNS Resolution (google.com)\n{_truncate(dns_check, 300)}\n\n"
        f"## WiFi Info\n{_truncate(wifi_info, 600)}\n\n"
        f"## Open Listening Ports\n{_truncate(open_ports, 600)}\n\n"
        f"## Traceroute (first 15 hops)\n{traceroute[:1200]}\n"
    )

    system_prompt = (
        "You are a network engineer. Based on the real network diagnostics:\n"
        "1. Determine if the internet connection is healthy\n"
        "2. Identify any DNS issues and suggest alternative DNS servers (1.1.1.1 or 8.8.8.8)\n"
        "3. Diagnose any WiFi signal or configuration problems\n"
        "4. Identify unusual latency or packet loss hops in the traceroute\n"
        "5. Suggest exact commands to flush DNS cache, reset network settings, or test specific ports\n"
        "Format as a Markdown report with a quick health summary at the top."
    )

    report = _call_llm("network_medic", system_prompt, context)

    # Generate common fix commands
    fix_script_lines = [
        "#!/bin/bash",
        "# TIMPS Network Medic — Common Fixes (DRY RUN)",
        "",
        "# Flush DNS cache (macOS)",
        "# sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder",
        "",
        "# Flush DNS cache (Linux systemd-resolve)",
        "# sudo systemd-resolve --flush-caches",
        "",
        "# Reset WiFi (macOS)",
        "# networksetup -setairportpower en0 off && networksetup -setairportpower en0 on",
        "",
        "# Test if port is open on a host",
        "# nc -zv <host> <port>",
        "",
        "# Release and renew DHCP (macOS)",
        "# sudo ipconfig set en0 DHCP",
    ]

    report_path = _save_report("network_medic_report.md", f"# Network Medic Report\n\n{report}")
    script_path = _save_script("fix_network.sh", "\n".join(fix_script_lines))

    return {
        "agent": "network_medic",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "internet_reachable": internet_ping.get("reachable"),
            "packet_loss_pct": internet_ping.get("packet_loss_pct"),
            "avg_rtt_ms": internet_ping.get("avg_rtt_ms"),
            "dns_ok": dns_check.get("resolves"),
        },
    }


# ---------------------------------------------------------------------------
# 6. Battery Analyst
# ---------------------------------------------------------------------------

def battery_analyst_node(state: Dict) -> Dict:
    """
    Identify battery drainers and report battery health.
    """
    logger.info("[battery_analyst] Scanning battery and energy consumers…")
    monitor = BatteryMonitor()

    battery_status     = monitor.get_battery_status()
    energy_consumers   = monitor.get_top_energy_consumers(n=15)
    battery_history    = monitor.get_macos_battery_history()

    context = (
        f"## Battery Status\n{_truncate(battery_status, 400)}\n\n"
        f"## Top Energy Consumers (by CPU%)\n{_truncate(energy_consumers, 1500)}\n\n"
        f"## Battery Health / Cycle Count\n{battery_history[:600]}\n"
    )

    system_prompt = (
        "You are a battery optimization expert. Based on real system data:\n"
        "1. Identify the top 3 'energy vampire' processes\n"
        "2. Estimate roughly how much battery life each is wasting\n"
        "3. Explain whether the battery health is good or degraded\n"
        "4. Give actionable commands to kill specific background processes\n"
        "5. Suggest macOS/Linux power settings to extend battery life\n"
        "Format as a Markdown report. Be specific with process names."
    )

    report = _call_llm("battery_analyst", system_prompt, context)

    # Generate kill commands for top CPU consumers
    kill_lines = [
        "#!/bin/bash",
        "# TIMPS Battery Analyst — Kill Energy Vampires (DRY RUN)",
        "# Remove # prefix to execute",
        "",
    ]
    for proc in energy_consumers[:5]:
        if isinstance(proc, dict) and proc.get("pid"):
            kill_lines.append(f"# kill -TERM {proc['pid']}  # {proc.get('name', 'unknown')} ({proc.get('cpu_pct', 0)}% CPU)")

    report_path = _save_report("battery_analyst_report.md", f"# Battery Analyst Report\n\n{report}")
    script_path = _save_script("kill_energy_vampires.sh", "\n".join(kill_lines))

    return {
        "agent": "battery_analyst",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "battery_pct": battery_status.get("percent"),
            "plugged_in": battery_status.get("plugged_in"),
            "hours_left": battery_status.get("hours_left"),
            "top_consumer": energy_consumers[0].get("name") if energy_consumers and isinstance(energy_consumers[0], dict) else None,
        },
    }


# ---------------------------------------------------------------------------
# 7. Update Manager
# ---------------------------------------------------------------------------

def update_manager_node(state: Dict) -> Dict:
    """
    Check for pending updates: OS, Homebrew, pip, npm.
    Generate a safe, ordered update script.
    """
    logger.info("[update_manager] Checking for updates…")
    checker = UpdateChecker()

    results = checker.full_check()

    # Summarise update counts
    brew_count = len(results.get("brew", {}).get("packages", "").splitlines()) if results.get("brew", {}).get("available") else 0
    npm_pkg    = results.get("npm", {}).get("packages", {})
    npm_count  = len(npm_pkg) if isinstance(npm_pkg, dict) else 0
    pip_pkg    = results.get("pip", {}).get("packages", [])
    pip_count  = len(pip_pkg) if isinstance(pip_pkg, list) else 0

    context = (
        f"## Homebrew Updates (~{brew_count} packages)\n{_truncate(results.get('brew', {}), 800)}\n\n"
        f"## NPM Global Updates ({npm_count} packages)\n{_truncate(results.get('npm', {}), 800)}\n\n"
        f"## pip Updates ({pip_count} packages)\n{_truncate(results.get('pip', {}), 800)}\n\n"
        f"## OS Updates\n{_truncate(results.get('os', {}), 600)}\n"
    )

    system_prompt = (
        "You are a software update advisor. Given real update data:\n"
        "1. Categorise updates as: Security (must update), Recommended, Optional\n"
        "2. Flag any packages with known vulnerabilities\n"
        "3. Warn about breaking changes (e.g. major version bumps)\n"
        "4. Recommend the safest update order (OS → system tools → app packages)\n"
        "5. Estimate total update time\n"
        "Format as a Markdown report with a prioritised update table."
    )

    report = _call_llm("update_manager", system_prompt, context)
    update_script = checker.generate_update_script(results)

    report_path = _save_report("update_manager_report.md", f"# Update Manager Report\n\n{report}")
    script_path = _save_script("run_updates.sh", update_script)

    return {
        "agent": "update_manager",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "brew_updates": brew_count,
            "npm_updates": npm_count,
            "pip_updates": pip_count,
            "os_updates_available": results.get("os", {}).get("available", False),
        },
    }


# ---------------------------------------------------------------------------
# 8. Log Interpreter
# ---------------------------------------------------------------------------

def log_interpreter_node(state: Dict) -> Dict:
    """
    Read crash logs and system logs, extract stack traces, explain in plain English.
    """
    logger.info("[log_interpreter] Reading crash logs and system log…")
    reader = LogReader()

    crash_logs = reader.read_crash_logs(max_logs=3)
    sys_log    = reader.read_system_log(lines=80)

    # Extract stack traces from all crash logs
    all_traces = []
    for log in crash_logs:
        traces = reader.extract_stack_traces(log.get("content", ""))
        all_traces.extend(traces[:2])

    # User-provided log path via state
    user_log_path = state.get("user_request", "")
    user_log_content = ""
    if user_log_path and Path(user_log_path).exists():
        user_log_content = reader.read_log_file(user_log_path)

    context = (
        f"## Recent Crash Logs ({len(crash_logs)} files found)\n"
        + "\n\n".join(
            f"### {log['file']}\n{log['content'][:1500]}" for log in crash_logs
        )
        + f"\n\n## System Log (last 80 lines, errors/faults only)\n{sys_log[:2000]}\n\n"
        f"## Extracted Stack Traces\n" + ("\n\n".join(f"```\n{t}\n```" for t in all_traces[:3]) or "None found")
        + (f"\n\n## User-Provided Log\n{user_log_content[:2000]}" if user_log_content else "")
    )

    system_prompt = (
        "You are a debugging expert. Given real crash logs and stack traces:\n"
        "1. Identify the root cause of each crash in plain English\n"
        "2. Name the specific app, service, or library that crashed\n"
        "3. Classify crashes as: App bug, macOS bug, Hardware issue, or User error\n"
        "4. Give exact steps to reproduce and fix each crash\n"
        "5. If any crash is security-related, flag it prominently\n"
        "Format as a Markdown report. Translate technical crash messages into simple language."
    )

    report = _call_llm("log_interpreter", system_prompt, context)
    report_path = _save_report("log_interpreter_report.md", f"# Log Interpreter Report\n\n{report}")

    return {
        "agent": "log_interpreter",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "crash_log_count": len(crash_logs),
            "stack_traces_found": len(all_traces),
            "crash_files": [log["file"] for log in crash_logs],
        },
    }


# ---------------------------------------------------------------------------
# 9. Privacy Cleaner
# ---------------------------------------------------------------------------

def privacy_cleaner_node(state: Dict) -> Dict:
    """
    Audit browser cookies, app permissions (camera/mic/location).
    Generate a cleanup manifest — no data deleted until user approves.
    """
    logger.info("[privacy_cleaner] Auditing privacy settings…")
    auditor = PrivacyAuditor()

    cookie_stats = auditor.get_browser_cookie_stats()
    permissions  = auditor.get_app_permissions()

    total_cookies = sum(
        v.get("cookie_count", 0)
        for v in cookie_stats.values()
        if isinstance(v.get("cookie_count"), int)
    )

    context = (
        f"## Browser Cookie Statistics (total ~{total_cookies:,})\n{_truncate(cookie_stats, 1200)}\n\n"
        f"## App Permissions (Camera, Mic, Location, Contacts…)\n{_truncate(permissions, 2000)}\n"
    )

    system_prompt = (
        "You are a privacy security auditor. Given real permission and cookie data:\n"
        "1. Flag any apps with unexpected camera/microphone/location access\n"
        "2. Identify browsers with excessive cookies (>500 as 'high', >2000 as 'very high')\n"
        "3. Point out any permissions that look like spyware patterns\n"
        "4. Recommend specific settings to change (with navigation path, e.g. System Settings > Privacy)\n"
        "5. Explain what each permission type means in plain language\n"
        "Format as a Markdown report with a risk table."
    )

    report = _call_llm("privacy_cleaner", system_prompt, context)
    cleanup_manifest = auditor.generate_cleanup_manifest(cookie_stats)

    report_path = _save_report("privacy_cleaner_report.md", f"# Privacy Cleaner Report\n\n{report}")
    script_path = _save_script("privacy_cleanup_manifest.md", cleanup_manifest)

    return {
        "agent": "privacy_cleaner",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "total_cookies": total_cookies,
            "browsers_scanned": list(cookie_stats.keys()),
            "permission_services": list(permissions.keys()) if isinstance(permissions, dict) else [],
        },
    }


# ---------------------------------------------------------------------------
# 10. Media Librarian
# ---------------------------------------------------------------------------

def media_librarian_node(state: Dict) -> Dict:
    """
    Scan Photos/Downloads/Desktop for unnamed photos, duplicate images,
    and oversized videos. Generate a rename + compress plan (dry-run).
    """
    logger.info("[media_librarian] Scanning media files…")
    scanner = MediaScanner()

    # Scan likely media locations
    search_dirs = [
        str(Path.home() / "Pictures"),
        str(Path.home() / "Downloads"),
        str(Path.home() / "Desktop"),
    ]

    total_stats: Dict[str, Any] = {"photos": {"count": 0, "size_mb": 0.0}, "videos": {"count": 0, "size_mb": 0.0}, "total_size_mb": 0.0}
    all_screenshots = []
    all_large_videos = []

    for d in search_dirs:
        if Path(d).exists():
            s = scanner.scan_media(d)
            total_stats["photos"]["count"] += s["photos"]["count"]
            total_stats["photos"]["size_mb"] += s["photos"]["size_mb"]
            total_stats["videos"]["count"] += s["videos"]["count"]
            total_stats["videos"]["size_mb"] += s["videos"]["size_mb"]
            total_stats["total_size_mb"] += s["total_size_mb"]
            all_screenshots.extend(scanner.find_screenshots(d))
            all_large_videos.extend(scanner.get_large_videos(d, min_size_mb=50.0))

    rename_plan = scanner.suggest_rename_plan([s["path"] for s in all_screenshots[:20]])

    context = (
        f"## Media Summary Across {search_dirs}\n{_truncate(total_stats, 600)}\n\n"
        f"## Screenshots Found ({len(all_screenshots)})\n{_truncate(all_screenshots[:20], 1000)}\n\n"
        f"## Large Videos >50 MB ({len(all_large_videos)})\n{_truncate(all_large_videos[:15], 1000)}\n\n"
        f"## Suggested Rename Plan ({len(rename_plan)} files)\n{_truncate(rename_plan[:10], 800)}\n"
    )

    system_prompt = (
        "You are a digital media organiser. Based on real file scan data:\n"
        "1. Summarise the total media footprint (how many GB of photos/videos)\n"
        "2. Identify which videos are best candidates for compression and by how much (h264 CRF 28 saves ~60%)\n"
        "3. Explain the screenshot backlog and suggest a naming convention\n"
        "4. Recommend a folder structure (e.g. Photos/2024/YYYY-MM/)\n"
        "5. Estimate how much space the compression + organisation would free\n"
        "Format as a Markdown report."
    )

    report = _call_llm("media_librarian", system_prompt, context)
    compress_script = scanner.generate_compress_script(all_large_videos[:10])

    report_path = _save_report("media_librarian_report.md", f"# Media Librarian Report\n\n{report}")
    script_path = _save_script("compress_videos.sh", compress_script)

    return {
        "agent": "media_librarian",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "total_photos": total_stats["photos"]["count"],
            "total_videos": total_stats["videos"]["count"],
            "total_size_mb": round(total_stats["total_size_mb"], 1),
            "screenshots_count": len(all_screenshots),
            "large_videos_count": len(all_large_videos),
        },
    }


# ---------------------------------------------------------------------------
# 11. Backup Sentinel
# ---------------------------------------------------------------------------

def backup_sentinel_node(state: Dict) -> Dict:
    """
    Audit backup health: Time Machine status, uncommitted git repos,
    files at risk (Desktop/Documents not in git or cloud).
    """
    logger.info("[backup_sentinel] Auditing backup status…")
    checker = BackupChecker()

    time_machine  = checker.check_time_machine()
    git_repos     = checker.scan_git_repos()
    risky_files   = checker.get_risky_files()

    repos_with_changes  = [r for r in git_repos if r.get("uncommitted_changes")]
    repos_with_unpushed = [r for r in git_repos if r.get("unpushed_commits", "0").strip() != "0"]

    context = (
        f"## Time Machine Status\n{_truncate(time_machine, 500)}\n\n"
        f"## Git Repositories ({len(git_repos)} found)\n"
        f"- With uncommitted changes: {len(repos_with_changes)}\n"
        f"- With unpushed commits: {len(repos_with_unpushed)}\n"
        f"{_truncate(git_repos[:10], 1200)}\n\n"
        f"## At-Risk Files (Desktop/Documents, not in git/cloud, top 20)\n{_truncate(risky_files, 1000)}\n"
    )

    system_prompt = (
        "You are a data protection advisor. Based on real backup audit data:\n"
        "1. Assess the overall backup health (Good / Warning / Critical)\n"
        "2. List specific files or repos that have NEVER been backed up\n"
        "3. Calculate how much data is 'at risk' in total\n"
        "4. Explain how long ago the last Time Machine backup was\n"
        "5. Give exact git commands to push uncommitted/unpushed work\n"
        "6. Suggest a simple backup strategy for untracked files\n"
        "Format as a Markdown report with a risk score (0-10)."
    )

    report = _call_llm("backup_sentinel", system_prompt, context)
    backup_script = checker.generate_backup_script(risky_files)

    report_path = _save_report("backup_sentinel_report.md", f"# Backup Sentinel Report\n\n{report}")
    script_path = _save_script("backup_at_risk.sh", backup_script)

    return {
        "agent": "backup_sentinel",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "time_machine_latest": time_machine.get("latest_backup", "unknown"),
            "repos_scanned": len(git_repos),
            "repos_with_changes": len(repos_with_changes),
            "repos_with_unpushed": len(repos_with_unpushed),
            "risky_file_count": len(risky_files),
        },
    }


# ---------------------------------------------------------------------------
# 12. Context Switcher
# ---------------------------------------------------------------------------

def context_switcher_node(state: Dict) -> Dict:
    """
    Analyse current work context: open apps, browser tabs, git state.
    Generate a 'focus mode' session plan and distraction elimination script.
    """
    logger.info("[context_switcher] Analysing current work context…")
    analyzer = ContextAnalyzer()

    active_windows = analyzer.get_active_windows()
    tab_counts     = analyzer.get_open_browser_tabs_count()
    git_context    = analyzer.get_git_working_context()

    # Classify apps as work vs distraction
    distraction_apps = {
        "Slack", "Discord", "WhatsApp", "Telegram", "Messages",
        "Twitter", "X", "Reddit", "YouTube", "Netflix", "Spotify",
        "Mail", "Notion", "Obsidian",
    }
    work_apps = {"Terminal", "iTerm2", "VS Code", "Xcode", "Cursor", "PyCharm", "Vim", "Emacs"}

    open_app_names = {w.get("app", "") for w in active_windows}
    distractors = list(open_app_names & distraction_apps)
    workers     = list(open_app_names & work_apps)

    focus_script = analyzer.generate_focus_script(distractors)

    context = (
        f"## Active Applications ({len(active_windows)} open)\n{_truncate(active_windows[:30], 800)}\n\n"
        f"## Detected Distractors\n{distractors or 'None detected'}\n\n"
        f"## Work Applications Open\n{workers or 'None detected'}\n\n"
        f"## Browser Tab Estimates\n{_truncate(tab_counts, 300)}\n\n"
        f"## Current Git Context\n{_truncate(git_context, 500)}\n"
    )

    system_prompt = (
        "You are a productivity coach and context management expert. Based on real system state:\n"
        "1. Describe the current 'cognitive load' — how scattered is the user's attention?\n"
        "2. Name the specific distraction apps that should be closed for focus\n"
        "3. Suggest a focus session structure (e.g. '90-min deep work: close X, Y, Z; set timer')\n"
        "4. If in a git repo, remind the user what they were working on based on branch name and recent commits\n"
        "5. Recommend keyboard shortcuts or tools (e.g. Raycast, One Switch) for faster context switching\n"
        "Format as a Markdown productivity report."
    )

    report = _call_llm("context_switcher", system_prompt, context)

    report_path = _save_report("context_switcher_report.md", f"# Context Switcher Report\n\n{report}")
    script_path = _save_script("enter_focus_mode.sh", focus_script)

    return {
        "agent": "context_switcher",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "open_app_count": len(active_windows),
            "distractor_count": len(distractors),
            "distractors": distractors,
            "git_branch": git_context.get("branch"),
        },
    }


# ---------------------------------------------------------------------------
# Dispatcher — route a natural language request to the right agent
# ---------------------------------------------------------------------------

def _context_keeper_dispatch(state: Dict) -> Dict:
    """Thin wrapper so context_keeper_node can be referenced in _KEYWORD_MAP."""
    from src.context_keeper import context_keeper_node
    return context_keeper_node(state)


def _dependency_rebel_dispatch(state: Dict) -> Dict:
    from src.expert_agents import dependency_rebel_node
    return dependency_rebel_node(state)


def _merge_conflict_dispatch(state: Dict) -> Dict:
    from src.expert_agents import merge_conflict_predictor_node
    return merge_conflict_predictor_node(state)


def _tech_debt_dispatch(state: Dict) -> Dict:
    from src.expert_agents import tech_debt_quantifier_node
    return tech_debt_quantifier_node(state)


def _migration_pilot_dispatch(state: Dict) -> Dict:
    from src.expert_agents import migration_pilot_node
    return migration_pilot_node(state)


def _flaky_test_dispatch(state: Dict) -> Dict:
    from src.expert_agents import flaky_test_detective_node
    return flaky_test_detective_node(state)


def _onboarding_dispatch(state: Dict) -> Dict:
    from src.expert_agents import onboarding_mentor_node
    return onboarding_mentor_node(state)


def _incident_responder_dispatch(state: Dict) -> Dict:
    from src.expert_agents import incident_responder_node
    return incident_responder_node(state)


def _cloud_cost_dispatch(state: Dict) -> Dict:
    from src.expert_agents import cloud_cost_auditor_node
    return cloud_cost_auditor_node(state)


def _cert_rotator_dispatch(state: Dict) -> Dict:
    from src.expert_agents import certificate_rotator_node
    return certificate_rotator_node(state)


def _terraform_dispatch(state: Dict) -> Dict:
    from src.expert_agents import terraform_plan_reviewer_node
    return terraform_plan_reviewer_node(state)


def _dotfile_doctor_dispatch(state: Dict) -> Dict:
    from src.expert_agents import dotfile_doctor_node
    return dotfile_doctor_node(state)


def _disk_space_dispatch(state: Dict) -> Dict:
    from src.expert_agents import disk_space_prophet_node
    return disk_space_prophet_node(state)


# Expert agents are listed FIRST so specific keywords (e.g. "dotfile") beat
# general ones (e.g. "files" which is a substring of "dotfiles").
_KEYWORD_MAP = [
    # ── Expert / Deep-Diagnostic agents (checked first — more specific) ──────
    (["depend", "conflict", "npm audit", "peer dep", "version conflict", "pip check", "lockfile", "outdated package"], _dependency_rebel_dispatch),
    (["merge conflict", "predict conflict", "safe to merge", "branch conflict", "rebase risk", "will it merge"], _merge_conflict_dispatch),
    (["tech debt", "code quality", "todo fixme", "cyclomatic", "refactor score", "debt score", "code smell"], _tech_debt_dispatch),
    (["migrate", "migration", "upgrade react", "upgrade django", "breaking change", "upgrade from", "version upgrade"], _migration_pilot_dispatch),
    (["flaky test", "flakey", "intermittent test", "test keeps failing", "non-deterministic test"], _flaky_test_dispatch),
    (["onboard", "new developer", "onboarding", "new team member", "first day", "understand codebase", "where to start"], _onboarding_dispatch),
    (["incident", "outage", "production down", "service down", "triage", "root cause", "what broke", "correlated logs"], _incident_responder_dispatch),
    (["cloud cost", "aws bill", "terraform waste", "idle resource", "unused ec2", "cost audit"], _cloud_cost_dispatch),
    (["certificate", "cert expir", "tls expir", "ssl expir", "https cert", "x509", "renewal"], _cert_rotator_dispatch),
    (["terraform plan", "terraform apply", "destroy resource", "infrastructure change", "tf plan", "tfplan"], _terraform_dispatch),
    (["dotfile", "zshrc", "bashrc", "shell slow", "slow terminal", "shell startup", "shell config"], _dotfile_doctor_dispatch),
    (["disk full", "no space", "disk space", "disk usage", "disk will", "storage full", "disk"], _disk_space_dispatch),
    # ── General Computer Health agents (broader keywords, checked after expert) ─
    (["slow", "throttle", "startup", "thermal", "jet engine", "fan", "bloat", "cpu"], system_optimizer_node),
    (["files", "downloads", "desktop", "organiz", "duplicat", "clutter", "mess", "junk"], file_organizer_node),
    (["python", "node", "npm", "pip", "docker", "path", "environment", "broken", "not found", "command not found", "venv"], environment_doctor_node),
    (["security", "port", "camera", "microphone", "permissions", "hack", "virus", "malware", "firewall"], security_guard_node),
    (["wifi", "network", "internet", "dns", "connection", "latency", "ping", "localhost refused"], network_medic_node),
    (["battery", "drain", "charge", "energy", "power", "zombie"], battery_analyst_node),
    (["update", "upgrade", "outdated", "patch", "version", "brew", "apt"], update_manager_node),
    (["crash", "log", "error", "stack trace", "fault", "exception", "kernel panic"], log_interpreter_node),
    (["privacy", "tracker", "cookie", "permission", "clipboard", "data", "spy"], privacy_cleaner_node),
    (["photo", "video", "media", "picture", "screenshot", "image", "librari", "compress"], media_librarian_node),
    (["backup", "git", "uncommitted", "unsaved", "time machine", "lost", "sync"], backup_sentinel_node),
    (["tab", "focus", "distract", "switch", "overwhelm", "project"], context_switcher_node),
    (["what was i doing", "context", "briefing", "resume", "memory", "last session", "pick up"], _context_keeper_dispatch),
]


def run_full_checkup(focus: str = "") -> dict:
    """
    Run a comprehensive computer health scan across 6 agents:
    system_optimizer, battery_analyst, security_guard, network_medic,
    backup_sentinel, update_manager.

    Returns a combined dict with per-agent reports, a health_summary,
    a 0-100 health_score, and a list of action_scripts.
    """
    agents_to_run = [
        ("system_optimizer",  system_optimizer_node),
        ("battery_analyst",   battery_analyst_node),
        ("security_guard",    security_guard_node),
        ("network_medic",     network_medic_node),
        ("backup_sentinel",   backup_sentinel_node),
        ("update_manager",    update_manager_node),
    ]

    state_base: Dict = {"user_request": focus or "full system checkup"}
    reports = []
    action_scripts = []
    errors = []
    agents_run = []

    for name, fn in agents_to_run:
        try:
            result = fn(dict(state_base))
            result["agent"] = name
            reports.append(result)
            agents_run.append(name)
            if result.get("script_path"):
                action_scripts.append(result["script_path"])
        except Exception as exc:
            logger.warning("run_full_checkup: agent %s failed: %s", name, exc)
            errors.append(f"{name}: {exc}")

    # Derive a simple 0-100 health score from the reports
    # Start at 100 and deduct points for critical/warning keywords in reports
    score = 100
    for r in reports:
        report_text = (r.get("report") or "").lower()
        score -= report_text.count("critical") * 10
        score -= report_text.count("warning") * 3
        score -= report_text.count("error") * 5
    score = max(0, min(100, score))

    # Build a short health_summary
    health_summary = (
        f"Health score: {score}/100 across {len(agents_run)} agents. "
        + (f"Issues detected — review reports below." if score < 80 else "System looks healthy.")
    )

    return {
        "status": "ok",
        "health_score": score,
        "health_summary": health_summary,
        "agents_run": agents_run,
        "reports": reports,
        "action_scripts": action_scripts,
        "errors": errors,
    }


def dispatch(request: str, state: Optional[Dict] = None) -> Dict:
    """
    Route a plain-English request to the most appropriate computer health agent.
    Falls back to system_optimizer if no keyword matches.

    Usage:
        from src.computer_agents import dispatch
        result = dispatch("my wifi keeps dropping")
    """
    req_lower = request.lower()
    for keywords, node_fn in _KEYWORD_MAP:
        if any(kw in req_lower for kw in keywords):
            logger.info("[dispatch] Routing '%s' → %s", request[:60], node_fn.__name__)
            return node_fn(state or {"user_request": request})
    logger.info("[dispatch] No keyword match for '%s', defaulting to system_optimizer", request[:60])
    return system_optimizer_node(state or {"user_request": request})
