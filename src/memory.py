"""
TIMPS Agent Memory — persistent cross-session knowledge store.

Agents become smarter over time by:
  1. Recording every run (request, summary, success) to ~/.timps/memory/runs.jsonl
  2. Recalling past similar fixes before running (context injected into LLM prompt)
  3. Storing user preferences in ~/.timps/memory/preferences.json

Storage layout (all files in ~/.timps/memory/  or  $TIMPS_MEMORY_DIR):
  runs.jsonl          — append-only log of every agent run
  preferences.json    — user preferences key-value store

Usage (agents call these automatically — no manual wiring needed):
  from src.memory import record_run, recall_similar, get_preference, set_preference
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_MEMORY_DIR = Path(
    os.environ.get("TIMPS_MEMORY_DIR", str(Path.home() / ".timps" / "memory"))
)


def _ensure_dir() -> Path:
    _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return _MEMORY_DIR


# ─────────────────────────────────────────────────────────────────────────────
# Recording
# ─────────────────────────────────────────────────────────────────────────────

def record_run(
    agent_name: str,
    request: str,
    summary: str,
    success: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a completed agent run to runs.jsonl (fire-and-forget, never raises)."""
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "request": request[:300],
            "summary": summary[:1000],
            "success": success,
            "metadata": metadata or {},
        }
        with open(_ensure_dir() / "runs.jsonl", "a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # memory is best-effort — never crash an agent


# ─────────────────────────────────────────────────────────────────────────────
# Recall
# ─────────────────────────────────────────────────────────────────────────────

def recall_similar(
    query: str,
    agent: Optional[str] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Return up to `limit` past runs whose request overlaps with `query`.
    Sorted by overlap score descending, then by recency.
    Never raises.
    """
    try:
        runs_file = _ensure_dir() / "runs.jsonl"
        if not runs_file.exists():
            return []

        query_words = set(query.lower().split())
        candidates: list[tuple[int, Dict]] = []

        with open(runs_file) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if agent and entry.get("agent") != agent:
                    continue
                req_words = set(entry.get("request", "").lower().split())
                overlap = len(query_words & req_words)
                if overlap > 0:
                    candidates.append((overlap, entry))

        # sort by overlap desc, then ts desc (ISO strings sort lexicographically)
        candidates.sort(key=lambda x: (x[0], x[1].get("ts", "")), reverse=True)
        return [entry for _, entry in candidates[:limit]]
    except Exception:
        return []


def format_past_context(past_runs: List[Dict]) -> str:
    """Format past runs as a compact context block for LLM prompts."""
    if not past_runs:
        return ""
    lines = ["--- PAST SIMILAR FIXES (for context) ---"]
    for r in past_runs:
        ts = r.get("ts", "")[:10]
        status = "✅" if r.get("success") else "❌"
        req = r.get("request", "")[:80]
        summary = r.get("summary", "")[:200]
        lines.append(f"[{ts}] {status} {r.get('agent', '?')}: {req}\n  → {summary}")
    lines.append("--- END PAST FIXES ---\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Preferences
# ─────────────────────────────────────────────────────────────────────────────

def get_preference(key: str, default: Any = None) -> Any:
    """Get a stored user preference. Never raises."""
    try:
        prefs_file = _ensure_dir() / "preferences.json"
        if not prefs_file.exists():
            return default
        return json.loads(prefs_file.read_text()).get(key, default)
    except Exception:
        return default


def set_preference(key: str, value: Any) -> None:
    """Store a user preference. Never raises."""
    try:
        prefs_file = _ensure_dir() / "preferences.json"
        _ensure_dir()
        try:
            prefs = json.loads(prefs_file.read_text()) if prefs_file.exists() else {}
        except (json.JSONDecodeError, OSError):
            prefs = {}
        prefs[key] = value
        prefs_file.write_text(json.dumps(prefs, indent=2))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Summary (for CLI / timps memory)
# ─────────────────────────────────────────────────────────────────────────────

def get_memory_summary() -> str:
    """Return a human-readable summary of everything stored in memory."""
    runs_file = _ensure_dir() / "runs.jsonl"
    prefs_file = _ensure_dir() / "preferences.json"

    total_runs = 0
    successes = 0
    agent_counts: Dict[str, int] = {}
    last_run: Optional[Dict] = None

    if runs_file.exists():
        with open(runs_file) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    total_runs += 1
                    if e.get("success"):
                        successes += 1
                    a = e.get("agent", "?")
                    agent_counts[a] = agent_counts.get(a, 0) + 1
                    last_run = e
                except json.JSONDecodeError:
                    pass

    lines = [
        f"📦 Memory store: {_MEMORY_DIR}",
        f"📊 Total runs recorded: {total_runs}  ({successes} successful)",
    ]

    if agent_counts:
        top = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        lines.append("🤖 Most-used agents: " + ", ".join(f"{a}({n})" for a, n in top))

    if last_run:
        lines.append(
            f"🕐 Last run: [{last_run.get('ts', '')[:10]}] "
            f"{last_run.get('agent')} — {last_run.get('request', '')[:60]}"
        )

    prefs: Dict = {}
    if prefs_file.exists():
        try:
            prefs = json.loads(prefs_file.read_text())
        except Exception:
            pass
    if prefs:
        lines.append(f"⚙️  Preferences stored: {len(prefs)}")
        for k, v in list(prefs.items())[:5]:
            lines.append(f"   {k} = {v}")

    return "\n".join(lines)
