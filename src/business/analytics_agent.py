"""
Analytics Agent — generates event tracking, funnel analysis, and
PostHog/Mixpanel/Amplitude integration code.

Input:  product_description (str), events (list), provider (str),
        funnel_steps (list), retention_window_days (int)
Output: tracking_code, funnel_analysis, dashboard_config, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def analytics_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    product  = args.get("product_description", "SaaS product")
    events: List[str] = args.get("events", ["signup", "activation", "payment", "churn"])
    provider = args.get("provider", "posthog")
    funnel: List[str] = args.get("funnel_steps", ["visit", "signup", "activation", "payment"])
    retention = int(args.get("retention_window_days", 30))

    system = (
        "You are a product analytics expert. Return JSON: "
        "{tracking_code:str, event_schema:[{event,properties:{key:{type,required:bool}}}], "
        "funnel_analysis_code:str, retention_analysis_code:str, "
        "dashboard_config:object, alert_queries:[{name,query,threshold}], "
        "north_star_metric:str, lagging_indicators:[str]}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Product: {product}\nProvider: {provider}\nRetention window: {retention}d\n"
        f"Events: {json.dumps(events)}\nFunnel: {json.dumps(funnel)}\n\n"
        "Generate complete analytics implementation."
    )

    data = _parse_json(_llm(prompt, system, "analytics_agent"), {
        "tracking_code": "# analytics stub", "event_schema": [], "dashboard_config": {},
    })

    ts = _ts()
    code_path     = _save("code",     f"analytics_{provider}_{ts}.py",  data.get("tracking_code", ""))
    funnel_path   = _save("code",     f"funnel_analysis_{ts}.py",       data.get("funnel_analysis_code", ""))
    dashboard_path = _save("reports", f"dashboard_{provider}_{ts}.json",
                            json.dumps(data.get("dashboard_config", {}), indent=2))

    _record("analytics_agent", f"{provider}:{product}", code_path)
    return {
        "event_schema":          data.get("event_schema", []),
        "north_star_metric":     data.get("north_star_metric", ""),
        "lagging_indicators":    data.get("lagging_indicators", []),
        "alert_queries":         data.get("alert_queries", []),
        "code_path":             code_path,
        "funnel_path":           funnel_path,
        "dashboard_path":        dashboard_path,
        "summary": f"Analytics ({provider}): {len(events)} events, {len(funnel)}-step funnel → {code_path}.",
    }
