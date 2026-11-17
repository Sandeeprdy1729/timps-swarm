"""Prompt store: versioning, promotion, rollback and safety."""
import json

import pytest

from src import prompt_store


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("TIMPS_PROMPT_DIR", str(tmp_path / "prompts"))
    prompt_store.clear_cache()
    yield
    prompt_store.clear_cache()


def _candidate(agent, text, source="test"):
    return prompt_store.propose(agent, text, source=source, rationale="unit test")


def test_resolve_falls_back_without_override():
    assert prompt_store.resolve("ghost_agent", "BAKED_IN") == "BAKED_IN"


def test_propose_is_shadow_then_promote_changes_effective_prompt(tmp_path):
    path = _candidate("demo_agent", "IMPROVED SYSTEM PROMPT")
    assert prompt_store.resolve("demo_agent", "BAKED_IN") == "BAKED_IN"

    prompt_store.promote("demo_agent", path, score=8.5, note="passed eval")
    assert prompt_store.resolve("demo_agent", "BAKED_IN") == "IMPROVED SYSTEM PROMPT"
    meta = json.loads((tmp_path / "prompts/overrides/demo_agent.meta.json").read_text())
    assert meta["score"] == 8.5
    assert meta["promotions"] == 1


def test_rollback_restores_previous_prompt():
    first = _candidate("demo_agent", "VERSION ONE")
    second = _candidate("demo_agent", "VERSION TWO")
    prompt_store.promote("demo_agent", first)
    prompt_store.promote("demo_agent", second)
    assert prompt_store.resolve("demo_agent", "BAKED_IN") == "VERSION TWO"

    assert prompt_store.rollback("demo_agent") is True
    assert prompt_store.resolve("demo_agent", "BAKED_IN") == "VERSION ONE"


def test_rollback_without_history_removes_override():
    path = _candidate("demo_agent", "ONLY VERSION")
    prompt_store.promote("demo_agent", path)
    assert prompt_store.rollback("demo_agent") is True
    assert prompt_store.rollback("demo_agent") is False
    assert prompt_store.resolve("demo_agent", "BAKED_IN") == "BAKED_IN"


def test_disable_switches_back_without_deleting_history():
    path = _candidate("demo_agent", "IMPROVED")
    prompt_store.promote("demo_agent", path)
    prompt_store.set_enabled("demo_agent", False)
    assert prompt_store.resolve("demo_agent", "BAKED_IN") == "BAKED_IN"
    prompt_store.set_enabled("demo_agent", True)
    assert prompt_store.resolve("demo_agent", "BAKED_IN") == "IMPROVED"


def test_agent_name_is_validated_before_filesystem_access():
    with pytest.raises(ValueError):
        _candidate("../../etc/passwd", "evil")
    assert prompt_store.resolve("../../etc/passwd", "SAFE") == "SAFE"


def test_oversized_and_empty_prompts_rejected():
    with pytest.raises(ValueError):
        _candidate("demo_agent", "")
    with pytest.raises(ValueError):
        _candidate("demo_agent", "x" * 20_001)


def test_status_reports_candidates_and_override():
    status = prompt_store.status()
    assert status == {}
    _candidate("demo_agent", "X")
    assert prompt_store.status()["demo_agent"]["candidates"] == 1
    assert prompt_store.status()["demo_agent"]["active"] is False
