from datetime import datetime, timedelta

import pytest

from src.observer import TaskObserver


class TestPatternDetection:
    def test_single_call_no_pattern(self):
        observer = TaskObserver()
        observer.pattern_threshold = 3
        observer.record_call("timps_unit_test_writer", {"file": "auth.py"}, {"status": "ok"})
        patterns = observer.detect_repetitive_patterns()
        assert len(patterns) == 0

    def test_three_calls_triggers_pattern(self):
        observer = TaskObserver()
        observer.pattern_threshold = 3
        for i in range(3):
            observer.record_call(
                "timps_unit_test_writer",
                {"file": f"handler_{i}.py", "instruction": "add tests"},
                {"status": "ok"},
            )
        patterns = observer.detect_repetitive_patterns()
        assert len(patterns) >= 1

    def test_different_tools_no_pattern(self):
        observer = TaskObserver()
        observer.pattern_threshold = 3
        observer.record_call("timps_unit_test_writer", {"file": "auth.py"}, {"status": "ok"})
        observer.record_call("timps_docstring_generator", {"file": "users.py"}, {"status": "ok"})
        observer.record_call("timps_pr_reviewer", {"file": "orders.py"}, {"status": "ok"})
        patterns = observer.detect_repetitive_patterns()
        assert len(patterns) == 0

    def test_old_calls_expire_from_window(self):
        observer = TaskObserver(window_duration_minutes=1)
        observer.pattern_threshold = 3
        now = datetime.now()
        observer.call_buffer.append({
            "tool": "timps_unit_test_writer",
            "args_hash": "abc123",
            "timestamp": now - timedelta(hours=2),
            "result_status": "ok",
            "duration_ms": 100,
        })
        observer.call_buffer.append({
            "tool": "timps_unit_test_writer",
            "args_hash": "abc123",
            "timestamp": now,
            "result_status": "ok",
            "duration_ms": 100,
        })
        observer.call_buffer.append({
            "tool": "timps_unit_test_writer",
            "args_hash": "abc123",
            "timestamp": now,
            "result_status": "ok",
            "duration_ms": 100,
        })
        patterns = observer.detect_repetitive_patterns()
        assert len(patterns) == 0

    def test_buffer_max_size(self):
        observer = TaskObserver(window_size=5)
        for i in range(100):
            observer.record_call("timps_unit_test_writer", {"file": f"{i}.py"}, {"status": "ok"})
        assert len(observer.call_buffer) == 5

    def test_pattern_suggested_action_depends_on_count(self):
        observer = TaskObserver()
        observer.pattern_threshold = 3
        for i in range(5):
            observer.record_call(
                "timps_unit_test_writer",
                {"file": f"{i}.py", "instruction": "add tests"},
                {"status": "ok"},
            )
        patterns = observer.detect_repetitive_patterns()
        for p in patterns:
            if p["count"] >= 5:
                assert p["suggested_action"] == "spawn_sub_agents"
            else:
                assert p["suggested_action"] == "batch"

    def test_spawn_callbacks_are_invoked(self):
        callback_triggered = [False]

        def callback(pattern):
            callback_triggered[0] = True

        observer = TaskObserver(window_size=10)
        observer.pattern_threshold = 3
        observer.spawn_callbacks.append(callback)
        for i in range(3):
            observer.record_call("test_tool", {"x": "y"}, {"status": "ok"})
        assert callback_triggered[0] is True


class TestFingerprinting:
    def test_different_arg_keys_different_fingerprint(self):
        observer = TaskObserver()
        fp1 = observer._fingerprint_args({"file": "auth.py"})
        fp2 = observer._fingerprint_args({"directory": "src/"})
        assert fp1 != fp2

    def test_long_text_different_from_short_text(self):
        observer = TaskObserver()
        long_fp = observer._fingerprint_args({"content": "x" * 500})
        short_fp = observer._fingerprint_args({"content": "hello"})
        assert long_fp != short_fp
        assert isinstance(long_fp, str)
        assert len(long_fp) > 0

    def test_list_args_are_hashed(self):
        observer = TaskObserver()
        fp = observer._fingerprint_args({"files": ["a.py", "b.py", "c.py"]})
        assert isinstance(fp, str)
        assert len(fp) > 0
