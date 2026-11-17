"""The self-improvement loop: telemetry, score persistence and prompt consumption."""
import json
from unittest.mock import patch

import pytest

from src import prompt_store
from src._helpers import _llm
from src.memory import record_run


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    import src.memory as memory

    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.setenv("TIMPS_MEMORY_DIR", str(mem))
    monkeypatch.setenv("TIMPS_PROMPT_DIR", str(tmp_path / "prompts"))
    monkeypatch.setattr(memory, "_MEMORY_DIR", mem)
    prompt_store.clear_cache()
    yield mem
    prompt_store.clear_cache()


def _rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_record_run_persists_quality_score(isolated):
    record_run("demo_agent", "do the thing", "done", score=8.5, latency_ms=12.3)
    rows = _rows(isolated / "runs.jsonl")
    assert rows[0]["score"] == 8.5
    assert rows[0]["latency_ms"] == 12.3
    assert "score" not in _rows(isolated / "runs.jsonl")[0]["metadata"]


def test_llm_uses_active_override_as_system_prompt(isolated):
    candidate = prompt_store.propose("demo_agent", "IMPROVED SYSTEM")
    prompt_store.promote("demo_agent", candidate)

    with patch("src.llm_router.LLMRouter.call", return_value="ok") as call:
        assert _llm("user prompt", "BAKED_IN", "demo_agent") == "ok"

    assert call.call_args.args[0] == "demo_agent"
    assert call.call_args.args[2] == "IMPROVED SYSTEM"


def test_llm_emits_telemetry_on_success_and_failure(isolated):
    with patch("src.llm_router.LLMRouter.call", return_value="answer"):
        _llm("p", "s", "telemetry_agent")
    with patch("src.llm_router.LLMRouter.call", side_effect=RuntimeError("boom")):
        _llm("p", "s", "telemetry_agent")

    rows = _rows(isolated / "llm_calls.jsonl")
    assert len(rows) == 2
    assert rows[0]["success"] is True and rows[0]["output_chars"] == 6
    assert rows[1]["success"] is False
    assert all(r["agent"] == "telemetry_agent" and r["latency_ms"] >= 0 for r in rows)


def test_learner_honours_min_score(isolated):
    from src.intelligence.learning_agent import learning_agent

    for score in (9, 3):
        record_run("demo_agent", f"run {score}", "done", score=score)
    payload = json.dumps(
        {"agent_improvements": [], "meta_patterns": [], "recommended_actions": []}
    )
    with patch("src.intelligence.learning_agent._llm", return_value=payload):
        result = learning_agent({"target_agent": "demo_agent", "min_score": 8})

    assert "Analysed 1 runs" in result["summary"]


def test_self_critic_persists_its_score(isolated, monkeypatch):
    from src.more_agents import self_critic_agent

    monkeypatch.setattr("src.more_agents._save", lambda sub, name, content: "/tmp/report.md")
    critique = json.dumps(
        {
            "score": 8,
            "verdict": "pass",
            "strengths": ["clear"],
            "weaknesses": ["minor gap"],
            "critical_issues": [],
            "improvement_prompt": "",
            "revised_output": "",
        }
    )
    with patch("src.more_agents._llm", return_value=critique):
        result = self_critic_agent(
            {"content": "good output", "agent": "demo_agent", "task": "write docs"}
        )

    assert result["score"] == 8
    rows = _rows(isolated / "runs.jsonl")
    assert len(rows) == 1
    assert rows[0]["agent"] == "demo_agent"
    assert rows[0]["score"] == 8.0
    assert rows[0]["metadata"]["source"] == "self_critic_agent"
