from src.llm_router import (
    ENGINEERING_PRINCIPLES,
    _with_engineering_principles,
)


class TestSharedEngineeringPrinciples:
    def test_empty_system_prompt_gets_principles(self):
        result = _with_engineering_principles("")
        assert result == ENGINEERING_PRINCIPLES

    def test_existing_prompt_is_preserved(self):
        result = _with_engineering_principles("You are a SQL expert. Output ONLY valid JSON.")
        assert result.startswith("You are a SQL expert. Output ONLY valid JSON.")
        assert ENGINEERING_PRINCIPLES in result

    def test_principles_are_not_duplicated(self):
        once = _with_engineering_principles("You are an agent.")
        twice = _with_engineering_principles(once)
        assert once == twice
        assert twice.count("<engineering_principles>") == 1

    def test_all_seven_principles_are_present(self):
        expected = [
            "Fix the codebase before adding prose rules",
            "Ban nuanced/misused APIs",
            "Directory structure as context",
            "Runtime verification",
            "Property-based / fuzz testing",
            "Formal verification (TLA+, Lean)",
            'Full "software factory" + auto-merge',
        ]
        for principle in expected:
            assert principle in ENGINEERING_PRINCIPLES
