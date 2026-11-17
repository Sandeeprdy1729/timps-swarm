"""
Sampled quality scoring for agent outputs.

Every scored run is the missing input to the nightly learner. Scoring every task
would double LLM spend, so only a small sample is critiqued, with a hard per-run
budget. Defaults: 10% of outputs, at most 3 critiques per process.

Environment:
  TIMPS_CRITIC_SAMPLE_RATE   0.0–1.0, default 0.1  (0 disables entirely)
  TIMPS_CRITIC_MAX_PER_RUN   default 3

All functions fail open: a scoring error never changes or blocks agent output.
"""
from __future__ import annotations

import logging
import os
import random
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_calls_this_process = 0


def _rate() -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv("TIMPS_CRITIC_SAMPLE_RATE", "0.1"))))
    except (TypeError, ValueError):
        return 0.0


def _max_per_run() -> int:
    try:
        return max(0, int(os.getenv("TIMPS_CRITIC_MAX_PER_RUN", "3")))
    except (TypeError, ValueError):
        return 0


def reset_counter() -> None:
    """Reset the per-run budget (used by tests and long-lived servers)."""
    global _calls_this_process
    with _lock:
        _calls_this_process = 0


def _take_budget() -> bool:
    global _calls_this_process
    with _lock:
        if _calls_this_process >= _max_per_run():
            return False
        _calls_this_process += 1
        return True


def should_sample(agent: str, output: str) -> bool:
    """Whether this output should be critiqued on this run."""
    if _rate() <= 0.0 or not output or len(output) < 80:
        return False
    if agent in {"self_critic_agent", "unknown", "default"}:
        return False
    if output.startswith("[No LLM provider available"):
        return False
    if random.random() >= _rate():
        return False
    return _take_budget()


def maybe_score(
    agent: str,
    task: str,
    output: str,
    threshold: int = 7,
) -> Optional[float]:
    """
    Critique one output and persist its score. Returns the score or None.

    No re-runs: this is measurement, not repair. Re-running agents mid-swarm
    would change the very output being evaluated.
    """
    if not should_sample(agent, output):
        return None
    try:
        from src.more_agents import self_critic_agent
        result = self_critic_agent(
            {
                "content": output[:5000],
                "agent": agent,
                "task": (task or f"output from {agent}")[:300],
                "threshold": threshold,
                "max_retries": 0,
            }
        )
        score = result.get("score")
        return float(score) if score is not None else None
    except Exception as exc:
        logger.warning("Critic sampler failed for %s: %s", agent, exc)
        return None


def with_critic_sampling(node_fn: Callable, name: str = "node") -> Callable:
    """Wrap a LangGraph node so completed task outputs are sampled for scoring."""
    def _wrapped(state: Any) -> Any:
        result = node_fn(state)
        try:
            if isinstance(result, dict):
                for task in result.get("tasks", []) or []:
                    if not isinstance(task, dict) or task.get("status") != "completed":
                        continue
                    maybe_score(
                        str(task.get("assigned_to", "unknown")),
                        str(task.get("description", "")),
                        str(task.get("output", "") or ""),
                    )
        except Exception as exc:
            logger.debug("Critic sampling skipped for %s: %s", name, exc)
        return result
    _wrapped.__name__ = f"{name}_scored"
    return _wrapped
