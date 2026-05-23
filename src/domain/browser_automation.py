"""
Browser Automation Agent — generates Playwright E2E test suites,
page object models, CI config, and visual regression setup.

Input:  url (str), user_flows (list), browser (str), ci_system (str),
        visual_regression (bool)
Output: test_suite_code, page_objects, ci_config, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def browser_automation(args: Dict[str, Any]) -> Dict[str, Any]:
    url       = args.get("url", "https://app.example.com")
    flows: List[str] = args.get("user_flows", ["login", "checkout", "profile"])
    browser   = args.get("browser", "chromium")
    ci_system = args.get("ci_system", "github_actions")
    visual_regression = args.get("visual_regression", False)

    system = (
        "You are a Playwright E2E expert. Return JSON: "
        "{test_suite_code:str, page_objects:[{name,code}], "
        "fixtures_code:str, ci_config:str, "
        "playwright_config:str, visual_regression_setup:str, "
        "accessibility_tests:str, performance_tests:str}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"URL: {url}\nBrowser: {browser}\nCI: {ci_system}\n"
        f"Flows: {json.dumps(flows)}\nVisual regression: {visual_regression}\n\n"
        "Generate E2E test suite."
    )

    data = _parse_json(_llm(prompt, system, "browser_automation"), {
        "test_suite_code": "// tests stub", "page_objects": [], "ci_config": "",
    })

    ts = _ts()
    tests_path  = _save("tests",   f"e2e_suite_{ts}.spec.ts",        data.get("test_suite_code", ""))
    fixtures    = _save("tests",   f"e2e_fixtures_{ts}.ts",          data.get("fixtures_code", ""))
    ci_path     = _save("scripts", f"ci_e2e_{ci_system}_{ts}.yml",   data.get("ci_config", ""))
    pw_config   = _save("code",    f"playwright_config_{ts}.ts",     data.get("playwright_config", ""))

    for po in data.get("page_objects", [])[:5]:
        _save("tests", f"pages_{po.get('name','po')}_{ts}.ts", po.get("code", ""))

    _record("browser_automation", f"{browser}:{url}", tests_path)
    return {
        "flows_covered":    flows,
        "page_objects":     [p.get("name") for p in data.get("page_objects", [])],
        "tests_path":       tests_path,
        "ci_path":          ci_path,
        "playwright_config": pw_config,
        "summary": f"E2E suite ({browser}) for {url}. {len(flows)} flows. → {tests_path}.",
    }
