"""
Expert Agents — 12 deep specialist agents for high-friction dev/ops pain points.

SDLC specialists (6):
  dependency_rebel           — cross-language dependency conflict detection & resolution
  merge_conflict_predictor   — predict merge conflicts before they happen
  tech_debt_quantifier       — cyclomatic complexity, TODO density, debt score
  migration_pilot            — framework/library upgrade analysis & PR draft
  flaky_test_detective       — identify flaky tests from patterns and cache
  onboarding_mentor          — customized onboarding guide for new devs

DevOps / reliability (5):
  cloud_cost_auditor         — Terraform waste detection + AWS idle resources
  certificate_rotator        — TLS cert expiry across all infra hosts
  terraform_plan_reviewer    — flag destructive terraform plan changes
  incident_responder         — multi-source log correlation + triage
  dotfile_doctor             — shell config bugs, slow startup, PATH conflicts

Workstation (1):
  disk_space_prophet         — predict full-disk events, identify prune targets
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.git_tools import (
    MergeAnalyzer, TechDebtScanner, DependencyAnalyzer,
    FlakeyTestAnalyzer, DotfileDoctor, DiskSpaceAnalyzer,
)
from src.cloud_tools import (
    CertificateChecker, TerraformReviewer, CloudCostAuditor, IncidentCorrelator,
)

logger = logging.getLogger(__name__)

GENERATED_DIR = Path("generated/reports")
SCRIPTS_DIR   = Path("generated/scripts")


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _router():
    from src.llm_router import LLMRouter
    return LLMRouter()


def _save_report(filename: str, content: str) -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path = GENERATED_DIR / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


def _save_script(filename: str, content: str) -> str:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / filename
    path.write_text(content, encoding="utf-8")
    os.chmod(str(path), 0o644)
    return str(path)


def _call_llm(agent_name: str, system_prompt: str, data_context: str,
               request: str = "") -> str:
    # Prepend relevant past fixes so the LLM builds on prior knowledge
    try:
        from src.memory import recall_similar, format_past_context
        past = recall_similar(request or data_context[:120], agent=agent_name, limit=3)
        if past:
            data_context = format_past_context(past) + data_context
    except Exception:
        pass
    try:
        return _router().call(agent_name, data_context, system_prompt=system_prompt)
    except Exception as exc:
        logger.warning("[expert_agents] LLM call failed for %s: %s", agent_name, exc)
        return f"[LLM unavailable — raw data follows]\n\n{data_context[:3000]}"


def _record(agent_name: str, request: str, result: Dict) -> None:
    """Persist a completed expert-agent run to memory (best-effort)."""
    try:
        from src.memory import record_run
        record_run(
            agent_name=agent_name,
            request=request,
            summary=(result.get("report") or "")[:500],
            success=True,
        )
    except Exception:
        pass


def _truncate(obj: Any, max_chars: int = 4000) -> str:
    s = json.dumps(obj, indent=2, default=str) if not isinstance(obj, str) else obj
    return s[:max_chars] + ("…" if len(s) > max_chars else "")


def _repo_path(state: Dict) -> str:
    return state.get("repo_path") or state.get("_scan_path") or os.getcwd()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Dependency Rebel
# ─────────────────────────────────────────────────────────────────────────────

def dependency_rebel_node(state: Dict) -> Dict:
    """
    Detect dependency conflicts, vulnerabilities, and outdated packages
    across Python, Node, Rust, Java, and Go in one shot.
    """
    logger.info("[dependency_rebel] Scanning dependencies…")
    repo = _repo_path(state)
    analyzer = DependencyAnalyzer(repo)
    langs = analyzer.detect_language()

    scans = {}
    fix_notes = []
    for lang in langs:
        if lang == "python":
            scan = analyzer.scan_python()
        elif lang == "node":
            scan = analyzer.scan_node()
        else:
            scan = {"language": lang, "note": "Static scan only — run language-specific tools for full analysis"}
        scans[lang] = scan
        fix_notes.append(analyzer.generate_fix_plan(scan))

    context = (
        f"## Detected Languages: {', '.join(langs) or 'none'}\n\n"
        + "\n\n".join(f"### {lang.title()}\n{_truncate(s, 1500)}" for lang, s in scans.items())
        + f"\n\n## Auto-extracted Fix Notes\n" + "\n".join(fix_notes)
    )

    system_prompt = (
        "You are a dependency management expert. Given real scan data:\n"
        "1. List every dependency conflict with root cause explanation\n"
        "2. Rank vulnerabilities by severity (Critical/High/Medium/Low)\n"
        "3. For each issue, give the exact command to fix it\n"
        "4. Identify any 'phantom dependencies' — things imported but not in requirements\n"
        "5. Suggest a lockfile strategy if none exists\n"
        "Format as a Markdown report. Be specific about package names and versions."
    )

    report = _call_llm("dependency_rebel", system_prompt, context)
    report_path = _save_report("dependency_rebel_report.md", f"# Dependency Rebel Report\n\n{report}")

    # Generate fix script
    script_lines = ["#!/bin/bash", "# Dependency Rebel — Auto-Fix Script (DRY RUN)", "# Remove # prefix to execute", ""]
    for lang, scan in scans.items():
        if lang == "python":
            if scan.get("conflicts"):
                script_lines.append("# Fix Python conflicts:")
                script_lines.append("# pip install --upgrade pip && pip check")
        elif lang == "node":
            if scan.get("total_vulns", 0) > 0:
                script_lines.append("# Fix npm vulnerabilities:")
                script_lines.append("# npm audit fix")
                script_lines.append("# npm audit fix --force  # only if audit fix isn't enough")

    script_path = _save_script("fix_dependencies.sh", "\n".join(script_lines))

    return {
        "agent": "dependency_rebel",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "languages": langs,
            "python_conflicts": len(scans.get("python", {}).get("conflicts", [])),
            "node_vulns": scans.get("node", {}).get("total_vulns", 0),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Merge Conflict Predictor
# ─────────────────────────────────────────────────────────────────────────────

def merge_conflict_predictor_node(state: Dict) -> Dict:
    """
    Predict which files will conflict when merging two branches,
    including line-level overlap analysis.
    """
    logger.info("[merge_conflict_predictor] Analyzing branches for conflicts…")
    repo = _repo_path(state)
    analyzer = MergeAnalyzer(repo)

    branches = analyzer.list_branches()
    current = analyzer.current_branch()

    # Try to get two branches from the request
    request = state.get("user_request", "")
    branch_a = current
    branch_b = "main"

    # Parse "predict conflicts between X and Y" patterns
    import re
    m = re.search(r"\b(?:between|merge)\s+([\w/.\-]+)\s+(?:and|into|with)\s+([\w/.\-]+)", request, re.IGNORECASE)
    if m:
        branch_a = m.group(1)
        branch_b = m.group(2)

    prediction = analyzer.predict_conflicts(branch_a, branch_b)
    recent = analyzer.get_recent_commits(branch_a, n=5)

    context = (
        f"## Merge Conflict Prediction: `{branch_a}` → `{branch_b}`\n"
        f"{_truncate(prediction, 2000)}\n\n"
        f"## Recent Commits on `{branch_a}`\n{_truncate(recent, 800)}\n\n"
        f"## Available Branches ({len(branches)} total)\n"
        + "\n".join(f"  - {b}" for b in branches[:15])
    )

    system_prompt = (
        "You are a git expert and merge specialist. Given the overlap analysis:\n"
        "1. Rate the merge risk: Low / Medium / High / Critical\n"
        "2. For each conflicting file, explain WHY it will conflict (feature vs. refactor etc.)\n"
        "3. Suggest the safest merge strategy (merge, rebase, squash)\n"
        "4. Recommend which files to resolve manually vs. auto-resolving\n"
        "5. Give exact git commands to attempt the merge safely\n"
        "Format as a Markdown report."
    )

    report = _call_llm("merge_conflict_predictor", system_prompt, context)

    script_lines = [
        "#!/bin/bash",
        f"# Merge Conflict Predictor — Safe Merge Script for {branch_a} → {branch_b}",
        "# Review and execute step by step",
        "",
        f"# 1. Fetch latest",
        "# git fetch --all",
        f"# 2. Checkout target branch",
        f"# git checkout {branch_b}",
        f"# 3. Dry-run merge (no commit)",
        f"# git merge --no-commit --no-ff {branch_a}",
        "# 4. Review conflicts",
        "# git status",
        "# 5. Abort if too risky",
        "# git merge --abort",
    ]

    report_path = _save_report("merge_conflict_predictor_report.md", f"# Merge Conflict Predictor Report\n\n{report}")
    script_path = _save_script("safe_merge.sh", "\n".join(script_lines))

    return {
        "agent": "merge_conflict_predictor",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "branch_a": branch_a,
            "branch_b": branch_b,
            "conflict_risk": prediction.get("conflict_risk"),
            "overlapping_files": prediction.get("overlapping_files", 0),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tech Debt Quantifier
# ─────────────────────────────────────────────────────────────────────────────

def tech_debt_quantifier_node(state: Dict) -> Dict:
    """
    Scan codebase for TODO/FIXME density, cyclomatic complexity hotspots,
    deprecated patterns, and produce a prioritized debt repayment plan.
    """
    logger.info("[tech_debt_quantifier] Scanning codebase for tech debt…")
    repo = _repo_path(state)
    scanner = TechDebtScanner(repo)
    analyzer = MergeAnalyzer(repo)

    debt = scanner.scan_directory(repo)
    hottest = analyzer.get_hottest_files(n=10)

    # Complexity for the top 5 most-changed files
    complexity_results = []
    for item in hottest[:5]:
        fp = str(Path(repo) / item["file"])
        if Path(fp).exists():
            cr = scanner.cyclomatic_complexity(fp)
            complexity_results.append(cr)

    context = (
        f"## Debt Summary\n{_truncate(debt, 2000)}\n\n"
        f"## Most-Changed Files (highest churn = highest debt risk)\n{_truncate(hottest, 800)}\n\n"
        f"## Cyclomatic Complexity Hotspots\n{_truncate(complexity_results, 800)}\n"
    )

    system_prompt = (
        "You are a software quality architect. Given the static analysis data:\n"
        "1. Calculate a tech debt score (0-100, higher = more debt)\n"
        "2. Identify the top 5 highest-risk files that need refactoring most urgently\n"
        "3. Estimate developer-hours to pay off each category of debt\n"
        "4. Prioritize: what gives the biggest quality improvement for least effort?\n"
        "5. Flag any patterns that indicate specific architecture smells\n"
        "Format as a Markdown report with a debt score table at the top."
    )

    report = _call_llm("tech_debt_quantifier", system_prompt, context)
    report_path = _save_report("tech_debt_quantifier_report.md", f"# Tech Debt Report\n\n{report}")

    return {
        "agent": "tech_debt_quantifier",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "files_scanned": debt["files_scanned"],
            "total_lines": debt["total_lines"],
            "todo_fixme_count": debt["todo_fixme_count"],
            "long_files": len(debt.get("long_files", [])),
            "files_with_debt": len(debt["debt_by_file"]),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Migration Pilot
# ─────────────────────────────────────────────────────────────────────────────

def migration_pilot_node(state: Dict) -> Dict:
    """
    Analyze a codebase for breaking-change APIs relative to a target
    framework/library version, and generate a step-by-step migration plan.
    """
    logger.info("[migration_pilot] Analyzing codebase for migration requirements…")
    repo = _repo_path(state)
    request = state.get("user_request", "")

    dep_analyzer = DependencyAnalyzer(repo)
    debt_scanner = TechDebtScanner(repo)

    langs = dep_analyzer.detect_language()
    py_scan = dep_analyzer.scan_python() if "python" in langs else {}
    node_scan = dep_analyzer.scan_node() if "node" in langs else {}
    debt = debt_scanner.scan_directory(repo)

    context = (
        f"## Migration Request\n{request}\n\n"
        f"## Current Dependencies\n"
        f"### Python\n{_truncate(py_scan, 1000)}\n"
        f"### Node\n{_truncate(node_scan, 1000)}\n\n"
        f"## Code Patterns That May Break\n{_truncate(debt['debt_by_file'][:10], 1500)}\n"
    )

    system_prompt = (
        "You are a framework migration expert. Given the codebase analysis:\n"
        "1. Identify every file that uses APIs changed in the target version\n"
        "2. List each breaking change with the old API and the new replacement\n"
        "3. Provide a numbered, ordered migration checklist\n"
        "4. Estimate total migration effort (hours)\n"
        "5. Flag any changes that MUST be done before others (blockers)\n"
        "6. Suggest which changes can be automated with codemods\n"
        "Format as a Markdown migration guide with a step-by-step checklist."
    )

    report = _call_llm("migration_pilot", system_prompt, context)
    report_path = _save_report("migration_pilot_report.md", f"# Migration Pilot Report\n\n{report}")

    return {
        "agent": "migration_pilot",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "languages": langs,
            "files_analyzed": debt["files_scanned"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Flaky Test Detective
# ─────────────────────────────────────────────────────────────────────────────

def flaky_test_detective_node(state: Dict) -> Dict:
    """
    Identify flaky tests by scanning for timing dependencies, random data,
    external HTTP calls, and reading pytest failure cache.
    """
    logger.info("[flaky_test_detective] Scanning for flaky tests…")
    repo = _repo_path(state)
    analyzer = FlakeyTestAnalyzer(repo)

    scan = analyzer.run_quick_scan()

    context = (
        f"## Test Files Found: {scan['test_files_found']}\n"
        f"## Files With Flakiness Patterns: {scan['files_with_patterns']}\n\n"
        f"## Previously Failing Tests (from cache)\n"
        + ("\n".join(f"  - {t}" for t in scan["last_failed_tests"]) or "  None found")
        + f"\n\n## Flakiness Pattern Analysis\n{_truncate(scan['flakiness_findings'], 2500)}\n"
    )

    system_prompt = (
        "You are a test reliability expert. Given flakiness pattern analysis:\n"
        "1. Rank tests from most-flaky to least-flaky\n"
        "2. For each flaky test, explain the root cause (timing, random data, external dep, etc.)\n"
        "3. Give exact code fixes: how to mock the external dependency, use fixed seeds, etc.\n"
        "4. Suggest pytest markers like @pytest.mark.flaky or xfail for known flaky ones\n"
        "5. Recommend a test architecture fix (e.g., 'move all HTTP calls behind an interface')\n"
        "Format as a Markdown report. Include specific code examples."
    )

    report = _call_llm("flaky_test_detective", system_prompt, context)
    report_path = _save_report("flaky_test_detective_report.md", f"# Flaky Test Detective Report\n\n{report}")

    return {
        "agent": "flaky_test_detective",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "test_files_found": scan["test_files_found"],
            "files_with_patterns": scan["files_with_patterns"],
            "last_failed_count": len(scan["last_failed_tests"]),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. Onboarding Mentor
# ─────────────────────────────────────────────────────────────────────────────

def onboarding_mentor_node(state: Dict) -> Dict:
    """
    Generate a customized onboarding guide: most-touched files, architecture
    overview, key modules, and walkthroughs of recent PRs.
    """
    logger.info("[onboarding_mentor] Building onboarding guide…")
    repo = _repo_path(state)
    git = MergeAnalyzer(repo)
    debt = TechDebtScanner(repo)

    hottest = git.get_hottest_files(n=15)
    recent = git.get_recent_commits("HEAD", n=10)

    # Map top-level structure
    root = Path(repo)
    top_level = []
    for item in sorted(root.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            py_count = len(list(item.rglob("*.py")))
            js_count = len(list(item.rglob("*.{js,ts}")))
            top_level.append({"name": item.name, "type": "dir", "py_files": py_count, "js_files": js_count})
        else:
            top_level.append({"name": item.name, "type": "file"})

    # Read README if present
    readme = ""
    for rname in ["README.md", "readme.md", "README.rst"]:
        rp = root / rname
        if rp.exists():
            readme = rp.read_text(encoding="utf-8", errors="ignore")[:1500]
            break

    context = (
        f"## Repository Structure\n{_truncate(top_level, 600)}\n\n"
        f"## README Excerpt\n{readme}\n\n"
        f"## Most-Touched Files (core to understand)\n{_truncate(hottest, 800)}\n\n"
        f"## Recent Commits (last 10)\n{_truncate(recent, 1000)}\n"
    )

    system_prompt = (
        "You are a senior developer writing an onboarding guide for a new team member. "
        "Given the repository analysis:\n"
        "1. Write a 'What does this codebase do?' summary (2-3 sentences)\n"
        "2. Draw a simple architecture diagram (ASCII or Mermaid)\n"
        "3. List the 5 most important files to read first, with why\n"
        "4. Explain the 3 most recent features/changes based on commit messages\n"
        "5. List gotchas and non-obvious conventions (e.g. 'never modify X directly')\n"
        "6. Give a 'first task' suggestion for a new dev\n"
        "Format as a Markdown onboarding guide."
    )

    report = _call_llm("onboarding_mentor", system_prompt, context)
    report_path = _save_report("onboarding_guide.md", f"# Onboarding Guide\n\n{report}")

    return {
        "agent": "onboarding_mentor",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "hottest_files": [h["file"] for h in hottest[:5]],
            "recent_commit_count": len(recent),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. Cloud Cost Auditor
# ─────────────────────────────────────────────────────────────────────────────

def cloud_cost_auditor_node(state: Dict) -> Dict:
    """
    Find Terraform waste (over-provisioned instances, idle resources, missing
    deletion protection) + live AWS CLI idle resource check if credentials are available.
    """
    logger.info("[cloud_cost_auditor] Auditing cloud costs…")
    repo = _repo_path(state)
    auditor = CloudCostAuditor()

    # Find Terraform directories
    tf_dirs = []
    for tf in Path(repo).rglob("*.tf"):
        if tf.parent not in tf_dirs:
            tf_dirs.append(tf.parent)

    tf_scan: Dict[str, Any] = {"tf_files_scanned": 0, "issues": []}
    for tf_dir in tf_dirs[:3]:
        s = auditor.scan_terraform_dir(str(tf_dir))
        tf_scan["tf_files_scanned"] += s["tf_files_scanned"]
        tf_scan["issues"].extend(s["issues"])
        tf_scan.setdefault("resource_types", {}).update(s.get("resource_types", {}))

    aws_scan = auditor.scan_aws_cli_output()

    context = (
        f"## Terraform Analysis ({tf_scan['tf_files_scanned']} files)\n{_truncate(tf_scan, 2000)}\n\n"
        f"## Live AWS Resources\n{_truncate(aws_scan, 1000)}\n"
    )

    system_prompt = (
        "You are a FinOps cloud cost optimization expert. Given the infrastructure scan:\n"
        "1. List every waste finding with estimated monthly cost\n"
        "2. Prioritize savings opportunities (biggest bang for least risk)\n"
        "3. Flag any security risks found during the cost audit\n"
        "4. Give exact Terraform or AWS CLI commands to remediate each issue\n"
        "5. Estimate total monthly savings if all recommendations are applied\n"
        "Format as a Markdown report with a savings summary table."
    )

    report = _call_llm("cloud_cost_auditor", system_prompt, context)
    report_path = _save_report("cloud_cost_auditor_report.md", f"# Cloud Cost Auditor Report\n\n{report}")

    total_tf_issues = len(tf_scan["issues"])
    return {
        "agent": "cloud_cost_auditor",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "tf_files_scanned": tf_scan["tf_files_scanned"],
            "tf_issues": total_tf_issues,
            "aws_available": aws_scan.get("available", False),
            "aws_issues": len(aws_scan.get("issues", [])),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. Certificate Rotator
# ─────────────────────────────────────────────────────────────────────────────

def certificate_rotator_node(state: Dict) -> Dict:
    """
    Check TLS certificate expiry for all hosts found in config files.
    Warn 30 days before expiry and generate renewal commands.
    """
    logger.info("[certificate_rotator] Checking TLS certificates…")
    repo = _repo_path(state)
    checker = CertificateChecker()

    # Get hosts from config files + any explicit in request
    hosts_from_repo = checker.find_hosts_from_repo(repo)
    request = state.get("user_request", "")
    # Also extract any hosts mentioned in the request
    import re
    request_hosts = re.findall(r"\b([\w\-]+\.[\w.\-]{2,})\b", request)
    all_hosts = list(dict.fromkeys(hosts_from_repo + request_hosts))[:15]

    results = checker.check_hosts(all_hosts) if all_hosts else []

    expiring = [r for r in results if r.get("status") in ("critical", "warning")]
    errors = [r for r in results if r.get("status") == "error"]

    context = (
        f"## Hosts Checked: {len(results)}\n"
        f"## Expiring Soon: {len(expiring)}\n"
        f"## Unreachable / Errors: {len(errors)}\n\n"
        f"## Certificate Details\n{_truncate(results, 2000)}\n"
    )

    system_prompt = (
        "You are a TLS/PKI operations expert. Given certificate check results:\n"
        "1. List all certificates expiring within 30 days — critical first\n"
        "2. For each expiring cert, give the exact renewal command (Let's Encrypt, ACM, etc.)\n"
        "3. Flag any certificate mismatches or verification errors\n"
        "4. Recommend automating renewal with certbot or AWS Certificate Manager\n"
        "5. Estimate impact of each expired cert (user-facing vs internal)\n"
        "Format as a Markdown report with urgency color-coding."
    )

    report = _call_llm("certificate_rotator", system_prompt, context)

    renewal_lines = ["#!/bin/bash", "# Certificate Rotator — Renewal Commands", ""]
    for r in expiring:
        host = r.get("host", "")
        days = r.get("days_until_expiry", "?")
        renewal_lines.append(f"# {host} — expires in {days} days")
        renewal_lines.append(f"# sudo certbot renew --cert-name {host}")
        renewal_lines.append("")

    report_path = _save_report("certificate_rotator_report.md", f"# Certificate Rotator Report\n\n{report}")
    script_path = _save_script("renew_certs.sh", "\n".join(renewal_lines))

    return {
        "agent": "certificate_rotator",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "hosts_checked": len(results),
            "expiring_soon": len(expiring),
            "critical": len([r for r in results if r.get("status") == "critical"]),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. Terraform Plan Reviewer
# ─────────────────────────────────────────────────────────────────────────────

def terraform_plan_reviewer_node(state: Dict) -> Dict:
    """
    Review terraform plan output for destructive changes.
    Requires explicit approval before allowing apply.
    """
    logger.info("[terraform_plan_reviewer] Reviewing Terraform plan…")
    repo = _repo_path(state)
    reviewer = TerraformReviewer()

    # Check if plan text was passed in state
    plan_text = state.get("plan_text") or state.get("user_request", "")

    if len(plan_text) < 100:
        # Try to run terraform plan
        result = reviewer.run_plan_check(repo)
        if "error" in result:
            # Try to find a saved plan file
            plan_file = reviewer.find_plan_file(repo)
            if plan_file:
                plan_text = Path(plan_file).read_text(encoding="utf-8", errors="ignore")
                result = reviewer.parse_plan_text(plan_text)
            else:
                result = {"error": result["error"], "changes": {}, "risk_level": "unknown"}
    else:
        result = reviewer.parse_plan_text(plan_text)

    context = (
        f"## Terraform Plan Analysis\n{_truncate(result, 2000)}\n\n"
        f"## Raw Plan (excerpt)\n{plan_text[:2000]}\n"
    )

    system_prompt = (
        "You are a Terraform and cloud infrastructure expert. Given the plan analysis:\n"
        "1. List EVERY resource that will be DESTROYED or REPLACED — these are critical\n"
        "2. For each destructive change, explain why it's happening and what data/service is at risk\n"
        "3. Suggest safer alternatives (e.g. in-place update instead of destroy+create)\n"
        "4. Rate overall plan risk: Safe / Review Required / STOP — Do Not Apply\n"
        "5. List the exact Terraform resources and configs to change to avoid destruction\n"
        "If risk is HIGH or CRITICAL, state clearly: 'DO NOT RUN terraform apply WITHOUT REVIEWING'\n"
        "Format as a Markdown safety review."
    )

    report = _call_llm("terraform_plan_reviewer", system_prompt, context)
    approval_note = ""
    if result.get("approval_required"):
        approval_note = "\n\n⚠️  **APPROVAL REQUIRED before terraform apply** — destructive changes detected."

    report_path = _save_report(
        "terraform_plan_review.md",
        f"# Terraform Plan Review\n{approval_note}\n\n{report}",
    )

    return {
        "agent": "terraform_plan_reviewer",
        "report": report + approval_note,
        "report_path": report_path,
        "raw_data": {
            "risk_level": result.get("risk_level", "unknown"),
            "destructive_ops": len(result.get("destructive_operations", [])),
            "high_risk_resources": len(result.get("high_risk_resources", [])),
            "approval_required": result.get("approval_required", False),
            "changes": result.get("changes", {}),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10. Incident Responder
# ─────────────────────────────────────────────────────────────────────────────

def incident_responder_node(state: Dict) -> Dict:
    """
    Multi-source log correlation + triage for production incidents.
    Gathers Docker logs, app logs, and system logs, then builds a timeline.
    """
    logger.info("[incident_responder] Correlating incident logs…")
    repo = _repo_path(state)
    correlator = IncidentCorrelator(repo)

    window = int(state.get("window_minutes", 30))
    timeline = correlator.correlate_timeline(window_minutes=window)

    # Also get system log snapshot
    from src.system_tools import LogReader
    reader = LogReader()
    sys_log = reader.read_system_log(lines=50)

    context = (
        f"## Incident Window: last {window} minutes\n\n"
        f"## Event Timeline ({len(timeline['error_events'])} error events)\n"
        f"{_truncate(timeline['error_events'], 2500)}\n\n"
        f"## System Log (errors only, last 50 lines)\n{sys_log[:1500]}\n"
    )

    system_prompt = (
        "You are a site reliability engineer responding to a production incident. "
        "Given the correlated log timeline:\n"
        "1. Identify the ROOT CAUSE — what triggered the cascade?\n"
        "2. Build a chronological story: what failed first, what failed next?\n"
        "3. Identify the blast radius: what services/users were affected?\n"
        "4. List immediate mitigation steps (what to do RIGHT NOW)\n"
        "5. List post-incident actions (what to fix to prevent recurrence)\n"
        "Be direct and actionable. Format as an incident triage report."
    )

    report = _call_llm("incident_responder", system_prompt, context)
    report_path = _save_report("incident_responder_report.md", f"# Incident Triage Report\n\n{report}")

    return {
        "agent": "incident_responder",
        "report": report,
        "report_path": report_path,
        "raw_data": {
            "docker_containers_checked": timeline["docker_containers_checked"],
            "app_log_files_checked": timeline["app_log_files_checked"],
            "error_events_found": len(timeline["error_events"]),
            "window_minutes": window,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 11. Dotfile Doctor
# ─────────────────────────────────────────────────────────────────────────────

def dotfile_doctor_node(state: Dict) -> Dict:
    """
    Detect errors and performance issues in shell config files (.zshrc, .bashrc,
    .gitconfig, etc.) that cause slow startup, broken keybindings, or PATH chaos.
    """
    logger.info("[dotfile_doctor] Scanning shell and tool configs…")
    doctor = DotfileDoctor()
    scan = doctor.full_scan()

    context = (
        f"## Configs With Issues: {len(scan['configs_with_issues'])}\n"
        f"## Total Issues Found: {scan['total_issues']}\n\n"
        f"## Detailed Findings\n{_truncate(scan['configs_with_issues'], 2500)}\n"
    )

    system_prompt = (
        "You are a shell configuration and developer experience expert. "
        "Given the dotfile scan results:\n"
        "1. Explain each issue in plain language (what is wrong, why it matters)\n"
        "2. Rank issues by impact on shell startup time and daily workflow\n"
        "3. Give the exact config change to fix each issue\n"
        "4. Flag any syntax errors that break the shell entirely\n"
        "5. Suggest a backup strategy before making changes\n"
        "Format as a Markdown report. Include before/after code snippets."
    )

    report = _call_llm("dotfile_doctor", system_prompt, context)

    # Generate backup + fix script
    script_lines = [
        "#!/bin/bash",
        "# Dotfile Doctor — Backup & Fix Script (DRY RUN)",
        "# Step 1: Back up config files before editing",
        "",
    ]
    for cfg in scan["configs_with_issues"]:
        path = cfg["file"]
        script_lines.append(f"# cp {path} {path}.bak.$(date +%Y%m%d)")
    script_lines += [
        "",
        "# Step 2: After reviewing the report, apply fixes manually or use:",
        "# nano ~/.zshrc  (or your preferred editor)",
        "",
        "# Step 3: Reload config",
        "# source ~/.zshrc",
        "",
        "# Step 4: Measure startup time improvement",
        "# time zsh -i -c exit",
    ]

    report_path = _save_report("dotfile_doctor_report.md", f"# Dotfile Doctor Report\n\n{report}")
    script_path = _save_script("fix_dotfiles.sh", "\n".join(script_lines))

    return {
        "agent": "dotfile_doctor",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "configs_checked": len(DotfileDoctor.SHELL_CONFIGS) + len(DotfileDoctor.TOOL_CONFIGS),
            "configs_with_issues": len(scan["configs_with_issues"]),
            "total_issues": scan["total_issues"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 12. Disk Space Prophet
# ─────────────────────────────────────────────────────────────────────────────

def disk_space_prophet_node(state: Dict) -> Dict:
    """
    Predict disk usage trends, identify prune targets (caches, derived data),
    and warn before "no space left on device" events.
    """
    logger.info("[disk_space_prophet] Analyzing disk usage and growth…")
    analyzer = DiskSpaceAnalyzer()

    disk_usage = analyzer.get_disk_usage()
    prune_savings = analyzer.estimate_prune_savings()
    large_dirs = analyzer.scan_large_dirs("~", depth=2)
    inode_usage = analyzer.get_inode_usage()

    total_savings = len(prune_savings)

    context = (
        f"## Current Disk Usage\n{_truncate(disk_usage, 300)}\n\n"
        f"## Inode Usage\n{_truncate(inode_usage, 200)}\n\n"
        f"## Largest Directories in Home\n{_truncate(large_dirs, 800)}\n\n"
        f"## Pruneable Cache Directories ({total_savings} found)\n{_truncate(prune_savings, 800)}\n"
    )

    system_prompt = (
        "You are a disk space management expert and systems administrator. "
        "Given the disk usage analysis:\n"
        "1. State the current disk situation clearly (% used, GB free)\n"
        "2. Identify the top 3 space wasters with exact sizes\n"
        "3. List cache directories that are 100% safe to delete\n"
        "4. Estimate total free space recoverable from safe pruning\n"
        "5. Predict when disk will be full based on typical growth patterns\n"
        "6. Recommend an ongoing cleanup policy (e.g. weekly cache purge)\n"
        "Format as a Markdown report."
    )

    report = _call_llm("disk_space_prophet", system_prompt, context)

    cleanup_lines = ["#!/bin/bash", "# Disk Space Prophet — Safe Cleanup Script", "# Each command is commented — remove # to execute", ""]
    for item in prune_savings:
        cleanup_lines.append(f"# rm -rf {item['path']}  # {item['size']}")
    cleanup_lines += [
        "",
        "# Clear npm cache",
        "# npm cache clean --force",
        "",
        "# Clear pip cache",
        "# pip cache purge",
        "",
        "# Clear brew caches",
        "# brew cleanup --prune=7",
        "",
        "# Clear macOS derived data",
        "# rm -rf ~/Library/Developer/Xcode/DerivedData",
    ]

    report_path = _save_report("disk_space_prophet_report.md", f"# Disk Space Prophet Report\n\n{report}")
    script_path = _save_script("reclaim_disk_space.sh", "\n".join(cleanup_lines))

    return {
        "agent": "disk_space_prophet",
        "report": report,
        "report_path": report_path,
        "script_path": script_path,
        "raw_data": {
            "disk_use_percent": disk_usage.get("use_percent", "unknown"),
            "disk_available": disk_usage.get("available", "unknown"),
            "pruneable_dirs": len(prune_savings),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch table for expert agents
# ─────────────────────────────────────────────────────────────────────────────

EXPERT_AGENT_MAP = {
    "dependency_rebel":          dependency_rebel_node,
    "merge_conflict_predictor":  merge_conflict_predictor_node,
    "tech_debt_quantifier":      tech_debt_quantifier_node,
    "migration_pilot":           migration_pilot_node,
    "flaky_test_detective":      flaky_test_detective_node,
    "onboarding_mentor":         onboarding_mentor_node,
    "cloud_cost_auditor":        cloud_cost_auditor_node,
    "certificate_rotator":       certificate_rotator_node,
    "terraform_plan_reviewer":   terraform_plan_reviewer_node,
    "incident_responder":        incident_responder_node,
    "dotfile_doctor":            dotfile_doctor_node,
    "disk_space_prophet":        disk_space_prophet_node,
}


def dispatch_expert(request: str, state: Optional[Dict] = None) -> Optional[Dict]:
    """
    Route a plain-English request to an expert agent.
    Returns None if no expert agent matches (fall through to computer_agents.dispatch).
    """
    req = request.lower()
    keyword_map = [
        (["dependency", "requirements", "package conflict", "npm audit", "peer dep", "pip check",
          "lockfile", "version conflict", "outdated package"], "dependency_rebel"),
        (["merge conflict", "predict conflict", "safe to merge", "which files conflict",
          "branch conflict", "rebase risk"], "merge_conflict_predictor"),
        (["tech debt", "code quality", "todo fixme", "cyclomatic", "refactor", "complexity score",
          "debt score", "code smell"], "tech_debt_quantifier"),
        (["migrate", "migration", "upgrade react", "upgrade django", "upgrade rails",
          "breaking change", "upgrade from", "version upgrade"], "migration_pilot"),
        (["flaky test", "flakey", "unreliable test", "test keeps failing", "intermittent test",
          "race condition test", "non-deterministic"], "flaky_test_detective"),
        (["onboard", "new developer", "onboarding guide", "new team member", "first day",
          "understand the codebase", "where to start"], "onboarding_mentor"),
        (["cloud cost", "aws bill", "terraform waste", "idle resource", "unused ec2",
          "unattached ebs", "cost audit", "overspend"], "cloud_cost_auditor"),
        (["certificate", "tls", "ssl", "cert expir", "https expir", "renewal",
          "x509"], "certificate_rotator"),
        (["terraform plan", "terraform apply", "destroy resource", "infrastructure change",
          "tf plan", "tfplan"], "terraform_plan_reviewer"),
        (["incident", "outage", "production down", "service down", "triage", "root cause",
          "what broke", "correlated logs"], "incident_responder"),
        (["dotfile", "zshrc", "bashrc", "shell slow", "slow terminal", "shell startup",
          "shell config", ".gitconfig broken"], "dotfile_doctor"),
        (["disk full", "no space", "disk space", "disk usage", "clean up disk",
          "storage full", "disk running out"], "disk_space_prophet"),
    ]
    for keywords, agent_name in keyword_map:
        if any(kw in req for kw in keywords):
            logger.info("[expert_dispatch] Routing '%s' → %s", request[:60], agent_name)
            s = state or {"user_request": request}
            result = EXPERT_AGENT_MAP[agent_name](s)
            _record(agent_name, request, result)
            return result
    return None
