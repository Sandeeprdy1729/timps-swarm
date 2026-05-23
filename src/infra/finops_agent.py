"""
FinOps Agent — analyses cloud costs, generates Infracost estimates,
rightsizing recommendations, and budget alerts.

Input:  infrastructure_description (str), cloud_provider (str),
        monthly_budget_usd (float), top_services (list)
Output: cost_breakdown, recommendations, savings_usd, terraform_changes, report_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record, _run


def finops_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    infra_desc  = args.get("infrastructure_description", "cloud infrastructure")
    cloud       = args.get("cloud_provider", "aws")
    budget      = float(args.get("monthly_budget_usd", 1000))
    services: List[str] = args.get("top_services", ["ec2", "rds", "s3"])

    infracost_out = _run(
        "infracost breakdown --path . --format json 2>/dev/null | "
        "python3 -c \"import json,sys; d=json.load(sys.stdin); "
        "print(json.dumps({'total':d.get('totalMonthlyCost'),'projects':len(d.get('projects',[]))}))\" "
        "2>/dev/null || echo '{\"total\":null}'"
    )[:500]

    system = (
        "You are a FinOps expert. Return JSON: "
        "{cost_breakdown:[{service,monthly_usd:float,annual_usd:float,"
        "pct_of_total:float,optimization_potential:'high'|'medium'|'low'}], "
        "recommendations:[{action,service,monthly_savings_usd:float,effort:'low'|'medium'|'high',"
        "risk:'low'|'medium'|'high',terraform_snippet:str}], "
        "total_monthly_usd:float, projected_savings_usd:float, "
        "budget_alert_config:object, savings_plan_analysis:str, "
        "tagging_strategy:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Cloud: {cloud}\nInfra: {infra_desc}\nBudget: ${budget}/mo\n"
        f"Services: {json.dumps(services)}\n"
        f"Infracost output: {infracost_out}\n\n"
        "Analyse costs and generate savings recommendations."
    )

    data = _parse_json(_llm(prompt, system, "finops_agent"), {
        "cost_breakdown": [], "recommendations": [], "total_monthly_usd": 0,
        "projected_savings_usd": 0,
    })

    savings = data.get("projected_savings_usd", 0)
    ts = _ts()
    report = (
        f"# FinOps Report — {_ts()}\n\n"
        f"**Cloud:** {cloud}  **Total:** ${data.get('total_monthly_usd',0):,.0f}/mo  "
        f"**Projected savings:** ${savings:,.0f}/mo\n\n"
        "## Recommendations\n"
        + "\n".join(
            f"- [{r.get('effort','?').upper()}] {r.get('action','')} "
            f"— save ${r.get('monthly_savings_usd',0):,.0f}/mo"
            for r in data.get("recommendations", [])
        )
    )

    report_path = _save("reports", f"finops_{cloud}_{ts}.md", report)
    _record("finops_agent", f"{cloud}:{infra_desc}", f"Savings: ${savings:,.0f}")

    return {
        "cost_breakdown":      data.get("cost_breakdown", []),
        "recommendations":     data.get("recommendations", []),
        "total_monthly_usd":   data.get("total_monthly_usd", 0),
        "projected_savings_usd": savings,
        "tagging_strategy":    data.get("tagging_strategy", []),
        "report_path":         report_path,
        "summary": (
            f"FinOps ({cloud}): ${data.get('total_monthly_usd',0):,.0f}/mo. "
            f"${savings:,.0f}/mo savings available. → {report_path}."
        ),
    }
