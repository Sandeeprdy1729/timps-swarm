"""
A/B Testing Agent — designs statistically rigorous experiments,
power analysis, GrowthBook / Optimizely config, and result analysis.

Input:  hypothesis (str), baseline_conversion (float), mde (float),
        traffic_pct (float), days (int), framework (str)
Output: sample_size, config, analysis_code, report_path
"""
from __future__ import annotations

import math
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def ab_testing_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    hypothesis  = args.get("hypothesis", "Variant B increases conversion")
    baseline    = float(args.get("baseline_conversion", 0.05))
    mde         = float(args.get("mde", 0.15))
    traffic_pct = float(args.get("traffic_pct", 0.5))
    days        = int(args.get("days", 14))
    framework   = args.get("framework", "growthbook")

    # Welch's approximate sample size
    p1 = baseline
    p2 = baseline * (1 + mde)
    z_alpha, z_beta = 1.96, 0.84
    pooled = (p1 + p2) / 2
    n = math.ceil(
        ((z_alpha * math.sqrt(2 * pooled * (1 - pooled))
          + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2)
        / (p2 - p1) ** 2
    )

    system = (
        "You are an experimentation expert. Return JSON: "
        "{experiment_config:object, feature_flag_code:str (Python), "
        "assignment_code:str, analysis_code:str (statsmodels), "
        "result_interpretation_guide:str, peeking_problem_notes:str, "
        "sequential_testing_alternative:str, "
        "exclusion_criteria:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Hypothesis: {hypothesis}\nBaseline conversion: {baseline:.1%}\n"
        f"MDE: {mde:.1%}\nTraffic split: {traffic_pct:.0%}\nDuration: {days}d\n"
        f"Framework: {framework}\nCalculated sample size: {n} per variant\n\n"
        "Generate A/B test implementation."
    )

    data = _parse_json(_llm(prompt, system, "ab_testing_agent"), {
        "experiment_config": {}, "analysis_code": "# analysis stub",
    })

    ts = _ts()
    config_path   = _save("code",    f"ab_test_config_{framework}_{ts}.json",
                           str(data.get("experiment_config", {})))
    analysis_path = _save("code",    f"ab_analysis_{ts}.py",   data.get("analysis_code", ""))
    report_path   = _save("reports", f"ab_test_design_{ts}.md",
                           f"# A/B Test Design\n\n"
                           f"**Hypothesis:** {hypothesis}\n"
                           f"**Sample size:** {n}/variant\n"
                           f"**Duration:** {days} days\n"
                           f"**Baseline:** {baseline:.1%} | **MDE:** {mde:.1%}\n\n"
                           + data.get("result_interpretation_guide", ""))

    _record("ab_testing_agent", hypothesis, report_path)
    return {
        "sample_size_per_variant": n,
        "experiment_config":       data.get("experiment_config", {}),
        "peeking_problem_notes":   data.get("peeking_problem_notes", ""),
        "exclusion_criteria":      data.get("exclusion_criteria", []),
        "config_path":             config_path,
        "analysis_path":           analysis_path,
        "report_path":             report_path,
        "summary": f"A/B test: {n} users/variant, {days} days. → {report_path}.",
    }
