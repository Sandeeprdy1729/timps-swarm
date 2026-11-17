"""Sampled scoring turns agent outputs into the quality signal the learner needs."""
import json
from unittest.mock import patch

import pytest

from src import critic_sampler


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    import src.memory as memory

    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setenv("TIMPS_MEMORY_DIR", str(mem))
    monkeypatch.setenv("TIMPS_CRITIC_SAMPLE_RATE", "1.0")
    monkeypatch.setenv("TIMPS_CRITIC_MAX_PER_RUN", "3")
    monkeypatch.setattr(memory, "_MEMORY_DIR", mem)
    critic_sampler.reset_counter()
    yield mem
    critic_sampler.reset_counter()


def test_zero_rate_disables_sampling(monkeypatch):
    monkeypatch.setenv("TIMPS_CRITIC_SAMPLE_RATE", "0")
    assert critic_sampler.should_sample("demo_agent", "x" * 200) is False


def test_budget_caps_critiques_per_run():
    assert all(critic_sampler.should_sample("demo_agent", "x" * 200) for _ in range(3))
    assert critic_sampler.should_sample("demo_agent", "x" * 200) is False


def test_short_and_critic_outputs_ignored():
    assert critic_sampler.should_sample("demo_agent", "too short") is False
    assert critic_sampler.should_sample("self_critic_agent", "x" * 200) is False
    assert critic_sampler.should_sample("demo_agent", "[No LLM provider available] " + "x" * 200) is False


def test_maybe_score_persists_score(isolated, monkeypatch):
    monkeypatch.setattr("src.more_agents._save", lambda *a: "/tmp/report.md")
    critique = json.dumps(
        {"score": 6, "verdict": "fail", "strengths": [], "weaknesses": ["thin"],
         "critical_issues": [], "improvement_prompt": "", "revised_output": ""}
    )
    with patch("src.more_agents._llm", return_value=critique):
        score = critic_sampler.maybe_score("demo_agent", "write docs", "x" * 200)

    assert score == 6.0
    rows = [json.loads(line) for line in (isolated / "runs.jsonl").read_text().splitlines()]
    assert rows[0]["agent"] == "demo_agent"
    assert rows[0]["score"] == 6.0
    assert rows[0]["metadata"]["source"] == "self_critic_agent"


def test_node_wrapper_samples_only_completed_tasks():
    calls = []

    def fake_node(state):
        return {
            "tasks": [
                {"assigned_to": "demo_agent", "status": "completed", "output": "x" * 100,
                 "description": "done"},
                {"assigned_to": "other_agent", "status": "pending", "output": "y" * 100,
                 "description": "waiting"},
            ]
        }

    with patch("src.critic_sampler.maybe_score", side_effect=lambda *a: calls.append(a)):
        result = critic_sampler.with_critic_sampling(fake_node, "demo")({})

    assert len(result["tasks"]) == 2
    assert len(calls) == 1
    assert calls[0][0] == "demo_agent"
