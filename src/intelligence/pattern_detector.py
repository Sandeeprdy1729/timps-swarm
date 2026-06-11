"""
Pattern Detector — finds duplicate code blocks, god classes,
missed abstractions, and magic numbers.

Input:  code (str) | path (str), language (str), min_lines (int)
Output: patterns, god_classes, magic_numbers, refactor_priority,
        estimated_loc_reduction, report_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record


def pattern_detector(args: Dict[str, Any]) -> Dict[str, Any]:
    code      = args.get("code", "")
    path_str  = args.get("path", "")
    language  = args.get("language", "python")
    min_lines = int(args.get("min_lines", 10))

    if not code and path_str:
        p = Path(path_str)
        if p.is_file():
            code = p.read_text(encoding="utf-8", errors="ignore")
        elif p.is_dir():
            parts = []
            for f in list(p.rglob("*.py"))[:20]:
                parts.append(f"### {f.name}\n{f.read_text(encoding='utf-8', errors='ignore')[:600]}")
            code = "\n\n".join(parts)

    if not code.strip():
        return {"error": "No code provided", "patterns": []}

    system = (
        f"You are a code-quality expert. Find ALL repeated patterns (blocks ≥ {min_lines} lines), "
        "near-duplicate functions, god classes (>300 lines), missed factory/strategy patterns, "
        "magic numbers. Return JSON: {patterns: [{type, locations:[str], lines, description, "
        "suggested_abstraction}], god_classes:[str], magic_numbers:[{value, locations:[str]}], "
        "refactor_priority:'high'|'medium'|'low', estimated_loc_reduction:int}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Language: {language}  Min block: {min_lines} lines\n\n"
        f"Code:\n```{language}\n{code[:8000]}\n```"
    )

    data = _parse_json(_llm(prompt, system, "pattern_detector"), {
        "patterns": [], "god_classes": [], "magic_numbers": [],
        "refactor_priority": "medium", "estimated_loc_reduction": 0,
    })

    report = (
        f"# Pattern Detector Report — {_ts()}\n\n"
        f"**Language:** {language}  **Patterns:** {len(data.get('patterns', []))}\n"
        f"**LoC reduction:** ~{data.get('estimated_loc_reduction', 0)}  "
        f"**Priority:** {data.get('refactor_priority', '?').upper()}\n\n"
        "## Patterns\n"
        + "\n".join(
            f"### {p.get('type','?')} ({p.get('lines','?')} lines)\n"
            f"Locations: {', '.join(p.get('locations', []))}\n"
            f"Suggested: {p.get('suggested_abstraction', '')}\n"
            for p in data.get("patterns", [])
        )
        + "\n\n## God Classes\n"
        + "\n".join(f"- `{c}`" for c in data.get("god_classes", []))
    )

    report_path = _save("reports", f"pattern_detector_{_ts()}.md", report)
    _record("pattern_detector", path_str or "inline", report[:400])

    return {
        "patterns":              data.get("patterns", []),
        "god_classes":           data.get("god_classes", []),
        "magic_numbers":         data.get("magic_numbers", []),
        "refactor_priority":     data.get("refactor_priority", "medium"),
        "estimated_loc_reduction": data.get("estimated_loc_reduction", 0),
        "report_path":           report_path,
        "summary": (
            f"{len(data.get('patterns', []))} patterns, "
            f"{len(data.get('god_classes', []))} god classes. "
            f"~{data.get('estimated_loc_reduction', 0)} LoC reducible."
        ),
    }
