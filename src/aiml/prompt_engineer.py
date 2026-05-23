"""
Prompt Engineer — scans codebases for hardcoded LLM prompts and rewrites
them with chain-of-thought, few-shot examples, and structured outputs.

Input:  code (str) | path (str), task (str), style (str)
Output: found_prompts, rewritten_prompts, instrumented_code, report_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def prompt_engineer(args: Dict[str, Any]) -> Dict[str, Any]:
    code     = args.get("code", "")
    path_str = args.get("path", "")
    task     = args.get("task", "AI application")
    style    = args.get("style", "auto")

    if not code and path_str:
        p = Path(path_str)
        if p.is_file():
            code = p.read_text(encoding="utf-8", errors="ignore")
        elif p.is_dir():
            parts = []
            for f in list(p.rglob("*.py"))[:10]:
                parts.append(f.read_text(encoding="utf-8", errors="ignore")[:1000])
            code = "\n\n".join(parts)

    system = (
        "You are a prompt engineering expert. Scan code for LLM prompts and rewrite them "
        "using chain-of-thought, XML tags, few-shot examples, output schemas, "
        "system/user separation, and temperature guidance. Return JSON: "
        "{found_prompts:[{location,original,issues:[str]}], "
        "rewritten_prompts:[{location,original,rewritten,techniques_applied:[str],"
        "expected_quality_gain:str}], missing_system_prompts:[str], "
        "instrumented_code:str, benchmark_plan:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"App task: {task}\nStyle: {style}\n\n"
        f"Source:\n```python\n{code[:7000]}\n```"
    )

    data = _parse_json(_llm(prompt, system, "prompt_engineer"), {
        "found_prompts": [], "rewritten_prompts": [], "instrumented_code": code,
    })

    rewritten = data.get("rewritten_prompts", [])
    report = (
        f"# Prompt Engineer Report — {_ts()}\n\n"
        f"**Task:** {task}  **Style:** {style}\n"
        f"**Found:** {len(data.get('found_prompts', []))}  **Rewritten:** {len(rewritten)}\n\n"
        "## Rewrites\n"
        + "\n".join(
            f"### {r.get('location','?')}\n"
            f"Techniques: {', '.join(r.get('techniques_applied', []))}\n"
            f"Gain: {r.get('expected_quality_gain', '')}\n"
            f"```python\n{r.get('rewritten', '')}\n```\n"
            for r in rewritten
        )
    )

    report_path = _save("reports", f"prompt_engineer_{_ts()}.md", report)
    if data.get("instrumented_code"):
        _save("code", f"prompts_rewritten_{_ts()}.py", data["instrumented_code"])

    _record("prompt_engineer", task, report[:400])
    return {
        "found_prompts":        data.get("found_prompts", []),
        "rewritten_prompts":    rewritten,
        "missing_system_prompts": data.get("missing_system_prompts", []),
        "instrumented_code":    data.get("instrumented_code", ""),
        "benchmark_plan":       data.get("benchmark_plan", ""),
        "report_path":          report_path,
        "summary": (
            f"Found {len(data.get('found_prompts', []))} prompts, "
            f"rewrote {len(rewritten)} with {style} style."
        ),
    }
