"""
Sprint Planning Agent — decomposes features into sprint-ready tickets
with estimates, GitHub Issues / Linear creation templates,
and velocity-based capacity planning.

Input:  feature_description (str), team_size (int), sprint_days (int),
        velocity_pts (int), labels (list), repo (str)
Output: tickets, capacity_plan, milestone_map, tickets_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def sprint_planning_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    feature   = args.get("feature_description", "new feature")
    team_size = int(args.get("team_size", 3))
    sprint_days = int(args.get("sprint_days", 14))
    velocity  = int(args.get("velocity_pts", 40))
    labels: List[str] = args.get("labels", ["enhancement"])
    repo      = args.get("repo", "")

    system = (
        "You are a Scrum/Kanban coach. Return JSON: "
        "{tickets:[{title,description,acceptance_criteria:[str],"
        "story_points:int,type:'story'|'task'|'bug'|'spike',"
        "labels:[str],dependencies:[int],priority:'P0'|'P1'|'P2'}], "
        "capacity_plan:{total_pts:int,committed_pts:int,buffer_pts:int}, "
        "milestone_map:[{sprint:int,tickets:[int],goal:str}], "
        "risks:[str], definition_of_done:[str], "
        "github_issues_payload:str (JSON array)}. Output ONLY valid JSON."
    )
    prompt = (
        f"Feature: {feature}\nTeam: {team_size}\nSprint: {sprint_days}d\n"
        f"Velocity: {velocity}pts\nLabels: {json.dumps(labels)}\nRepo: {repo or 'unset'}\n\n"
        "Decompose into sprint tickets."
    )

    data = _parse_json(_llm(prompt, system, "sprint_planning_agent"), {
        "tickets": [], "capacity_plan": {}, "milestone_map": [],
    })

    ts = _ts()
    tickets_path = _save("specs", f"sprint_tickets_{ts}.json",
                          json.dumps(data.get("tickets", []), indent=2))
    milestone_path = _save("specs", f"milestone_map_{ts}.md",
                            "\n".join(
                                f"## Sprint {m.get('sprint','?')}: {m.get('goal','')}\n"
                                + "\n".join(f"- Ticket #{t}" for t in m.get("tickets", []))
                                for m in data.get("milestone_map", [])
                            ))
    gh_payload_path = _save("scripts", f"github_issues_create_{ts}.json",
                             data.get("github_issues_payload", "[]"))

    _record("sprint_planning_agent", feature, tickets_path)
    return {
        "ticket_count":        len(data.get("tickets", [])),
        "capacity_plan":       data.get("capacity_plan", {}),
        "milestone_map":       data.get("milestone_map", []),
        "risks":               data.get("risks", []),
        "definition_of_done":  data.get("definition_of_done", []),
        "tickets_path":        tickets_path,
        "milestone_path":      milestone_path,
        "github_payload_path": gh_payload_path,
        "summary": (
            f"Sprint plan for '{feature}': "
            f"{len(data.get('tickets', []))} tickets. → {tickets_path}."
        ),
    }
