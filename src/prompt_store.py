"""
Versioned, per-agent system-prompt overrides with shadow candidates and rollback.

Storage layout (defaults to ~/.timps/prompts, override with TIMPS_PROMPT_DIR)::

    overrides/<agent>.md            active prompt (what _llm() actually uses)
    overrides/<agent>.meta.json     provenance: when promoted, score, source
    candidates/<agent>/<ts>.md      proposed-but-unreviewed improvements
    history/<agent>/<ts>.md         previous active prompts, for rollback

Design rules:
  - resolve() is fail-open: any error falls back to the agent's code-defined prompt.
  - Nothing here promotes automatically. Promotion is an explicit, audited action.
  - Agent names are validated before touching the filesystem (no path traversal).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

_AGENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_MAX_PROMPT_CHARS = 20_000
_resolve_cache: dict[str, tuple[int, str]] = {}
_write_lock = threading.RLock()
logger = logging.getLogger(__name__)


def root() -> Path:
    """Prompt store root. Read on every call so env overrides work in tests."""
    return Path(os.getenv("TIMPS_PROMPT_DIR", str(Path.home() / ".timps" / "prompts")))


def _check_agent(agent: str) -> str:
    if not isinstance(agent, str) or not _AGENT_RE.fullmatch(agent):
        raise ValueError(f"invalid agent name: {agent!r}")
    return agent


def _override_path(agent: str) -> Path:
    return root() / "overrides" / f"{agent}.md"


def _meta_path(agent: str) -> Path:
    return root() / "overrides" / f"{agent}.meta.json"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read_meta(agent: str) -> dict[str, Any]:
    try:
        return json.loads(_meta_path(agent).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_meta(agent: str, meta: dict[str, Any]) -> None:
    _atomic_write(_meta_path(agent), json.dumps(meta, indent=2, sort_keys=True))


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ── Read path (called on every LLM invocation) ────────────────────────────────

def resolve(agent: str, default: str = "") -> str:
    """
    Return the active override for *agent*, or *default* if none is active.

    Never raises. A corrupt file, bad agent name or missing directory all mean
    "use the prompt baked into the agent", so a broken store cannot take down
    the swarm.
    """
    try:
        _check_agent(agent)
        if _read_meta(agent).get("enabled") is False:
            return default
        path = _override_path(agent)
        st = path.stat()
        cached = _resolve_cache.get(agent)
        if cached and cached[0] == st.st_mtime_ns:
            return cached[1] or default
        text = path.read_text(encoding="utf-8").strip()
        if len(text) > _MAX_PROMPT_CHARS:
            return default
        _resolve_cache[agent] = (st.st_mtime_ns, text)
        return text or default
    except Exception:
        return default


def clear_cache() -> None:
    """Drop memoised prompts (used by tests and external editors)."""
    _resolve_cache.clear()


# ── Write path (explicit, audited actions only) ───────────────────────────────

def propose(
    agent: str,
    prompt: str,
    source: str = "manual",
    rationale: str = "",
) -> Path:
    """Write a candidate prompt. It has no effect until promote() is called."""
    _check_agent(agent)
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if len(prompt) > _MAX_PROMPT_CHARS:
        raise ValueError(f"prompt exceeds {_MAX_PROMPT_CHARS} characters")

    folder = root() / "candidates" / agent
    folder.mkdir(parents=True, exist_ok=True)
    index = len(list(folder.glob("*.md")))
    path = folder / f"{_stamp()}_{index:02d}.md"
    _atomic_write(path, prompt.strip())
    _atomic_write(
        path.with_suffix(".meta.json"),
        json.dumps(
            {
                "agent": agent,
                "source": source,
                "rationale": rationale[:500],
                "proposed_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        ),
    )
    return path


def list_candidates(agent: str) -> list[Path]:
    _check_agent(agent)
    folder = root() / "candidates" / agent
    return sorted(folder.glob("*.md")) if folder.exists() else []


def promote(agent: str, candidate: str | Path, score: Optional[float] = None, note: str = "") -> Path:
    """
    Activate a candidate. The previous prompt (if any) is archived for rollback.

    This is deliberately manual: callers must have run an eval gate first.
    """
    _check_agent(agent)
    path = Path(candidate).resolve()
    allowed = (root() / "candidates" / agent).resolve()
    if path.parent != allowed or path.suffix != ".md":
        raise ValueError("candidate must be a .md file in this agent's candidates folder")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("candidate prompt is empty")

    active = _override_path(agent)
    if active.exists():
        history = root() / "history" / agent
        _atomic_write(history / f"{_stamp()}.md", active.read_text(encoding="utf-8"))

    _atomic_write(active, text)
    meta = _read_meta(agent)
    _write_meta(
        agent,
        {
            "enabled": True,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "source_candidate": str(path),
            "score": score,
            "note": note[:500],
            "promotions": int(meta.get("promotions", 0)) + 1,
        },
    )
    _resolve_cache.pop(agent, None)
    return active


def rollback(agent: str) -> bool:
    """
    Restore the previous prompt, or remove the override entirely if there is
    no history (falling back to the agent's code-defined prompt).

    Returns True if something was changed.
    """
    _check_agent(agent)
    history = root() / "history" / agent
    archived = sorted(history.glob("*.md")) if history.exists() else []
    active = _override_path(agent)

    if archived:
        previous = archived[-1]
        _atomic_write(active, previous.read_text(encoding="utf-8"))
        previous.unlink()
        _write_meta(
            agent,
            {
                "enabled": True,
                "promoted_at": datetime.now(timezone.utc).isoformat(),
                "note": "rollback",
                "rolled_back_from": str(previous),
            },
        )
        _resolve_cache.pop(agent, None)
        return True

    if active.exists():
        active.unlink()
        meta = _meta_path(agent)
        if meta.exists():
            meta.unlink()
        _resolve_cache.pop(agent, None)
        return True

    return False


def set_enabled(agent: str, enabled: bool) -> None:
    """Temporarily switch an agent back to its baked-in prompt without deleting history."""
    _check_agent(agent)
    meta = _read_meta(agent)
    meta["enabled"] = bool(enabled)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_meta(agent, meta)


@contextmanager
def with_prompt(agent: str, prompt: Optional[str] = None) -> Iterator[None]:
    """
    Run a block with one prompt active, then restore the exact prior state.

    ``prompt=None`` means the code-defined prompt (baseline). Used by the eval
    harness to compare baseline vs candidate without leaving state behind.
    Serialised with a re-entrant lock; safe to nest.
    """
    _check_agent(agent)
    if prompt is not None and len(prompt) > _MAX_PROMPT_CHARS:
        raise ValueError(f"prompt exceeds {_MAX_PROMPT_CHARS} characters")

    active = _override_path(agent)
    meta = _meta_path(agent)
    with _write_lock:
        prior_active = active.read_text(encoding="utf-8") if active.exists() else None
        prior_meta = meta.read_text(encoding="utf-8") if meta.exists() else None
        try:
            if prompt is None:
                if active.exists():
                    active.unlink()
                current = _read_meta(agent)
                current["enabled"] = False
                _write_meta(agent, current)
            else:
                _atomic_write(active, prompt.strip())
                current = _read_meta(agent)
                current["enabled"] = True
                current["note"] = "temporary eval prompt"
                _write_meta(agent, current)
            _resolve_cache.pop(agent, None)
            yield
        finally:
            try:
                if prior_active is None:
                    if active.exists():
                        active.unlink()
                else:
                    _atomic_write(active, prior_active)
                if prior_meta is None:
                    if meta.exists():
                        meta.unlink()
                else:
                    _atomic_write(meta, prior_meta)
                _resolve_cache.pop(agent, None)
            except OSError as exc:
                logger.warning("could not restore prompt state for %s: %s", agent, exc)


def status(agent: Optional[str] = None) -> dict[str, Any]:
    """Summarise overrides and pending candidates for one agent or all agents."""
    if agent:
        _check_agent(agent)
        agents = [agent]
    else:
        overrides = root() / "overrides"
        candidates = root() / "candidates"
        names = {p.stem for p in overrides.glob("*.md")} if overrides.exists() else set()
        names |= {p.name for p in candidates.iterdir() if p.is_dir()} if candidates.exists() else set()
        agents = sorted(names)

    result: dict[str, Any] = {}
    for name in agents:
        meta = _read_meta(name)
        result[name] = {
            "active": _override_path(name).exists(),
            "enabled": meta.get("enabled", True),
            "promoted_at": meta.get("promoted_at"),
            "score": meta.get("score"),
            "promotions": meta.get("promotions", 0),
            "candidates": len(list_candidates(name)),
        }
    return result


# ── CLI: python3 -m src.prompt_store ─────────────────────────────────────────

def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage per-agent prompt overrides")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="Show overrides and candidate counts")
    p_status.add_argument("agent", nargs="?")

    p_resolve = sub.add_parser("resolve", help="Print the effective system prompt for an agent")
    p_resolve.add_argument("agent")
    p_resolve.add_argument("--default", default="")

    p_propose = sub.add_parser("propose", help="Add a candidate prompt from a file or stdin")
    p_propose.add_argument("agent")
    p_propose.add_argument("file", nargs="?")
    p_propose.add_argument("--source", default="manual")
    p_propose.add_argument("--rationale", default="")

    p_promote = sub.add_parser("promote", help="Activate a reviewed candidate")
    p_promote.add_argument("agent")
    p_promote.add_argument("candidate")
    p_promote.add_argument("--score", type=float)
    p_promote.add_argument("--note", default="")

    for cmd in ("rollback", "enable", "disable"):
        sub.add_parser(cmd, help=f"{cmd} an agent's prompt override").add_argument("agent")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "status":
            print(json.dumps(status(args.agent), indent=2))
        elif args.cmd == "resolve":
            print(resolve(args.agent, args.default))
        elif args.cmd == "propose":
            text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
            print(propose(args.agent, text, args.source, args.rationale))
        elif args.cmd == "promote":
            print(promote(args.agent, args.candidate, args.score, args.note))
        elif args.cmd == "rollback":
            print("rolled back" if rollback(args.agent) else "nothing to roll back")
        elif args.cmd == "enable":
            set_enabled(args.agent, True)
            print("enabled")
        elif args.cmd == "disable":
            set_enabled(args.agent, False)
            print("disabled")
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
