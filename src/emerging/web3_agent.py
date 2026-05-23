"""
Web3 Agent — smart contract security audit using Slither/Mythril patterns,
generates Solidity code with best practices and gas optimisation.

Input:  contract_code (str) | description (str), chain (str), standard (str)
Output: audit_findings, gas_report, hardhat_tests, optimised_code, report_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src._helpers import _ts, _llm, _save, _parse_json, _record, _run


def web3_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    contract_code = args.get("contract_code", "")
    description   = args.get("description", "ERC-20 token")
    chain         = args.get("chain", "ethereum")
    standard      = args.get("standard", "ERC-20")

    if not contract_code and args.get("contract_path"):
        try:
            contract_code = Path(args["contract_path"]).read_text(encoding="utf-8")
        except Exception:
            pass

    # Try slither
    slither_out = ""
    if args.get("contract_path"):
        slither_out = _run(
            f"slither {args['contract_path']} --print human-summary 2>&1 | head -30"
        )

    system = (
        "You are a smart-contract security expert (Slither/Mythril/SWC). Return JSON: "
        "{audit_findings:[{swc_id,title,severity:'critical'|'high'|'medium'|'low'|'info',"
        "description,location,fix_snippet}], "
        "gas_report:[{function,gas_estimate:int,optimization:str}], "
        "hardhat_test_code:str, optimised_contract_code:str, "
        "deployment_script:str, "
        "reentrancy_guards:[str], access_control_analysis:str}. "
        "Output ONLY valid JSON."
    )
    prompt = (
        f"Chain: {chain}\nStandard: {standard}\nDescription: {description}\n"
        f"Slither output: {slither_out[:1000]}\n\n"
        f"Contract:\n```solidity\n{contract_code[:6000] or '// generate from description'}\n```\n\n"
        "Audit and optimise."
    )

    data = _parse_json(_llm(prompt, system, "web3_agent"), {
        "audit_findings": [], "gas_report": [], "hardhat_test_code": "",
        "optimised_contract_code": contract_code or "// contract stub",
    })

    critical = [f for f in data.get("audit_findings", []) if f.get("severity") == "critical"]
    ts = _ts()
    contract_path  = _save("code",    f"contract_optimised_{ts}.sol",    data.get("optimised_contract_code", ""))
    tests_path     = _save("tests",   f"hardhat_tests_{ts}.js",          data.get("hardhat_test_code", ""))
    deploy_path    = _save("scripts", f"deploy_{chain}_{ts}.js",         data.get("deployment_script", ""))
    report_path    = _save("reports", f"web3_audit_{ts}.md",
                            "# Smart Contract Audit\n\n"
                            + "\n".join(
                                f"### {f.get('swc_id','?')}: {f.get('title','?')} [{f.get('severity','?').upper()}]\n"
                                f"{f.get('description','')}\nFix: {f.get('fix_snippet','')[:200]}"
                                for f in data.get("audit_findings", [])
                            ))

    _record("web3_agent", f"{chain}:{standard}", report_path)
    return {
        "audit_findings":  data.get("audit_findings", []),
        "critical_count":  len(critical),
        "gas_report":      data.get("gas_report", []),
        "contract_path":   contract_path,
        "tests_path":      tests_path,
        "deploy_path":     deploy_path,
        "report_path":     report_path,
        "summary": (
            f"Web3 audit ({chain}/{standard}): "
            f"{len(data.get('audit_findings',[]))} findings ({len(critical)} critical). → {report_path}."
        ),
    }
