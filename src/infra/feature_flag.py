"""
Feature Flag Agent — designs feature flag strategy and generates
LaunchDarkly / Flagsmith / GrowthBook / homegrown configuration.

Input:  feature_description (str), provider (str), targeting_rules (list),
        rollout_pct (float), kill_switch (bool)
Output: flag_config, sdk_code, targeting_code, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def feature_flag(args: Dict[str, Any]) -> Dict[str, Any]:
    feature     = args.get("feature_description", "new feature")
    provider    = args.get("provider", "launchdarkly")
    rules: List[Dict] = args.get("targeting_rules", [])
    rollout_pct = float(args.get("rollout_pct", 10.0))
    kill_switch = bool(args.get("kill_switch", True))

    system = (
        "You are a feature flag expert. Return JSON: "
        "{flag_config:object, sdk_init_code:str, "
        "flag_evaluation_code:str, targeting_rules_yaml:str, "
        "gradual_rollout_plan:[{stage:int,pct:float,criteria:str}], "
        "cleanup_checklist:[str], observability_integration:str, "
        "flag_naming_conventions:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Feature: {feature}\nProvider: {provider}\n"
        f"Initial rollout: {rollout_pct}%\nKill switch: {kill_switch}\n"
        f"Targeting rules: {json.dumps(rules[:5])}\n\n"
        "Generate feature flag setup."
    )

    data = _parse_json(_llm(prompt, system, "feature_flag"), {
        "flag_config": {}, "sdk_init_code": "# sdk stub", "flag_evaluation_code": "",
    })

    ts = _ts()
    config_path = _save("code", f"flag_config_{provider}_{ts}.json",
                          json.dumps(data.get("flag_config", {}), indent=2))
    sdk_path    = _save("code", f"feature_flag_{provider}_{ts}.py", data.get("sdk_init_code", ""))
    rules_path  = _save("code", f"flag_rules_{ts}.yaml",            data.get("targeting_rules_yaml", ""))

    _record("feature_flag", f"{provider}:{feature}", config_path)
    return {
        "flag_config":         data.get("flag_config", {}),
        "gradual_rollout_plan": data.get("gradual_rollout_plan", []),
        "cleanup_checklist":   data.get("cleanup_checklist", []),
        "config_path":         config_path,
        "sdk_path":            sdk_path,
        "rules_path":          rules_path,
        "summary": f"Feature flag ({provider}) for '{feature}': {rollout_pct}% rollout. → {config_path}.",
    }
