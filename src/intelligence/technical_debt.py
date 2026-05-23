"""
Technical Debt Agent — quantifies debt per file and produces a
prioritised paydown roadmap using radon, git churn, and TODO density.

Input:  path (str), language (str), include_git_churn (bool)
Output: overall_debt_score, file_scores, paydown_roadmap, quick_wins,
        debt_categories, total_debt_hours, report_path
"""
from __future__ import annotations

from typing import Any, Dict

from src._helpers import _ts, _llm, _run, _save, _parse_json, _record


def technical_debt(args: Dict[str, Any]) -> Dict[str, Any]:
    repo_path  = args.get("path", ".")
    language   = args.get("language", "python")
    use_churn  = args.get("include_git_churn", True)

    radon_output = ""
    if language == "python":
        radon_output = _run(f"python3 -m radon cc {repo_path} -s -j 2>/dev/null || echo 'radon unavailable'")[:3000]

    churn_output = ""
    if use_churn:
        churn_output = _run(
            f"git -C {repo_path} log --format= --name-only "
            "| sort | uniq -c | sort -rn | head -30"
        )

    todo_output = _run(
        f"grep -r --include='*.py' -c 'TODO\\|FIXME\\|HACK\\|XXX' "
        f"{repo_path} 2>/dev/null | sort -t: -k2 -rn | head -20"
    )

    system = (
        "You are a technical-debt expert. Return JSON: "
        "{overall_debt_score:int(0-100), "
        "file_scores:[{file,complexity,churn,todos,debt_score:int,effort:'S'|'M'|'L'|'XL'}], "
        "total_debt_hours:int, "
        "paydown_roadmap:[{priority:int,file,action,effort,expected_improvement}], "
        "quick_wins:[str], "
        "debt_categories:{legacy_code,missing_tests,poor_naming,complex_logic,outdated_deps}}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Language: {language}  Repo: {repo_path}\n\n"
        f"Cyclomatic complexity:\n{radon_output}\n\n"
        f"Git churn:\n{churn_output}\n\n"
        f"TODO density:\n{todo_output}"
    )

    data = _parse_json(_llm(prompt, system, "technical_debt"), {
        "overall_debt_score": 50, "file_scores": [], "total_debt_hours": 0,
        "paydown_roadmap": [], "quick_wins": [], "debt_categories": {},
    })

    report = (
        f"# Technical Debt Report — {_ts()}\n\n"
        f"**Score:** {data.get('overall_debt_score', 0)}/100  "
        f"**Effort:** ~{data.get('total_debt_hours', 0)}h\n\n"
        "## Debt Categories\n"
        + "\n".join(f"- {k}: {v}" for k, v in data.get("debt_categories", {}).items())
        + "\n\n## Paydown Roadmap\n"
        + "\n".join(
            f"{r.get('priority','?')}. **{r.get('file','?')}** — {r.get('action','')} "
            f"(effort: {r.get('effort','?')})"
            for r in data.get("paydown_roadmap", [])
        )
        + "\n\n## Quick Wins\n"
        + "\n".join(f"- {q}" for q in data.get("quick_wins", []))
    )

    report_path = _save("reports", f"tech_debt_{_ts()}.md", report)
    _record("technical_debt", repo_path, report[:400])

    return {
        "overall_debt_score": data.get("overall_debt_score", 0),
        "total_debt_hours":   data.get("total_debt_hours", 0),
        "file_scores":        data.get("file_scores", []),
        "paydown_roadmap":    data.get("paydown_roadmap", []),
        "quick_wins":         data.get("quick_wins", []),
        "debt_categories":    data.get("debt_categories", {}),
        "report_path":        report_path,
        "summary": (
            f"Debt: {data.get('overall_debt_score', 0)}/100. "
            f"~{data.get('total_debt_hours', 0)}h to pay down. "
            f"{len(data.get('paydown_roadmap', []))} items in roadmap."
        ),
    }
