"""
TIMPS Swarm — Computer Health Graph

Standalone LangGraph pipeline for the 12 computer-health agents.
Routes plain-English requests to the right agent(s) then produces a
combined health summary.

Usage:
    from src.computer_health_graph import run_health_task, build_health_graph

    # Single dispatch (fastest)
    result = run_health_task("my wifi keeps dropping")

    # Multi-agent scan (thorough — runs several agents)
    result = run_health_task("full system checkup", multi_agent=True)

Graph shape (single-agent mode):
    router_node → <selected_agent>_node → summary_node → END

Graph shape (multi-agent mode):
    router_node → [system_optimizer, battery_analyst, security_guard, network_medic,
                   backup_sentinel, update_manager] → summary_node → END
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END

from src.state import ComputerHealthState
from src.computer_agents import (
    system_optimizer_node,
    file_organizer_node,
    environment_doctor_node,
    security_guard_node,
    network_medic_node,
    battery_analyst_node,
    update_manager_node,
    log_interpreter_node,
    privacy_cleaner_node,
    media_librarian_node,
    backup_sentinel_node,
    context_switcher_node,
)
from src.expert_agents import (
    dependency_rebel_node,
    merge_conflict_predictor_node,
    tech_debt_quantifier_node,
    migration_pilot_node,
    flaky_test_detective_node,
    onboarding_mentor_node,
    cloud_cost_auditor_node,
    certificate_rotator_node,
    terraform_plan_reviewer_node,
    incident_responder_node,
    dotfile_doctor_node,
    disk_space_prophet_node,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

_KEYWORD_ROUTING: list[tuple[list[str], str]] = [
    # Expert agents first — more specific keywords must win over broad ones
    (["depend", "conflict", "package", "vulnerab"],                                         "dependency_rebel"),
    (["disk", "storage", "inode", "prune", "clean up space"],                               "disk_space_prophet"),
    (["dotfile", ".zshrc", ".bashrc", "shell config"],                                      "dotfile_doctor"),
    (["cert", "tls", "ssl", "expire"],                                                      "certificate_rotator"),
    (["terraform", "infrastructure", "tf plan"],                                            "terraform_plan_reviewer"),
    (["incident", "outage", "correlate", "alert"],                                          "incident_responder"),
    (["cloud cost", "aws cost", "idle resource"],                                            "cloud_cost_auditor"),
    (["merge", "branch conflict", "rebase"],                                                "merge_conflict_predictor"),
    (["tech debt", "cyclomatic", "todo density", "fixme"],                                  "tech_debt_quantifier"),
    (["migrat", "upgrade framework"],                                                       "migration_pilot"),
    (["flak", "test fail", "intermittent test", "pytest"],                                  "flaky_test_detective"),
    (["onboard", "new developer", "new hire", "codebase tour"],                             "onboarding_mentor"),
    # General health agents
    (["slow", "throttle", "startup", "thermal", "jet engine", "fan", "cpu", "bloat"],      "system_optimizer"),
    (["files", "downloads", "desktop", "organiz", "duplicat", "clutter", "junk"],          "file_organizer"),
    (["python", "node", "npm", "pip", "docker", "path", "environment", "command not found", "venv"], "environment_doctor"),
    (["security", "port", "camera", "microphone", "permissions", "hack", "virus"],         "security_guard"),
    (["wifi", "network", "internet", "dns", "connection", "latency", "localhost refused"],  "network_medic"),
    (["battery", "drain", "charge", "energy", "power", "zombie"],                          "battery_analyst"),
    (["update", "upgrade", "outdated", "patch", "brew", "apt"],                             "update_manager"),
    (["crash", "log", "error", "stack trace", "fault", "exception"],                        "log_interpreter"),
    (["privacy", "tracker", "cookie", "permission", "clipboard"],                           "privacy_cleaner"),
    (["photo", "video", "media", "picture", "screenshot", "image"],                         "media_librarian"),
    (["backup", "uncommitted", "unsaved", "time machine", "lost"],                          "backup_sentinel"),
    (["tab", "focus", "distract", "context", "switch", "overwhelm"],                        "context_switcher"),
]

_FULL_CHECKUP_KEYWORDS = ["checkup", "everything", "all agents", "comprehensive", "complete scan", "health scan", "full scan", "full check"]

_AGENT_NODES: Dict[str, Any] = {
    # Expert agents
    "dependency_rebel":          dependency_rebel_node,
    "disk_space_prophet":        disk_space_prophet_node,
    "dotfile_doctor":            dotfile_doctor_node,
    "certificate_rotator":       certificate_rotator_node,
    "terraform_plan_reviewer":   terraform_plan_reviewer_node,
    "incident_responder":        incident_responder_node,
    "cloud_cost_auditor":        cloud_cost_auditor_node,
    "merge_conflict_predictor":  merge_conflict_predictor_node,
    "tech_debt_quantifier":      tech_debt_quantifier_node,
    "migration_pilot":           migration_pilot_node,
    "flaky_test_detective":      flaky_test_detective_node,
    "onboarding_mentor":         onboarding_mentor_node,
    # General health agents
    "system_optimizer":          system_optimizer_node,
    "file_organizer":            file_organizer_node,
    "environment_doctor":        environment_doctor_node,
    "security_guard":            security_guard_node,
    "network_medic":             network_medic_node,
    "battery_analyst":           battery_analyst_node,
    "update_manager":            update_manager_node,
    "log_interpreter":           log_interpreter_node,
    "privacy_cleaner":           privacy_cleaner_node,
    "media_librarian":           media_librarian_node,
    "backup_sentinel":           backup_sentinel_node,
    "context_switcher":          context_switcher_node,
}


def _select_agents(request: str, multi_agent: bool = False) -> List[str]:
    """Return the list of agent names to invoke for this request."""
    req_lower = request.lower()

    # Full checkup → run the most impactful 6
    if multi_agent or any(kw in req_lower for kw in _FULL_CHECKUP_KEYWORDS):
        return ["system_optimizer", "battery_analyst", "security_guard",
                "network_medic", "backup_sentinel", "update_manager"]

    # Single agent routing
    for keywords, agent_name in _KEYWORD_ROUTING:
        if any(kw in req_lower for kw in keywords):
            return [agent_name]

    return ["system_optimizer"]   # sensible default


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def router_node(state: ComputerHealthState) -> ComputerHealthState:
    """Decide which agents to run and record it in state."""
    selected = _select_agents(state.get("user_request", ""))
    logger.info("[health_graph] Router selected agents: %s", selected)
    return {
        "agents_run": [],          # will be populated as agents complete
        "reports": [],
        "action_scripts": [],
        "errors": [],
        "health_summary": None,
        "completed": False,
        "_selected_agents": selected,   # internal routing hint
    }


def _make_agent_node(agent_name: str):
    """Wrap an agent function as a LangGraph node that updates ComputerHealthState."""
    fn = _AGENT_NODES[agent_name]

    def node(state: ComputerHealthState) -> dict:
        try:
            result = fn(state)
            # ── Persist run to memory ──────────────────────────────────────
            try:
                from src.memory import record_run
                record_run(
                    agent_name=agent_name,
                    request=state.get("user_request", ""),
                    summary=(result.get("report") or "")[:500],
                    success=True,
                )
            except Exception:
                pass
            return {
                "reports": [result],
                "agents_run": [agent_name],
                "action_scripts": ([result["script_path"]] if result.get("script_path") else []),
            }
        except Exception as exc:
            logger.error("[health_graph] %s failed: %s", agent_name, exc, exc_info=True)
            try:
                from src.memory import record_run
                record_run(agent_name, state.get("user_request", ""), str(exc), success=False)
            except Exception:
                pass
            return {"errors": [f"{agent_name}: {exc}"]}

    node.__name__ = f"{agent_name}_node"
    return node


def summary_node(state: ComputerHealthState) -> dict:
    """Produce a combined health summary from all agent reports."""
    reports = state.get("reports", [])
    if not reports:
        return {"health_summary": "No agent reports generated.", "completed": True}

    from src.llm_router import LLMRouter
    router = LLMRouter()

    combined = "\n\n---\n\n".join(
        f"## {r.get('agent', 'unknown').replace('_', ' ').title()}\n{r.get('report', '')[:800]}"
        for r in reports
    )

    system_prompt = (
        "You are the TIMPS Swarm master health coordinator. "
        "Given reports from multiple specialist agents, produce a SINGLE concise summary:\n"
        "1. Overall computer health score (0-10)\n"
        "2. Top 3 most urgent issues across all reports\n"
        "3. Estimated time to fix everything\n"
        "4. Quick-win action the user should do FIRST\n"
        "Keep it under 300 words. Use bullet points."
    )

    try:
        summary = router.call("orchestrator", combined, system_prompt=system_prompt)
    except Exception as exc:
        summary = f"Summary unavailable ({exc}). Check individual reports in generated/reports/."

    return {"health_summary": summary, "completed": True}


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------

def build_health_graph(agent_names: Optional[List[str]] = None) -> StateGraph:
    """
    Build a LangGraph for the given agent names.
    All agents run in sequence (fan-out fan-in not supported in basic LangGraph).
    """
    agents = agent_names or list(_AGENT_NODES.keys())

    workflow = StateGraph(ComputerHealthState)

    # Add all selected agent nodes
    for name in agents:
        workflow.add_node(name, _make_agent_node(name))

    workflow.add_node("summary", summary_node)

    # Wire: first agent is entry point
    workflow.set_entry_point(agents[0])

    # Chain agents sequentially
    for i in range(len(agents) - 1):
        workflow.add_edge(agents[i], agents[i + 1])

    # Last agent → summary → END
    workflow.add_edge(agents[-1], "summary")
    workflow.add_edge("summary", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------

def run_health_task(request: str, multi_agent: bool = False) -> Dict[str, Any]:
    """
    Execute a computer-health task end-to-end.

    Args:
        request:     Plain-English description, e.g. "my wifi keeps dropping"
        multi_agent: If True, runs a comprehensive 6-agent scan.

    Returns:
        dict with 'reports', 'health_summary', 'action_scripts', 'agents_run'
    """
    agents = _select_agents(request, multi_agent=multi_agent)
    logger.info("[run_health_task] Running agents: %s for request: '%s'", agents, request[:60])

    initial_state: ComputerHealthState = {
        "user_request": request,
        "reports": [],
        "action_scripts": [],
        "health_summary": None,
        "agents_run": [],
        "errors": [],
        "completed": False,
    }

    graph = build_health_graph(agents)
    final_state = graph.invoke(initial_state)

    return {
        "request": request,
        "agents_run": final_state.get("agents_run", []),
        "reports": final_state.get("reports", []),
        "action_scripts": final_state.get("action_scripts", []),
        "health_summary": final_state.get("health_summary", ""),
        "errors": final_state.get("errors", []),
    }
