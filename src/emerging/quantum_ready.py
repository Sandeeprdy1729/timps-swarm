"""
Quantum-Ready Agent — identifies algorithms with quantum speedup potential,
generates Qiskit circuits, post-quantum migration plan, and NIST PQC guidance.

Input:  codebase_description (str), path (str), algorithms (list),
        threat_horizon_years (int)
Output: quantum_risk_map, qiskit_circuits, pqc_migration_plan, report_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


_QUANTUM_VULNERABLE = [
    "RSA", "ECDSA", "DH", "ECDH", "DSA", "AES-128",
    "SHA-1", "MD5",
]


def quantum_ready(args: Dict[str, Any]) -> Dict[str, Any]:
    desc        = args.get("codebase_description", "software system")
    path_str    = args.get("path", ".")
    algorithms: List[str] = args.get("algorithms", [])
    horizon     = int(args.get("threat_horizon_years", 10))

    # Grep for crypto usage
    grep_out = ""
    try:
        from src._helpers import _run
        grep_out = _run(
            f"grep -r --include='*.py' --include='*.js' --include='*.go' "
            f"-i 'rsa\\|ecdsa\\|aes\\|sha256\\|md5\\|hmac\\|jwt\\|ssl\\|tls' "
            f"{path_str} 2>/dev/null | head -30"
        )[:2000]
    except Exception:
        pass

    corpus = ""
    if path_str and Path(path_str).is_dir():
        for f in list(Path(path_str).rglob("*.py"))[:10]:
            try:
                corpus += f"\n### {f.name}\n" + f.read_text(encoding="utf-8", errors="ignore")[:500]
            except Exception:
                pass

    system = (
        "You are a quantum computing and post-quantum cryptography expert. Return JSON: "
        "{quantum_risk_map:[{algorithm,location,vulnerability,harvest_now_attack:bool,"
        "migration_priority:'immediate'|'high'|'medium'|'low'}], "
        "quantum_speedup_opportunities:[{algorithm_class,classical_complexity,quantum_complexity,"
        "qiskit_circuit_sketch:str}], "
        "pqc_migration_plan:[{step:int,current,replacement,nist_standard,"
        "migration_code:str}], "
        "harvest_now_risk_score:int(0-100), "
        "crypto_agility_recommendations:[str], "
        "timeline_analysis:str}. Output ONLY valid JSON."
    )
    prompt = (
        f"System: {desc}\nThreat horizon: {horizon} years\n"
        f"Algorithms detected: {', '.join(algorithms or _QUANTUM_VULNERABLE)}\n\n"
        f"Grep output:\n{grep_out}\n\n"
        f"Source corpus:\n{corpus[:3000]}\n\n"
        "Analyse quantum readiness."
    )

    data = _parse_json(_llm(prompt, system, "quantum_ready"), {
        "quantum_risk_map": [], "pqc_migration_plan": [], "harvest_now_risk_score": 50,
    })

    ts = _ts()
    report = (
        f"# Quantum Readiness Report — {ts}\n\n"
        f"**System:** {desc}\n"
        f"**Harvest-now risk:** {data.get('harvest_now_risk_score', 0)}/100\n"
        f"**Horizon:** {horizon} years\n\n"
        "## Risk Map\n"
        + "\n".join(
            f"- [{r.get('migration_priority','?').upper()}] "
            f"{r.get('algorithm','?')} @ {r.get('location','?')} — "
            f"{'🚨 HARVEST-NOW' if r.get('harvest_now_attack') else ''}"
            for r in data.get("quantum_risk_map", [])
        )
        + "\n\n## PQC Migration Plan\n"
        + "\n".join(
            f"{s.get('step','?')}. {s.get('current','?')} → {s.get('replacement','?')} "
            f"({s.get('nist_standard','')})"
            for s in data.get("pqc_migration_plan", [])
        )
        + "\n\n## Timeline\n"
        + data.get("timeline_analysis", "")
    )

    report_path = _save("reports", f"quantum_readiness_{ts}.md", report)
    _record("quantum_ready", desc, f"Risk: {data.get('harvest_now_risk_score',0)}/100")

    return {
        "quantum_risk_map":       data.get("quantum_risk_map", []),
        "quantum_speedup_opportunities": data.get("quantum_speedup_opportunities", []),
        "pqc_migration_plan":     data.get("pqc_migration_plan", []),
        "harvest_now_risk_score": data.get("harvest_now_risk_score", 0),
        "crypto_agility_recommendations": data.get("crypto_agility_recommendations", []),
        "report_path":            report_path,
        "summary": (
            f"Quantum readiness: {data.get('harvest_now_risk_score',0)}/100 harvest-now risk. "
            f"{len(data.get('quantum_risk_map',[]))} vulnerable algorithms. → {report_path}."
        ),
    }
