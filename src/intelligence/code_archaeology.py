"""
Code Archaeology — maps legacy codebases into navigable knowledge artefacts.

Input:  path (str), language (str), max_files (int)
Output: architecture_md, dependency_summary, risk_map, tribal_knowledge,
        onboarding_steps, arch_path, risk_path, tribal_path
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, List

from src._helpers import _ts, _llm, _save, _parse_json, _record


def code_archaeology(args: Dict[str, Any]) -> Dict[str, Any]:
    repo_path = Path(args.get("path", "."))
    language  = args.get("language", "python")
    max_files = int(args.get("max_files", 50))

    ext_map = {
        "python": ["*.py"], "javascript": ["*.js", "*.mjs"],
        "typescript": ["*.ts", "*.tsx"], "java": ["*.java"],
        "go": ["*.go"], "rust": ["*.rs"], "cpp": ["*.cpp", "*.h"],
    }
    exts  = ext_map.get(language, ["*.py"])
    files: List[Path] = []
    for ext in exts:
        files.extend(list(repo_path.rglob(ext))[:max_files])
    files = files[:max_files]

    corpus_parts: List[str] = []
    for f in files:
        try:
            snippet = f.read_text(encoding="utf-8", errors="ignore")[:800]
            corpus_parts.append(f"### {f.relative_to(repo_path)}\n{snippet}")
        except Exception:
            pass
    corpus = "\n\n".join(corpus_parts[:40])

    # Python call-graph via AST
    call_graph_text = ""
    if language == "python":
        imports: Dict[str, List[str]] = {}
        for f in files:
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
                imported = [
                    (n.asname or n.name)
                    for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for n in node.names
                ] + [
                    node.module or ""
                    for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                ]
                imports[str(f.relative_to(repo_path))] = [i for i in imported if i]
            except Exception:
                pass
        call_graph_text = json.dumps(imports, indent=2)[:3000]

    system = (
        "You are a code archaeologist. Given partial source code produce: "
        "1) ARCHITECTURE.md — module responsibilities, tech stack, key abstractions. "
        "2) dependency_summary — which modules depend on what. "
        "3) risk_map — files most dangerous to change (high coupling / no tests). "
        "4) tribal_knowledge — implicit contracts, magic constants, undocumented side-effects. "
        "5) onboarding_steps — 'how to make your first meaningful change'. "
        "Return JSON: {architecture_md, dependency_summary, "
        "risk_map: [{file, risk_level, reason}], tribal_knowledge: [str], "
        "onboarding_steps: [str]}. Output ONLY valid JSON."
    )
    prompt = (
        f"Language: {language}  Files: {len(files)}\n\n"
        f"Import graph:\n{call_graph_text}\n\n"
        f"Source corpus (first 800 chars/file):\n{corpus[:8000]}"
    )

    data = _parse_json(_llm(prompt, system, "code_archaeology"), {
        "architecture_md": "", "dependency_summary": call_graph_text,
        "risk_map": [], "tribal_knowledge": [], "onboarding_steps": [],
    })

    arch_path   = _save("reports", f"ARCHITECTURE_{_ts()}.md",         data.get("architecture_md", ""))
    risk_path   = _save("reports", f"risk_map_{_ts()}.json",           json.dumps(data.get("risk_map", []), indent=2))
    tribal_path = _save("reports", f"tribal_knowledge_{_ts()}.md",     "\n".join(f"- {t}" for t in data.get("tribal_knowledge", [])))

    _record("code_archaeology", str(repo_path), data.get("architecture_md", "")[:400])
    return {
        "files_analysed":    len(files),
        "architecture_md":   data.get("architecture_md", ""),
        "dependency_summary":data.get("dependency_summary", ""),
        "risk_map":          data.get("risk_map", []),
        "tribal_knowledge":  data.get("tribal_knowledge", []),
        "onboarding_steps":  data.get("onboarding_steps", []),
        "arch_path":         arch_path,
        "risk_path":         risk_path,
        "tribal_path":       tribal_path,
        "summary": (
            f"Mapped {len(files)} files. "
            f"{len(data.get('risk_map', []))} risk zones. "
            f"ARCHITECTURE.md → {arch_path}."
        ),
    }
