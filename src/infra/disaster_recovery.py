"""
Disaster Recovery Agent — designs RTO/RPO-aware backup strategies,
generates AWS/GCP/Azure DR runbooks, and tests failover procedures.

Input:  system_description (str), rto_minutes (int), rpo_minutes (int),
        cloud_provider (str), critical_components (list)
Output: dr_plan, backup_config, failover_runbook, dr_test_script, report_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def disaster_recovery(args: Dict[str, Any]) -> Dict[str, Any]:
    system_desc   = args.get("system_description", "production service")
    rto           = int(args.get("rto_minutes", 60))
    rpo           = int(args.get("rpo_minutes", 15))
    cloud         = args.get("cloud_provider", "aws")
    components: List[str] = args.get("critical_components", ["database", "api", "storage"])

    system = (
        "You are a disaster recovery architect. Return JSON: "
        "{dr_tier:'hot'|'warm'|'cold', "
        "backup_config:{strategy,frequency,retention_days:int,storage_class},"
        "replication_config:object, "
        "failover_runbook:[{step:int,action,command:str,rollback:str,timeout_min:int}], "
        "dr_test_script:str, "
        "monitoring_alerts:[{alert,condition,action}], "
        "cost_estimate_monthly_usd:float, "
        "compliance_notes:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"System: {system_desc}\nCloud: {cloud}\n"
        f"RTO: {rto}min  RPO: {rpo}min\n"
        f"Critical components: {json.dumps(components)}\n\n"
        "Design comprehensive DR plan."
    )

    data = _parse_json(_llm(prompt, system, "disaster_recovery"), {
        "dr_tier": "warm", "backup_config": {}, "failover_runbook": [], "dr_test_script": "",
    })

    ts = _ts()
    runbook_path = _save("reports", f"dr_runbook_{cloud}_{ts}.md",
                          "# DR Runbook\n\n"
                          + "\n".join(
                              f"{s.get('step','?')}. **{s.get('action','')}**\n"
                              f"   Cmd: `{s.get('command','')}`\n"
                              f"   Rollback: {s.get('rollback','')}"
                              for s in data.get("failover_runbook", [])
                          ))
    test_path    = _save("scripts", f"dr_test_{ts}.sh", data.get("dr_test_script", ""))
    config_path  = _save("code",    f"backup_config_{cloud}_{ts}.json",
                          json.dumps(data.get("backup_config", {}), indent=2))

    _record("disaster_recovery", f"{cloud}:{system_desc}", runbook_path)
    return {
        "dr_tier":             data.get("dr_tier", "warm"),
        "backup_config":       data.get("backup_config", {}),
        "replication_config":  data.get("replication_config", {}),
        "monitoring_alerts":   data.get("monitoring_alerts", []),
        "cost_estimate":       data.get("cost_estimate_monthly_usd", 0),
        "runbook_path":        runbook_path,
        "test_path":           test_path,
        "config_path":         config_path,
        "summary": (
            f"DR ({data.get('dr_tier','?').upper()}) for {system_desc}. "
            f"RTO:{rto}m RPO:{rpo}m. → {runbook_path}."
        ),
    }
