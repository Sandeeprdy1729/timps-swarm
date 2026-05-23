"""
Memory Agent — high-level interface to the persistent TIMPS memory system.
Stores and retrieves context across sessions (JSONL backing store).

Actions: store | recall | stats | forget
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def memory_agent(args: Dict[str, Any]) -> Dict[str, Any]:
    from src.memory import recall_similar, record_run

    action  = args.get("action", "recall")
    content = args.get("content", "")
    query   = args.get("query", content)
    agent   = args.get("agent")
    limit   = int(args.get("limit", 5))

    # ── store ──────────────────────────────────────────────────────────────
    if action == "store":
        if not content:
            return {"error": "content is required for store", "stored": False}
        record_run(
            agent_name=agent or "memory_agent",
            request=query or content[:100],
            summary=content[:1000],
            success=True,
            metadata=args.get("metadata", {}),
        )
        return {
            "stored": True,
            "agent":  agent or "memory_agent",
            "preview": content[:200],
            "summary": f"Memory stored for '{agent or 'memory_agent'}'.",
        }

    # ── recall ─────────────────────────────────────────────────────────────
    elif action == "recall":
        if not query:
            return {"error": "query is required for recall", "results": []}
        results = recall_similar(query, agent=agent, limit=limit)
        formatted = [
            {"agent": r.get("agent"), "request": r.get("request"),
             "summary": r.get("summary", "")[:300], "ts": r.get("ts")}
            for r in results
        ]
        return {
            "results": formatted,
            "count":   len(formatted),
            "query":   query,
            "summary": f"Found {len(formatted)} memories for '{query}'.",
        }

    # ── stats ──────────────────────────────────────────────────────────────
    elif action == "stats":
        mem_dir   = Path(os.environ.get("TIMPS_MEMORY_DIR", str(Path.home() / ".timps" / "memory")))
        runs_file = mem_dir / "runs.jsonl"
        total, agents_seen = 0, set()
        if runs_file.exists():
            for line in runs_file.read_text().splitlines():
                try:
                    e = json.loads(line)
                    total += 1
                    agents_seen.add(e.get("agent", ""))
                except Exception:
                    pass
        return {
            "total_runs":    total,
            "unique_agents": len(agents_seen),
            "agents":        sorted(agents_seen),
            "memory_dir":    str(mem_dir),
            "summary":       f"{total} runs across {len(agents_seen)} agents.",
        }

    # ── forget ─────────────────────────────────────────────────────────────
    elif action == "forget":
        return {
            "forgotten": False,
            "note": "Selective forget not yet implemented. "
                    "Clear ~/.timps/memory/runs.jsonl manually.",
        }

    return {"error": f"Unknown action: {action}. Use store|recall|stats|forget."}
