"""
Postmortem Agent — facilitates blameless postmortems using 5 Whys,
Fishbone analysis, action item tracking, and runbook generation.

Input:  incident_description (str), timeline (list), impact (str),
        systems_affected (list), duration_minutes (int)
Output: five_whys, root_causes, action_items, runbook, report_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def postmortem_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    incident  = args.get("incident_description", "service outage")
    timeline: List[Dict] = args.get("timeline", [])
    impact    = args.get("impact", "production users affected")
    systems: List[str] = args.get("systems_affected", [])
    duration  = int(args.get("duration_minutes", 60))

    timeline_text = json.dumps(timeline, indent=2)[:2000] if timeline else "Not provided."

    system = (
        "You are a blameless postmortem facilitator. Return JSON: "
        "{five_whys:[{why:str,answer:str}], "
        "root_causes:[{category:'people'|'process'|'technology',description,evidence}], "
        "contributing_factors:[str], "
        "action_items:[{id:int,priority:'P0'|'P1'|'P2',action,owner_role,due_days:int,"
        "success_metric}], "
        "detection_gap_analysis:str, "
        "runbook_markdown:str, "
        "severity_score:int(1-5), "
        "lessons_learned:[str], "
        "prevention_recommendations:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Incident: {incident}\nImpact: {impact}\n"
        f"Duration: {duration} minutes\nSystems: {json.dumps(systems)}\n\n"
        f"Timeline:\n{timeline_text}\n\n"
        "Conduct blameless postmortem."
    )

    data = _parse_json(_llm(prompt, system, "postmortem_agent"), {
        "five_whys": [], "root_causes": [], "action_items": [], "lessons_learned": [],
    })

    ts = _ts()
    report = (
        f"# Postmortem — {incident[:60]}\n"
        f"**Date:** {ts}  **Duration:** {duration}min  "
        f"**Severity:** P{data.get('severity_score', '?')}\n\n"
        f"**Impact:** {impact}\n\n"
        "## 5 Whys\n"
        + "\n".join(f"{i+1}. {w.get('why','?')} → {w.get('answer','?')}"
                    for i, w in enumerate(data.get("five_whys", [])))
        + "\n\n## Root Causes\n"
        + "\n".join(f"- [{r.get('category','?').upper()}] {r.get('description','')}"
                    for r in data.get("root_causes", []))
        + "\n\n## Action Items\n"
        + "\n".join(
            f"- [{i.get('priority','?')}] {i.get('action','')} "
            f"(due: {i.get('due_days','?')}d)"
            for i in data.get("action_items", [])
        )
        + "\n\n## Lessons Learned\n"
        + "\n".join(f"- {l}" for l in data.get("lessons_learned", []))
    )

    report_path  = _save("reports", f"postmortem_{ts}.md", report)
    runbook_path = _save("scripts", f"runbook_{ts}.md",    data.get("runbook_markdown", ""))

    _record("postmortem_agent", incident, report_path)
    return {
        "five_whys":               data.get("five_whys", []),
        "root_causes":             data.get("root_causes", []),
        "action_items":            data.get("action_items", []),
        "severity_score":          data.get("severity_score", 0),
        "lessons_learned":         data.get("lessons_learned", []),
        "prevention_recommendations": data.get("prevention_recommendations", []),
        "report_path":             report_path,
        "runbook_path":            runbook_path,
        "summary": (
            f"Postmortem: {incident[:60]}. "
            f"Severity P{data.get('severity_score','?')}. "
            f"{len(data.get('action_items', []))} action items. → {report_path}."
        ),
    }
