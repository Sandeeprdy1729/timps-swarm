import logging
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_PRICING = {
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gemini-2.5-flash": {"input": 0.000075, "output": 0.0003},
    "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
    "qwen2.5-coder:7b": {"input": 0.0, "output": 0.0},
    "qwen2.5:7b": {"input": 0.0, "output": 0.0},
    "qwen2.5:14b": {"input": 0.0, "output": 0.0},
    "qwen2.5:3b": {"input": 0.0, "output": 0.0},
    "TIMPS-Coder-0.5B": {"input": 0.0, "output": 0.0},
}
DEFAULT_PRICING = {"input": 0.005, "output": 0.015}


@dataclass
class TokenUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    agent_name: str
    timestamp: float = field(default_factory=time.time)
    task_id: Optional[str] = None


class TokenBudgetManager:
    def __init__(
        self,
        per_task_budget_usd: float = 0.50,
        per_run_budget_usd: float = 10.00,
        daily_budget_usd: float = 50.00,
    ):
        self.per_task_budget = per_task_budget_usd
        self.per_run_budget = per_run_budget_usd
        self.daily_budget = daily_budget_usd
        self._lock = Lock()
        self._current_run_cost = 0.0
        self._daily_cost = 0.0
        self._daily_date = time.strftime("%Y-%m-%d")
        self._usage_log: list[TokenUsage] = []
        self._max_log_size = 10000

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: str = "unknown",
        task_id: str = None,
    ) -> dict:
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        cost = (
            (input_tokens / 1000) * pricing["input"]
            + (output_tokens / 1000) * pricing["output"]
        )
        usage = TokenUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            agent_name=agent_name,
            task_id=task_id,
        )
        with self._lock:
            self._check_daily_reset()
            self._usage_log.append(usage)
            if len(self._usage_log) > self._max_log_size:
                self._usage_log = self._usage_log[-5000:]
            self._current_run_cost += cost
            self._daily_cost += cost

        result = {"cost_usd": round(cost, 6), "within_budget": True, "warning": None}
        if cost > self.per_task_budget:
            result["warning"] = (
                f"Single call cost ${cost:.4f} exceeds per-task budget "
                f"${self.per_task_budget:.2f}"
            )
        if self._current_run_cost > self.per_run_budget:
            result["within_budget"] = False
            result["warning"] = (
                f"Run budget exceeded: ${self._current_run_cost:.2f} "
                f"/ ${self.per_run_budget:.2f}. Halting."
            )
        if self._daily_cost > self.daily_budget:
            result["within_budget"] = False
            result["warning"] = (
                f"Daily budget exceeded: ${self._daily_cost:.2f} "
                f"/ ${self.daily_budget:.2f}. All runs halted until tomorrow."
            )
        if (self._current_run_cost > self.per_run_budget * 0.8
                and result["within_budget"]):
            result["warning"] = (
                f"Approaching run budget: ${self._current_run_cost:.2f} "
                f"/ ${self.per_run_budget:.2f} (80%)"
            )
        return result

    def _check_daily_reset(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._daily_date:
            self._daily_cost = 0.0
            self._daily_date = today

    def get_run_summary(self) -> dict:
        with self._lock:
            run_calls = [u for u in self._usage_log if u.task_id]
            by_model = {}
            for u in run_calls:
                if u.model not in by_model:
                    by_model[u.model] = {
                        "calls": 0, "input_tokens": 0,
                        "output_tokens": 0, "cost_usd": 0.0,
                    }
                by_model[u.model]["calls"] += 1
                by_model[u.model]["input_tokens"] += u.input_tokens
                by_model[u.model]["output_tokens"] += u.output_tokens
                by_model[u.model]["cost_usd"] += u.cost_usd
            return {
                "total_cost_usd": round(self._current_run_cost, 4),
                "total_calls": len(run_calls),
                "total_input_tokens": sum(u.input_tokens for u in run_calls),
                "total_output_tokens": sum(u.output_tokens for u in run_calls),
                "by_model": {
                    k: {**v, "cost_usd": round(v["cost_usd"], 4)}
                    for k, v in by_model.items()
                },
                "daily_cost_usd": round(self._daily_cost, 4),
                "daily_budget_usd": self.daily_budget,
                "daily_remaining_usd": round(
                    self.daily_budget - self._daily_cost, 4
                ),
            }

    def reset_run(self):
        with self._lock:
            self._current_run_cost = 0.0


_token_budget_manager: Optional[TokenBudgetManager] = None


def get_token_budget_manager() -> TokenBudgetManager:
    global _token_budget_manager
    if _token_budget_manager is None:
        _token_budget_manager = TokenBudgetManager()
    return _token_budget_manager
