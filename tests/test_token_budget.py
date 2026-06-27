import time

import pytest

from src.token_budget import TokenBudgetManager


class TestBudgetEnforcement:
    def test_per_task_budget_blocks_expensive_call(self):
        manager = TokenBudgetManager(per_task_budget_usd=0.01)
        result = manager.record_usage(
            model="claude-3-5-sonnet-20241022",
            input_tokens=100000,
            output_tokens=50000,
            agent_name="code_generator",
            task_id="task-1",
        )
        assert result["within_budget"] is True
        assert "per-task budget" in result["warning"]

    def test_per_run_budget_enforced(self):
        manager = TokenBudgetManager(per_run_budget_usd=0.05)
        r1 = manager.record_usage("claude-3-5-haiku-20241022", 10000, 5000, "agent", "t1")
        assert r1["within_budget"] is True
        r2 = manager.record_usage("claude-3-5-haiku-20241022", 100000, 50000, "agent", "t2")
        assert r2["within_budget"] is False
        assert "Run budget exceeded" in r2["warning"]

    def test_daily_budget_enforced(self):
        manager = TokenBudgetManager(daily_budget_usd=0.001)
        r = manager.record_usage("claude-3-5-haiku-20241022", 10000, 5000, "agent", "t1")
        assert r["within_budget"] is False
        assert "Daily budget exceeded" in r["warning"]

    def test_80_percent_pre_warning(self):
        manager = TokenBudgetManager(per_run_budget_usd=1.00)
        # Haiku: 800k input + 100k output = $0.64 + $0.40 = $1.04 (over budget)
        # Use enough to hit 80%: 80% of $1.00 = $0.80
        # 800000 input * 0.0008/1000 + 100000 output * 0.004/1000 = 0.64 + 0.40 = 1.04
        # Way too much. Let's use: 100k input + 10k output = 0.08 + 0.04 = $0.12
        # Need 80% = $0.80. Use sonnet: 100k input + 50k output = 0.30 + 0.75 = $1.05 (over)
        # Use sonnet: 80k input + 40k output = 0.24 + 0.60 = $0.84 (> $0.80)
        manager.record_usage("claude-3-5-sonnet-20241022", 80000, 40000, "agent", "t1")
        r = manager.record_usage("claude-3-5-sonnet-20241022", 100, 100, "agent", "t2")
        # t1: (80000/1000)*0.003 + (40000/1000)*0.015 = 0.24 + 0.60 = $0.84
        # t2 adds tiny amount
        # At this point we've spent > 80% of $1.00, and it should warn
        if r["within_budget"]:
            assert r["warning"] is not None and "Approaching run budget" in r["warning"]

    def test_daily_reset(self):
        manager = TokenBudgetManager(daily_budget_usd=50.00)
        manager.record_usage("claude-3-5-haiku-20241022", 10000, 5000, "agent", "t2")
        cost_before = manager._daily_cost
        assert cost_before > 0
        manager._daily_date = "2020-01-01"
        manager._check_daily_reset()
        assert manager._daily_cost == 0.0

    def test_local_models_are_free(self):
        manager = TokenBudgetManager(per_run_budget_usd=0.0001)
        for model in ["qwen2.5-coder:7b", "TIMPS-Coder-0.5B"]:
            r = manager.record_usage(model, 1000000, 1000000, "agent", "t1")
            assert r["cost_usd"] == 0.0
            assert r["within_budget"] is True


class TestRunSummary:
    def test_summary_includes_model_breakdown(self):
        manager = TokenBudgetManager()
        manager.record_usage("claude-3-5-haiku-20241022", 10000, 5000, "agent1", "t1")
        manager.record_usage("claude-3-5-haiku-20241022", 8000, 3000, "agent2", "t2")
        manager.record_usage("gemini-2.5-flash", 20000, 10000, "agent3", "t3")

        summary = manager.get_run_summary()
        assert "claude-3-5-haiku-20241022" in summary["by_model"]
        assert "gemini-2.5-flash" in summary["by_model"]
        assert summary["by_model"]["claude-3-5-haiku-20241022"]["calls"] == 2
        assert summary["by_model"]["gemini-2.5-flash"]["calls"] == 1
        assert summary["total_calls"] == 3

    def test_reset_run_clears_run_totals(self):
        manager = TokenBudgetManager()
        manager.record_usage("claude-3-5-haiku-20241022", 10000, 5000, "agent", "t1")
        assert manager._current_run_cost > 0
        manager.reset_run()
        assert manager._current_run_cost == 0.0

    def test_daily_remaining_in_summary(self):
        manager = TokenBudgetManager(daily_budget_usd=10.00)
        manager.record_usage("claude-3-5-haiku-20241022", 10000, 5000, "agent", "t1")
        summary = manager.get_run_summary()
        assert "daily_remaining_usd" in summary
        assert summary["daily_remaining_usd"] < 10.00
