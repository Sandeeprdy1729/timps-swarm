"""
Mobile Agent — generates React Native / Flutter / Expo project scaffolding,
platform-specific code, and deep link / push notification integration.

Input:  app_description (str), framework (str), platforms (list),
        features (list), backend_url (str)
Output: app_code, nav_code, push_notif_code, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def mobile_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    app_desc     = args.get("app_description", "mobile app")
    framework    = args.get("framework", "react_native")
    platforms: List[str] = args.get("platforms", ["ios", "android"])
    features: List[str] = args.get("features", ["auth", "push_notifications", "deep_links"])
    backend_url  = args.get("backend_url", "https://api.example.com")

    system = (
        "You are a mobile app expert. Return JSON: "
        "{app_structure:[{path,content_description}], "
        "main_app_code:str, navigation_code:str, "
        "push_notification_code:str, deep_link_config:str, "
        "platform_configs:{ios:object,android:object}, "
        "performance_checklist:[str], store_submission_checklist:[str]}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"App: {app_desc}\nFramework: {framework}\n"
        f"Platforms: {json.dumps(platforms)}\nFeatures: {json.dumps(features)}\n"
        f"Backend: {backend_url}\n\nGenerate mobile app code."
    )

    data = _parse_json(_llm(prompt, system, "mobile_agent"), {
        "main_app_code": "// app stub", "navigation_code": "", "push_notification_code": "",
    })

    ext = "dart" if framework == "flutter" else "tsx"
    ts = _ts()
    app_path  = _save("code", f"mobile_app_{framework}_{ts}.{ext}", data.get("main_app_code", ""))
    nav_path  = _save("code", f"mobile_navigation_{ts}.{ext}",      data.get("navigation_code", ""))
    push_path = _save("code", f"mobile_push_{ts}.{ext}",            data.get("push_notification_code", ""))

    _record("mobile_agent", f"{framework}:{app_desc}", app_path)
    return {
        "app_structure":        data.get("app_structure", []),
        "platform_configs":     data.get("platform_configs", {}),
        "performance_checklist": data.get("performance_checklist", []),
        "store_submission_checklist": data.get("store_submission_checklist", []),
        "app_path":             app_path,
        "navigation_path":      nav_path,
        "push_path":            push_path,
        "summary": f"Mobile app ({framework}) for '{app_desc}'. → {app_path}.",
    }
