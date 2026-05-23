"""
Secrets Management Agent — scans for hardcoded credentials, generates
Vault/AWS Secrets Manager migration code, and pre-commit hooks.

Input:  path (str), provider (str), language (str)
Output: findings, migration_code, pre_commit_config, report_path
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src._helpers import _ts, _llm, _run, _save, _parse_json, _record


_PATTERNS = [
    r"(api_key|apikey|secret|password|passwd|token|credential|private_key)\s*[=:]\s*['\"][^'\"]{8,}",
    r"(aws_access_key_id|aws_secret_access_key)\s*[=:]",
    r"(AKIA[0-9A-Z]{16})",
    r"(ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36})",
]


def secrets_management(args: Dict[str, Any]) -> Dict[str, Any]:
    path_str  = args.get("path", ".")
    provider  = args.get("provider", "aws_secrets_manager")
    language  = args.get("language", "python")

    # Run trufflehog / gitleaks / grep
    trufflehog = _run(
        f"trufflehog filesystem {path_str} --json 2>/dev/null | head -20 || "
        f"gitleaks detect --source {path_str} --no-git -f json 2>/dev/null | head -20 || "
        f"grep -r --include='*.py' --include='*.env' --include='*.js' -l "
        f"'password\\|api_key\\|secret' {path_str} 2>/dev/null | head -10 || echo 'no_scanner'"
    )[:2000]

    # Read .env files if present
    env_files_found = list(Path(path_str).rglob(".env"))[:3]
    env_sample = ""
    for ef in env_files_found:
        try:
            lines = ef.read_text(encoding="utf-8", errors="ignore").splitlines()
            redacted = [
                (l if "=" not in l else l.split("=")[0] + "=***REDACTED***")
                for l in lines[:10]
            ]
            env_sample += f"\n{ef}:\n" + "\n".join(redacted)
        except Exception:
            pass

    system = (
        "You are a secrets security expert. Return JSON: "
        "{findings:[{file,line,pattern,severity:'critical'|'high'|'medium',"
        "secret_type,redacted_value,fix}], "
        "migration_code:str (Python — using provider SDK), "
        "pre_commit_config_yaml:str, "
        "env_vault_mapping:[{env_var,vault_path}], "
        "gitignore_additions:[str], "
        "remediation_steps:[str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Provider: {provider}\nLanguage: {language}\n\n"
        f"Scanner output:\n{trufflehog}\n\n"
        f"Env files (redacted):\n{env_sample or 'none found'}\n\n"
        "Audit and migrate secrets."
    )

    data = _parse_json(_llm(prompt, system, "secrets_management"), {
        "findings": [], "migration_code": "", "pre_commit_config_yaml": "",
    })

    ts = _ts()
    report_path    = _save("reports", f"secrets_audit_{ts}.md",
                            "# Secrets Audit\n\n"
                            + "\n".join(
                                f"- [{f.get('severity','?').upper()}] `{f.get('file','?')}` — "
                                f"{f.get('secret_type','?')}: {f.get('fix','')}"
                                for f in data.get("findings", [])
                            ))
    migration_path = _save("code", f"secrets_migration_{provider}_{ts}.py",
                             data.get("migration_code", ""))
    precommit_path = _save("code", f"pre_commit_secrets_{ts}.yaml",
                             data.get("pre_commit_config_yaml", ""))

    critical = [f for f in data.get("findings", []) if f.get("severity") == "critical"]
    _record("secrets_management", path_str, f"{len(data.get('findings',[]))} secrets found")

    return {
        "findings":            data.get("findings", []),
        "critical_count":      len(critical),
        "env_vault_mapping":   data.get("env_vault_mapping", []),
        "gitignore_additions": data.get("gitignore_additions", []),
        "remediation_steps":   data.get("remediation_steps", []),
        "report_path":         report_path,
        "migration_path":      migration_path,
        "precommit_path":      precommit_path,
        "summary": (
            f"Secrets audit: {len(data.get('findings',[]))} found "
            f"({len(critical)} critical). → {report_path}."
        ),
    }
