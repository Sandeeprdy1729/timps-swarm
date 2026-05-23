"""
CLI Tool Agent — generates professional CLI tools using Click (Python),
Cobra (Go), or Commander.js (Node), with help text, shell completions, config.

Input:  tool_description (str), commands (list), language (str), config_format (str)
Output: main_code, help_text, completion_script, code_path
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def cli_tool_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    tool_desc     = args.get("tool_description", "CLI tool")
    commands: List[str] = args.get("commands", ["run", "config", "status", "version"])
    language      = args.get("language", "python")
    config_format = args.get("config_format", "toml")

    framework_map = {"python": "click", "go": "cobra", "javascript": "commander", "typescript": "commander"}
    framework = framework_map.get(language, "click")

    system = (
        "You are a CLI tool expert. Return JSON: "
        "{main_code:str, command_modules:[{name,code}], "
        "config_schema:object, shell_completion_script:str, "
        "dockerfile:str, release_workflow_yaml:str, "
        "test_code:str, manpage_content:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"Tool: {tool_desc}\nLanguage: {language} ({framework})\n"
        f"Commands: {json.dumps(commands)}\nConfig format: {config_format}\n\n"
        "Generate complete CLI tool."
    )

    data = _parse_json(_llm(prompt, system, "cli_tool_agent"), {
        "main_code": "# cli stub", "command_modules": [], "shell_completion_script": "",
    })

    ext_map = {"python": "py", "go": "go", "javascript": "js", "typescript": "ts"}
    ext = ext_map.get(language, "py")
    ts = _ts()
    main_path       = _save("code",    f"cli_main_{ts}.{ext}",           data.get("main_code", ""))
    completion_path = _save("scripts", f"cli_completion_{ts}.sh",        data.get("shell_completion_script", ""))
    test_path       = _save("tests",   f"cli_tests_{ts}.{ext}",          data.get("test_code", ""))
    release_path    = _save("scripts", f"cli_release_{ts}.yml",          data.get("release_workflow_yaml", ""))

    _record("cli_tool_agent", f"{language}:{tool_desc}", main_path)
    return {
        "command_count":         len(commands),
        "framework":             framework,
        "config_schema":         data.get("config_schema", {}),
        "main_path":             main_path,
        "completion_path":       completion_path,
        "test_path":             test_path,
        "release_workflow_path": release_path,
        "summary": f"CLI tool ({framework}) '{tool_desc}'. {len(commands)} commands. → {main_path}.",
    }
