"""Golden-case gate: candidates only get promoted on a measured improvement."""
import json

import pytest

from src import eval_harness, prompt_store


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("TIMPS_EVAL_DIR", str(tmp_path / "evals"))
    monkeypatch.setenv("TIMPS_PROMPT_DIR", str(tmp_path / "prompts"))
    monkeypatch.setenv("TIMPS_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("GENERATED_DIR", str(tmp_path / "generated"))
    prompt_store.clear_cache()
    yield tmp_path
    prompt_store.clear_cache()


def _write_cases(n=3):
    data = {
        "agent": "demo_agent",
        "cases": [
            {
                "id": f"c{i}",
                "args": {"user_request": f"task {i}"},
                "expect_contains": ["good"],
                "expect_not_contains": ["traceback"],
                "min_chars": 4,
            }
            for i in range(n)
        ],
    }
    path = eval_harness.cases_path("demo_agent")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path


def _fake_fn(args):
    system = prompt_store.resolve("demo_agent", "BASE")
    return {"summary": "good output from candidate" if "IMPROVED" in system else "bad output"}


def test_init_cases_creates_editable_template():
    path = eval_harness.init_cases("demo_agent", count=2)
    assert json.loads(path.read_text())["agent"] == "demo_agent"
    assert len(eval_harness.load_cases("demo_agent")) == 2
    with pytest.raises(FileExistsError):
        eval_harness.init_cases("demo_agent")


def test_load_cases_falls_back_to_shared_smoke_cases(monkeypatch, tmp_path):
    shared = tmp_path / "evals" / "cases"
    shared.mkdir(parents=True)
    (shared / "_default.json").write_text(
        json.dumps({"cases": [{"id": "shared", "args": {"user_request": "x"}}]})
    )
    monkeypatch.setenv("TIMPS_EVAL_DIR", str(tmp_path / "evals"))
    cases = eval_harness.load_cases("agent_without_cases")
    assert len(cases) == 1
    assert cases[0]["id"] == "shared"


def test_output_scoring_distinguishes_pass_fail_and_inconclusive():
    case = {"expect_contains": ["good"], "expect_not_contains": ["bad"], "min_chars": 10}
    assert eval_harness._score_output("a good answer", case) == 1.0
    assert eval_harness._score_output("bad answer", case) == pytest.approx(1 / 3)
    assert eval_harness._score_output("[No LLM provider available] good", case) is None
    assert eval_harness._score_output("answer", {}) is None


def test_evaluate_measures_baseline_vs_candidate():
    _write_cases(3)
    candidate = prompt_store.propose("demo_agent", "IMPROVED SYSTEM")
    result = eval_harness.evaluate(
        "demo_agent", candidate_prompt=candidate.read_text(), fn=_fake_fn
    )

    assert result["baseline_mean"] == pytest.approx(2 / 3)
    assert result["candidate_mean"] == 1.0
    assert result["delta"] == pytest.approx(1 / 3)


def test_gate_refuses_without_enough_cases():
    _write_cases(1)
    candidate = prompt_store.propose("demo_agent", "IMPROVED SYSTEM")
    result = eval_harness.gate("demo_agent", candidate)
    assert result["status"] == "insufficient_cases"


def test_gate_promotes_only_when_requested_and_delta_passes(monkeypatch):
    _write_cases(3)
    monkeypatch.setattr(eval_harness, "_find_agent_fn", lambda agent: _fake_fn)
    candidate = prompt_store.propose("demo_agent", "IMPROVED SYSTEM")

    reviewed = eval_harness.gate("demo_agent", candidate)
    assert reviewed["passed"] is True
    assert reviewed["promoted"] is False
    assert prompt_store.resolve("demo_agent", "BASE") == "BASE"

    promoted = eval_harness.gate("demo_agent", candidate, promote=True)
    assert promoted["promoted"] is True
    assert prompt_store.resolve("demo_agent", "BASE") == "IMPROVED SYSTEM"


def test_temporary_prompt_restores_state_even_on_exception():
    existing = prompt_store.propose("demo_agent", "ORIGINAL OVERRIDE")
    prompt_store.promote("demo_agent", existing)

    with pytest.raises(RuntimeError):
        with prompt_store.with_prompt("demo_agent", "TEMPORARY"):
            assert prompt_store.resolve("demo_agent", "BASE") == "TEMPORARY"
            raise RuntimeError("boom")

    assert prompt_store.resolve("demo_agent", "BASE") == "ORIGINAL OVERRIDE"
