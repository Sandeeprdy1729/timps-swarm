"""
Load Testing Agent — generates k6 / Artillery / Locust load test scripts
with ramp-up plans, SLO thresholds, and CI integration.

Input:  target_url (str), scenario (str), framework (str),
        peak_vus (int), duration_s (int), slo (dict)
Output: load_test_script, ci_config, results_dashboard, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def load_testing(args: Dict[str, Any]) -> Dict[str, Any]:
    url       = args.get("target_url", "http://localhost:8000")
    scenario  = args.get("scenario", "API load test")
    framework = args.get("framework", "k6")
    peak_vus  = int(args.get("peak_vus", 100))
    duration  = int(args.get("duration_s", 300))
    slo: Dict = args.get("slo", {"p95_ms": 500, "error_rate_pct": 1})

    system = (
        "You are a performance engineering expert. Return JSON: "
        "{load_test_script:str, ramp_up_plan:[{stage,vus:int,duration:str}], "
        "ci_config_yaml:str, grafana_dashboard_json:str, "
        "baseline_endpoints:[{method,path,expected_p95_ms}], "
        "bottleneck_checklist:[str], tuning_recommendations:[str]}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"URL: {url}\nScenario: {scenario}\nFramework: {framework}\n"
        f"Peak VUs: {peak_vus}\nDuration: {duration}s\n"
        f"SLO: {json.dumps(slo)}\n\n"
        "Generate load test suite."
    )

    data = _parse_json(_llm(prompt, system, "load_testing"), {
        "load_test_script": "// k6 stub", "ramp_up_plan": [], "ci_config_yaml": "",
    })

    ext_map = {"k6": "js", "artillery": "yml", "locust": "py"}
    ext = ext_map.get(framework, "js")
    ts = _ts()
    script_path    = _save("tests",   f"load_{framework}_{ts}.{ext}",   data.get("load_test_script", ""))
    ci_path        = _save("scripts", f"ci_load_{framework}_{ts}.yml",  data.get("ci_config_yaml", ""))
    dashboard_path = _save("reports", f"grafana_dashboard_{ts}.json",   data.get("grafana_dashboard_json", ""))

    _record("load_testing", f"{framework}:{url}", script_path)
    return {
        "ramp_up_plan":            data.get("ramp_up_plan", []),
        "bottleneck_checklist":    data.get("bottleneck_checklist", []),
        "tuning_recommendations":  data.get("tuning_recommendations", []),
        "script_path":             script_path,
        "ci_path":                 ci_path,
        "dashboard_path":          dashboard_path,
        "summary": f"Load test ({framework}) for {url}: {peak_vus} VUs, {duration}s → {script_path}.",
    }
