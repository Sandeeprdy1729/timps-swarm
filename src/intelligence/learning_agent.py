"""
Learning Agent — analyses high-scoring swarm runs, distils patterns,
and optionally upgrades agent system prompts.

Input:  target_agent (str), min_score (int), top_k (int), apply (bool)
Output: improvements, meta_patterns, recommended_actions, report_path
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def learning_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    target    = args.get("target_agent", "all")
    min_score = int(args.get("min_score", 8))
    top_k     = int(args.get("top_k", 10))
    apply     = args.get("apply", False)

    mem_dir   = Path(os.environ.get("TIMPS_MEMORY_DIR", str(Path.home() / ".timps" / "memory")))
    runs_file = mem_dir / "runs.jsonl"
    all_runs: List[Dict] = []
    if runs_file.exists():
        for line in runs_file.read_text().splitlines():
            try:
                all_runs.append(json.loads(line))
            except Exception:
                pass

    good_runs = [
        r for r in all_runs
        if r.get("success") and (target == "all" or r.get("agent") == target)
    ][-(top_k * 5):]

    if not good_runs:
        return {
            "improvements": [],
            "summary": f"No runs found for '{target}'. Complete some tasks first.",
        }

    run_corpus = json.dumps(good_runs[:top_k], indent=2, default=str)[:6000]

    system = (
        "You are a meta-learning engineer. Analyse successful agent runs and extract "
        "reusable prompt patterns and few-shot examples. Return JSON: "
        "{agent_improvements:[{agent, improved_system_prompt_fragment, "
        "few_shot_examples:[{input,output}], key_learnings:[str]}], "
        "meta_patterns:[str], recommended_actions:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Target: {target}  Analysing {len(good_runs)} runs  Min score: {min_score}\n\n"
        f"Runs:\n{run_corpus}"
    )

    data = _parse_json(_llm(prompt, system, "learning_agent"), {
        "agent_improvements": [], "meta_patterns": [], "recommended_actions": [],
    })

    improvements  = data.get("agent_improvements", [])
    saved_paths: List[str] = []

    if apply and improvements:
        for imp in improvements:
            fragment = imp.get("improved_system_prompt_fragment", "")
            agent_n  = imp.get("agent", "unknown")
            if fragment:
                saved_paths.append(
                    _save("prompts", f"{agent_n}_improved_{_ts()}.md",
                          f"# Improved prompt fragment — {agent_n}\n\n{fragment}")
                )

    report = (
        f"# Learning Agent Report — {_ts()}\n\n"
        f"**Target:** {target}  **Runs analysed:** {len(good_runs)}\n\n"
        "## Improvements\n"
        + "\n".join(
            f"### {i.get('agent','?')}\n"
            + "\n".join(f"- {k}" for k in i.get("key_learnings", []))
            for i in improvements
        )
        + "\n\n## Meta Patterns\n"
        + "\n".join(f"- {p}" for p in data.get("meta_patterns", []))
        + "\n\n## Recommended Actions\n"
        + "\n".join(f"- {a}" for a in data.get("recommended_actions", []))
    )

    report_path = _save("reports", f"learning_agent_{_ts()}.md", report)
    _record("learning_agent", target, report[:400])

    return {
        "improvements":        improvements,
        "meta_patterns":       data.get("meta_patterns", []),
        "recommended_actions": data.get("recommended_actions", []),
        "saved_prompt_paths":  saved_paths,
        "report_path":         report_path,
        "summary": (
            f"Analysed {len(good_runs)} runs. "
            f"{len(improvements)} improvement(s) generated. "
            f"{'Prompts written.' if apply else 'Pass apply=True to save.'}"
        ),
    }
