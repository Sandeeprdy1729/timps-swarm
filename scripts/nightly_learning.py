#!/usr/bin/env python3
"""
Nightly learning job — turns accumulated run/LLM telemetry into prompt candidates.

Default mode is SHADOW: it reads telemetry, writes a report and (optionally)
proposes candidates into prompt_store. It never promotes a prompt. Promotion is
a manual, gated action because there is not yet an automated eval harness::

    python3 -m src.prompt_store status
    python3 -m src.prompt_store promote <agent> <candidate.md> --score 8.5
    python3 -m src.prompt_store rollback <agent>

Usage::

    python3 scripts/nightly_learning.py                       # report only
    python3 scripts/nightly_learning.py --apply-candidates    # + LLM proposals
    python3 scripts/nightly_learning.py --days 30 --max-agents 5
    python3 scripts/nightly_learning.py --apply-candidates --auto-promote
        # ^ only via the golden-case gate; candidates without cases are skipped
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src._helpers import _save, _ts  # noqa: E402
from src import prompt_store  # noqa: E402


def _memory_dir() -> Path:
    return Path(os.getenv("TIMPS_MEMORY_DIR", str(Path.home() / ".timps" / "memory")))


def _load_jsonl(path: Path, since: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            ts = datetime.fromisoformat(row.get("ts", ""))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, AttributeError):
            continue
        if ts >= since:
            rows.append(row)
    return rows


def collect(days: int) -> dict[str, dict[str, Any]]:
    """Aggregate per-agent call and score stats over the trailing window."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    mem = _memory_dir()
    runs = _load_jsonl(mem / "runs.jsonl", since)
    calls = _load_jsonl(mem / "llm_calls.jsonl", since)

    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n_calls": 0, "failures": 0, "latencies": [], "scores": [], "n_runs": 0}
    )
    for row in calls:
        s = stats[str(row.get("agent", "unknown"))]
        s["n_calls"] += 1
        s["failures"] += 0 if row.get("success") else 1
        try:
            s["latencies"].append(float(row.get("latency_ms", 0)))
        except (TypeError, ValueError):
            pass
    for row in runs:
        s = stats[str(row.get("agent", "unknown"))]
        s["n_runs"] += 1
        if row.get("score") is not None:
            try:
                s["scores"].append(float(row["score"]))
            except (TypeError, ValueError):
                pass
    return dict(stats)


def _line(agent: str, s: dict[str, Any]) -> str:
    fail = (s["failures"] / s["n_calls"] * 100) if s["n_calls"] else 0.0
    lat = statistics.mean(s["latencies"]) if s["latencies"] else 0.0
    score = statistics.mean(s["scores"]) if s["scores"] else None
    return (
        f"| {agent} | {s['n_calls']} | {fail:.0f}% | {lat:.0f}ms | "
        f"{s['n_runs']} | {len(s['scores'])} | {score:.2f} |" if score is not None else
        f"| {agent} | {s['n_calls']} | {fail:.0f}% | {lat:.0f}ms | "
        f"{s['n_runs']} | 0 | — |"
    )


def build_report(stats: dict[str, dict[str, Any]], days: int, eligible: list[str]) -> str:
    lines = [
        f"# Nightly Learning Report — {_ts()}",
        "",
        f"Window: trailing {days} days. Mode: **shadow** (no automatic promotion).",
        "",
        "| Agent | LLM calls | Fail rate | Mean latency | Runs | Scored | Mean score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for agent, s in sorted(stats.items(), key=lambda kv: -kv[1]["n_calls"]):
        lines.append(_line(agent, s))
    lines += [
        "",
        f"## Candidates eligible for learning ({len(eligible)})",
        "",
        "\n".join(f"- `{a}`" for a in eligible) if eligible else "- none — need scored runs first",
        "",
        "## Next step",
        "",
        "Score signal comes from sampled scoring in the swarm graph, `self_critic_agent`, "
        "or callers passing `score=` to `record_run`. Promote only after the golden-case "
        "gate: `python3 -m src.eval_harness gate <agent> <candidate.md> --promote`, or "
        "rerun this job with `--apply-candidates --auto-promote`.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Nightly learning (shadow mode by default)")
    p.add_argument("--days", type=int, default=7, help="trailing window in days (default: 7)")
    p.add_argument("--min-runs", type=int, default=3, help="min scored runs before learning (default: 3)")
    p.add_argument("--max-agents", type=int, default=10, help="max agents to propose for (default: 10)")
    p.add_argument("--targets", default="", help="comma-separated agent names to restrict to")
    p.add_argument("--apply-candidates", action="store_true", help="call the learner and save candidates")
    p.add_argument(
        "--auto-promote",
        action="store_true",
        help="run the golden-case gate and promote only candidates that pass it",
    )
    p.add_argument("--min-delta", type=float, default=0.1, help="minimum eval improvement (default: 0.1)")
    args = p.parse_args(argv)

    stats = collect(args.days)
    if not stats:
        print(f"No telemetry found in {_memory_dir()} for the last {args.days} days.")
        return 0

    targets = {t.strip() for t in args.targets.split(",") if t.strip()}
    eligible = [
        a for a, s in stats.items()
        if len(s["scores"]) >= args.min_runs and (not targets or a in targets)
    ]
    # Worst mean score first — the agents with the clearest quality problem.
    eligible.sort(key=lambda a: statistics.mean(stats[a]["scores"]))
    eligible = eligible[:args.max_agents]

    proposed: list[str] = []
    gate_results: list[str] = []
    if args.apply_candidates and eligible:
        from src.intelligence.learning_agent import learning_agent
        for agent in eligible:
            try:
                result = learning_agent(
                    {"target_agent": agent, "min_score": 8, "top_k": 10, "apply": False}
                )
            except Exception as exc:
                print(f"  learner failed for {agent}: {exc}", file=sys.stderr)
                continue
            for imp in result.get("improvements", []):
                fragment = imp.get("improved_system_prompt_fragment", "")
                name = imp.get("agent", agent)
                if fragment and name == agent:
                    path = prompt_store.propose(
                        agent,
                        fragment,
                        source="nightly_learning",
                        rationale=f"mean score {statistics.mean(stats[agent]['scores']):.2f}",
                    )
                    proposed.append(str(path))
                    if args.auto_promote:
                        from src.eval_harness import gate
                        try:
                            verdict = gate(
                                agent, path,
                                min_delta=args.min_delta,
                                promote=True,
                                note="nightly auto-promote via golden-case gate",
                            )
                            gate_results.append(
                                f"- `{agent}`: {verdict.get('status')} — "
                                f"passed={verdict.get('passed', False)}, "
                                f"promoted={verdict.get('promoted', False)}"
                            )
                        except Exception as exc:
                            gate_results.append(f"- `{agent}`: gate error: {exc}")

    report = build_report(stats, args.days, eligible)
    if proposed:
        report += "\n## Produced candidates\n\n" + "\n".join(f"- `{p}`" for p in proposed) + "\n"
    if gate_results:
        report += "\n## Gate results\n\n" + "\n".join(gate_results) + "\n"
    report_path = _save("reports", f"nightly_learning_{_ts()}.md", report)

    print(f"Agents seen: {len(stats)} | eligible: {len(eligible)} | candidates: {len(proposed)}")
    print(f"Report: {report_path}")
    if not eligible:
        print("No agent has enough scored runs yet. Run self_critic_agent on real outputs first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
