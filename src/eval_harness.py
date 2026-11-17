"""
Golden-case eval harness — the gate before a candidate prompt may be promoted.

Cases live in ~/.timps/evals/cases/<agent>.json (override with TIMPS_EVAL_DIR)::

    {
      "agent": "security_guard",
      "cases": [
        {
          "id": "open-port",
          "args": {"user_request": "check my laptop for open ports"},
          "expect_contains": ["port", "action"],
          "expect_not_contains": ["traceback"],
          "min_chars": 120
        }
      ]
    }

Checks are deterministic string assertions — no LLM judge, no extra spend beyond
running the agent itself. Outputs that look like provider/rate-limit errors are
treated as inconclusive and never counted as a pass.

Agents without their own case file use the shared ``evals/cases/_default.json``
smoke cases, so the gate exists for all agents from day one. Override it with a
per-agent file for meaningful quality assertions.

Usage::

    python3 -m src.eval_harness init <agent>
    python3 -m src.eval_harness run <agent> <candidate.md>
    python3 -m src.eval_harness gate <agent> <candidate.md> --promote --min-delta 0.1
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from src._helpers import _save, _ts
from src import prompt_store

_AGENT_SOURCES = [
    ("src.priority_agents", "PRIORITY_AGENTS"),
    ("src.more_agents", "MORE_AGENTS"),
    ("src.aiml_agents", "AIML_AGENTS"),
    ("src.intelligence_agents", "INTELLIGENCE_AGENTS"),
    ("src.knowledge_swarm_agents", "KNOWLEDGE_AGENTS"),
    ("src.developer_swarm_agents", "DEVELOPER_AGENTS"),
    ("src.infra", "INFRA_AGENTS"),
    ("src.aiml", "AIML_AGENTS"),
    ("src.intelligence", "INTELLIGENCE_AGENTS"),
    ("src.india", "INDIA_AGENTS"),
    ("src.domain", "DOMAIN_AGENTS"),
    ("src.business", "BUSINESS_AGENTS"),
    ("src.emerging", "EMERGING_AGENTS"),
    ("src.nextgen", "NEXTGEN_AGENTS"),
]


def eval_dir() -> Path:
    override = os.getenv("TIMPS_EVAL_DIR")
    if override:
        return Path(override)
    # Golden cases belong with the code so they can be reviewed and versioned.
    repo_cases = Path(__file__).resolve().parent.parent / "evals"
    return repo_cases if repo_cases.is_dir() else Path.home() / ".timps" / "evals"


def cases_path(agent: str) -> Path:
    prompt_store._check_agent(agent)
    return eval_dir() / "cases" / f"{agent}.json"


def default_cases_path() -> Path:
    return eval_dir() / "cases" / "_default.json"


def load_cases(agent: str) -> list[dict[str, Any]]:
    """Load agent-specific cases, falling back to the shared smoke cases."""
    for path in (cases_path(agent), default_cases_path()):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cases = [
                c for c in data.get("cases", [])
                if isinstance(c, dict) and c.get("args") is not None
            ]
            if cases:
                return cases
        except Exception:
            continue
    return []


def init_cases(agent: str, count: int = 3) -> Path:
    """Create an editable golden-case template. Never overwrites existing cases."""
    path = cases_path(agent)
    if path.exists():
        raise FileExistsError(f"cases already exist: {path}")
    template = {
        "agent": agent,
        "note": "Fill in expect_contains / expect_not_contains before running the gate.",
        "cases": [
            {
                "id": f"case-{i + 1}",
                "args": {"user_request": f"representative task {i + 1} for {agent}"},
                "expect_contains": ["CHANGE ME"],
                "expect_not_contains": ["traceback", "[No LLM provider available"],
                "min_chars": 100,
            }
            for i in range(max(1, count))
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    return path


def _find_agent_fn(agent: str) -> Optional[Callable]:
    for module_name, attr in _AGENT_SOURCES:
        try:
            registry = getattr(importlib.import_module(module_name), attr, None)
            if isinstance(registry, dict) and agent in registry:
                fn = registry[agent]
                if callable(fn):
                    return fn
        except Exception:
            continue
    return None


def _extract_output(result: Any) -> str:
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return str(result)
    for key in ("summary", "report", "output", "spec_yaml", "final_output", "content"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return json.dumps(result)[:2000]


def _score_output(output: str, case: dict[str, Any]) -> Optional[float]:
    """Deterministic per-case score in [0, 1]; None means inconclusive."""
    if not output or output.startswith(("[No LLM provider available", "[Rate limit")):
        return None
    checks: list[bool] = []
    text = output.lower()
    for frag in case.get("expect_contains", []) or []:
        checks.append(str(frag).lower() in text)
    for frag in case.get("expect_not_contains", []) or []:
        checks.append(str(frag).lower() not in text)
    try:
        min_chars = int(case.get("min_chars", 0))
    except (TypeError, ValueError):
        min_chars = 0
    if min_chars:
        checks.append(len(output) >= min_chars)
    if not checks:
        return None
    return sum(checks) / len(checks)


def evaluate(
    agent: str,
    candidate_prompt: Optional[str] = None,
    cases: Optional[list[dict[str, Any]]] = None,
    fn: Optional[Callable] = None,
) -> dict[str, Any]:
    """Score baseline and (optionally) a candidate prompt over the same golden cases."""
    cases = cases if cases is not None else load_cases(agent)
    if not cases:
        return {"status": "no_cases", "agent": agent}
    fn = fn or _find_agent_fn(agent)
    if fn is None:
        return {"status": "no_agent_fn", "agent": agent}

    def _run() -> list[Optional[float]]:
        scores: list[Optional[float]] = []
        for case in cases:
            try:
                result = fn(dict(case.get("args", {})))
                output = _extract_output(result)
            except Exception as exc:
                output = f"Error: {exc}"
            scores.append(_score_output(output, case))
        return scores

    with prompt_store.with_prompt(agent, None):
        baseline = _run()
    candidate: list[Optional[float]] = []
    if candidate_prompt is not None:
        with prompt_store.with_prompt(agent, candidate_prompt):
            candidate = _run()

    def _mean(values: list[Optional[float]]) -> Optional[float]:
        usable = [v for v in values if v is not None]
        return statistics.mean(usable) if usable else None

    base_mean, cand_mean = _mean(baseline), _mean(candidate)
    result: dict[str, Any] = {
        "status": "ok",
        "agent": agent,
        "n_cases": len(cases),
        "n_valid_baseline": sum(v is not None for v in baseline),
        "baseline_mean": base_mean,
        "baseline_scores": baseline,
    }
    if candidate_prompt is not None:
        result.update(
            {
                "n_valid_candidate": sum(v is not None for v in candidate),
                "candidate_mean": cand_mean,
                "candidate_scores": candidate,
                "delta": (cand_mean - base_mean)
                if cand_mean is not None and base_mean is not None
                else None,
            }
        )
    return result


def gate(
    agent: str,
    candidate_path: str | Path,
    min_delta: float = 0.1,
    min_cases: int = 3,
    promote: bool = False,
    note: str = "",
) -> dict[str, Any]:
    """Evaluate a candidate and promote it only on a positive, measured delta."""
    path = Path(candidate_path)
    candidate = path.read_text(encoding="utf-8").strip()
    cases = load_cases(agent)
    if len(cases) < min_cases:
        return {
            "status": "insufficient_cases",
            "agent": agent,
            "detail": f"need {min_cases} golden cases, found {len(cases)}",
        }

    result = evaluate(agent, candidate_prompt=candidate, cases=cases)
    if result.get("status") != "ok":
        return result

    enough = (
        result.get("n_valid_baseline", 0) >= min_cases
        and result.get("n_valid_candidate", 0) >= min_cases
    )
    delta = result.get("delta")
    passed = bool(enough and delta is not None and delta >= min_delta)
    result.update({"passed": passed, "min_delta": min_delta, "promoted": False})

    if passed and promote:
        prompt_store.promote(
            agent,
            path,
            score=result["candidate_mean"],
            note=(note or "eval gate passed") + f" (delta {delta:+.2f})",
        )
        result["promoted"] = True

    report = [
        f"# Eval Gate — {agent} — {_ts()}",
        "",
        f"Candidate: `{path}`",
        f"Baseline mean: **{result.get('baseline_mean')}** "
        f"({result.get('n_valid_baseline')}/{result['n_cases']} valid)",
        f"Candidate mean: **{result.get('candidate_mean')}** "
        f"({result.get('n_valid_candidate')}/{result['n_cases']} valid)",
        f"Delta: **{delta}** (required ≥ {min_delta})",
        f"Verdict: **{'PASS' if passed else 'FAIL'}** — "
        f"{'promoted' if result['promoted'] else 'not promoted'}",
        "",
    ]
    report_path = _save("reports", f"eval_{agent}_{_ts()}.md", "\n".join(report))
    result["report_path"] = report_path
    return result


def _main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Golden-case eval gate for prompt candidates")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create a golden-case template")
    p_init.add_argument("agent")
    p_init.add_argument("--count", type=int, default=3)

    p_run = sub.add_parser("run", help="score baseline and a candidate")
    p_run.add_argument("agent")
    p_run.add_argument("candidate", nargs="?")
    p_run.add_argument("--min-cases", type=int, default=3)

    p_gate = sub.add_parser("gate", help="evaluate and optionally promote")
    p_gate.add_argument("agent")
    p_gate.add_argument("candidate")
    p_gate.add_argument("--promote", action="store_true")
    p_gate.add_argument("--min-delta", type=float, default=0.1)
    p_gate.add_argument("--min-cases", type=int, default=3)
    p_gate.add_argument("--note", default="")

    args = p.parse_args(argv)
    try:
        if args.cmd == "init":
            print(init_cases(args.agent, args.count))
            return 0

        if args.cmd == "run":
            cases = load_cases(args.agent)
            if len(cases) < args.min_cases:
                print(f"need {args.min_cases} cases; found {len(cases)}", file=sys.stderr)
                return 1
            candidate = Path(args.candidate).read_text() if args.candidate else None
            print(json.dumps(evaluate(args.agent, candidate_prompt=candidate), indent=2))
            return 0

        result = gate(
            args.agent,
            args.candidate,
            min_delta=args.min_delta,
            min_cases=args.min_cases,
            promote=args.promote,
            note=args.note,
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("passed") else 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
