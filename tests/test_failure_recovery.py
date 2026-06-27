import asyncio

import pytest

from src.failure_recovery import FailureRecovery


class TestErrorClassification:
    recovery = FailureRecovery()

    @pytest.mark.parametrize("error_string,expected", [
        ("request timed out after 30s", "timeout"),
        ("timeouterror: operation exceeded limit", "timeout"),
        ("rate limit exceeded, try again later", "rate_limit"),
        ("http 429 too many requests", "rate_limit"),
        ("authentication failed: invalid api key", "auth"),
        ("http 403 forbidden", "auth"),
        ("http 401 unauthorized", "auth"),
        ("context length exceeds model maximum", "context_length"),
        ("token limit: input too long", "context_length"),
        ("connectionerror: failed to connect", "connection"),
        ("networkerror: could not reach api", "connection"),
        ("expecting value: line 1 column 1 (char 0)", "json_parse"),
        ("jsondecodeerror: invalid json", "json_parse"),
        ("some unknown weird error", "unknown"),
    ])
    def test_classify_error(self, error_string, expected):
        assert self.recovery._classify_error(error_string) == expected


class TestPromptModification:
    recovery = FailureRecovery()

    def test_first_retry_removes_repo_context_on_timeout(self):
        args = {
            "task": "add tests for auth.py",
            "file_path": "auth.py",
            "_repo_context": {"framework": "django", "file_tree": "..."},
            "_parent_instruction": "add tests for all files",
        }
        modified = self.recovery._modify_args_for_retry(args, attempt=1, last_error="timeout")
        assert "_repo_context" not in modified
        assert "file_path" in modified
        assert "task" in modified

    def test_second_retry_adds_json_instruction(self):
        args = {"task": "generate schema", "file_path": "schema.py"}
        modified = self.recovery._modify_args_for_retry(args, attempt=2, last_error="json_parse")
        assert "valid JSON" in modified["task"]
        assert "_retry_attempt" in modified
        assert modified["_retry_attempt"] == 2

    def test_third_retry_is_minimal(self):
        args = {
            "task": "add tests for auth.py",
            "file_path": "auth.py",
            "_repo_context": {"framework": "django"},
            "_parent_instruction": "add tests for all files",
            "extra_stuff": "remove me",
        }
        modified = self.recovery._modify_args_for_retry(args, attempt=3, last_error="unknown")
        assert set(modified.keys()) == {"task", "file_path", "_retry_attempt", "_previous_error"}
        assert modified["_retry_attempt"] == 3

    def test_auth_error_is_not_retried(self):
        def fake_agent(args):
            raise Exception("HTTP 401 Unauthorized")

        recovery = FailureRecovery()
        result = asyncio.get_event_loop().run_until_complete(
            recovery.execute_with_recovery(
                agent_fn=fake_agent,
                args={"task": "test"},
                task={"id": 1, "target": "test.py"},
            )
        )
        assert result["status"] == "failed"
        assert result["attempts"] == 1

    def test_success_after_retry(self):
        call_count = [0]

        def fake_agent(args):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("timeout error")
            return "Added tests for auth.py with 10 test cases"

        recovery = FailureRecovery()

        async def run():
            return await recovery.execute_with_recovery(
                agent_fn=fake_agent,
                args={"task": "test"},
                task={"id": 1, "target": "test.py"},
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["status"] == "completed"
        assert result["attempts"] == 3
        assert result["recovered"] is True


class TestResultValidation:
    recovery = FailureRecovery()

    def test_none_is_invalid(self):
        assert self.recovery._is_valid_result(None) is False

    def test_empty_string_is_invalid(self):
        assert self.recovery._is_valid_result("   ") is False

    def test_short_string_is_invalid(self):
        assert self.recovery._is_valid_result("ok") is False

    def test_long_string_is_valid(self):
        assert self.recovery._is_valid_result("Created tests/test_auth.py with 12 test cases") is True

    def test_error_dict_is_invalid(self):
        assert self.recovery._is_valid_result({"status": "error", "error": "failed"}) is False

    def test_success_dict_is_valid(self):
        assert self.recovery._is_valid_result({"file_path": "tests/test_auth.py"}) is True

    def test_list_is_valid(self):
        assert self.recovery._is_valid_result(["file1.py", "file2.py"]) is True


class TestRecoveryStats:
    def test_stats_track_recovery_rate(self):
        recovery = FailureRecovery()
        assert recovery.get_recovery_stats()["total_retried"] == 0

        recovery.retry_log.append({"task_id": 1, "attempts": 2, "status": "recovered"})
        recovery.retry_log.append({"task_id": 2, "attempts": 3, "status": "failed"})
        stats = recovery.get_recovery_stats()
        assert stats["total_retried"] == 2
        assert stats["successfully_recovered"] == 1
        assert stats["ultimately_failed"] == 1
        assert stats["recovery_rate"] == "50%"
