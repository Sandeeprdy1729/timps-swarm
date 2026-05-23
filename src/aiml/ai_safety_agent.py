"""
AI Safety Agent — OWASP LLM Top 10 audit for AI applications.
Checks prompt injection, insecure output handling, excessive agency,
sensitive data exposure, and all 10 LLM vulnerability classes.

Input:  code (str) | path (str), app_description (str), strictness (str)
Output: overall_risk, findings, guardrail_recommendations, report_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


_OWASP_LLM = (
    "LLM01:Prompt Injection | LLM02:Insecure Output Handling | "
    "LLM03:Training Data Poisoning | LLM04:Model DoS | "
    "LLM05:Supply Chain | LLM06:Sensitive Info Disclosure | "
    "LLM07:Insecure Plugin Design | LLM08:Excessive Agency | "
    "LLM09:Overreliance | LLM10:Model Theft"
)


def ai_safety_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    code        = args.get("code", "")
    path_str    = args.get("path", "")
    app_desc    = args.get("app_description", "an AI application")
    strictness  = args.get("strictness", "standard")

    if not code and path_str:
        p = Path(path_str)
        if p.is_file():
            code = p.read_text(encoding="utf-8", errors="ignore")
        elif p.is_dir():
            parts = []
            for f in list(p.rglob("*.py"))[:10]:
                parts.append(f.read_text(encoding="utf-8", errors="ignore")[:800])
            code = "\n\n".join(parts)

    system = (
        f"You are an AI safety expert. Audit code against OWASP LLM Top 10: {_OWASP_LLM}. "
        "Return JSON: {overall_risk:'critical'|'high'|'medium'|'low', "
        "findings:[{id,title,severity,code_location,description,fix,cwe}], "
        "prompt_injection_vectors:[str], sensitive_data_exposure:[str], "
        "excessive_agency_risks:[str], guardrail_recommendations:[str], "
        "remediation_code:str, compliance_notes:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"Application: {app_desc}\nStrictness: {strictness}\n\n"
        f"Source:\n```python\n{code[:7000]}\n```"
    )

    data = _parse_json(_llm(prompt, system, "ai_safety_agent"), {
        "overall_risk": "unknown", "findings": [], "guardrail_recommendations": [],
    })

    findings  = data.get("findings", [])
    critical: List[Dict] = [f for f in findings if f.get("severity") in ("critical", "high")]

    report = (
        f"# AI Safety Audit — {_ts()}\n\n"
        f"**App:** {app_desc}  **Risk:** {data.get('overall_risk','?').upper()}\n"
        f"**Findings:** {len(findings)} ({len(critical)} critical/high)\n\n"
        "## Findings\n"
        + "\n".join(
            f"### {f.get('id','?')}: {f.get('title','?')} [{f.get('severity','?').upper()}]\n"
            f"Location: {f.get('code_location','N/A')}\n"
            f"Fix: {f.get('fix','')}\n"
            for f in findings
        )
        + "\n\n## Guardrails\n"
        + "\n".join(f"- {g}" for g in data.get("guardrail_recommendations", []))
    )

    report_path = _save("reports", f"ai_safety_{_ts()}.md", report)
    if data.get("remediation_code"):
        _save("code", f"ai_safety_fixes_{_ts()}.py", data["remediation_code"])

    _record("ai_safety_agent", app_desc, f"Risk:{data.get('overall_risk')} | {len(findings)} findings")
    return {
        "overall_risk":               data.get("overall_risk", "unknown"),
        "findings":                   findings,
        "critical_count":             len(critical),
        "prompt_injection_vectors":   data.get("prompt_injection_vectors", []),
        "sensitive_data_exposure":    data.get("sensitive_data_exposure", []),
        "excessive_agency_risks":     data.get("excessive_agency_risks", []),
        "guardrail_recommendations":  data.get("guardrail_recommendations", []),
        "report_path":                report_path,
        "summary": (
            f"AI safety: {data.get('overall_risk','?').upper()} risk. "
            f"{len(findings)} findings ({len(critical)} critical/high). → {report_path}."
        ),
    }
