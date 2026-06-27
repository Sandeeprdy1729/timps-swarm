import pytest

from src.delegation_engine import DelegationEngine, ResultAggregator, ResultNormalizer


class TestWaveResolution:
    engine = DelegationEngine()

    def test_all_independent_single_wave(self):
        tasks = [
            {"id": 1, "dependencies": []},
            {"id": 2, "dependencies": []},
            {"id": 3, "dependencies": []},
        ]
        waves = self.engine._resolve_execution_waves(tasks, max_parallel=10)
        assert len(waves) == 1
        assert len(waves[0]) == 3

    def test_max_parallel_splits_wave(self):
        tasks = [{"id": i, "dependencies": []} for i in range(10)]
        waves = self.engine._resolve_execution_waves(tasks, max_parallel=3)
        assert len(waves) == 4
        assert len(waves[0]) == 3
        assert len(waves[1]) == 3
        assert len(waves[2]) == 3
        assert len(waves[3]) == 1

    def test_chain_dependencies_creates_sequential_waves(self):
        tasks = [
            {"id": 1, "dependencies": []},
            {"id": 2, "dependencies": [1]},
            {"id": 3, "dependencies": [2]},
        ]
        waves = self.engine._resolve_execution_waves(tasks, max_parallel=10)
        assert len(waves) == 3
        assert waves[0][0]["id"] == 1
        assert waves[1][0]["id"] == 2
        assert waves[2][0]["id"] == 3

    def test_diamond_dependency(self):
        tasks = [
            {"id": "A", "dependencies": []},
            {"id": "B", "dependencies": ["A"]},
            {"id": "C", "dependencies": ["A"]},
            {"id": "D", "dependencies": ["B", "C"]},
        ]
        waves = self.engine._resolve_execution_waves(tasks, max_parallel=10)
        assert len(waves) == 3
        assert waves[0][0]["id"] == "A"
        wave2_ids = {t["id"] for t in waves[1]}
        assert wave2_ids == {"B", "C"}
        assert waves[2][0]["id"] == "D"

    def test_deadlock_handling(self):
        tasks = [
            {"id": 1, "dependencies": [2]},
            {"id": 2, "dependencies": [1]},
        ]
        waves = self.engine._resolve_execution_waves(tasks, max_parallel=10)
        assert len(waves) >= 1


class TestAggregation:
    def test_all_succeeded(self):
        normalizer = ResultNormalizer()
        aggregator = ResultAggregator()

        results = [
            normalizer.normalize({"file_path": "test_auth.py", "tests": 12}, {"id": 1, "target": "auth.py"}),
            normalizer.normalize("Created test_users.py with 8 test cases", {"id": 2, "target": "users.py"}),
        ]

        aggregated = aggregator.aggregate(results)
        assert aggregated["status"] == "completed"
        assert aggregated["succeeded"] == 2
        assert aggregated["failed"] == 0
        assert len(aggregated["files_created"]) == 2

    def test_mixed_success_and_failure(self):
        normalizer = ResultNormalizer()
        aggregator = ResultAggregator()

        results = [
            normalizer.normalize({"file_path": "test_auth.py"}, {"id": 1, "target": "auth.py"}),
            normalizer.normalize({"status": "error", "error": "too complex"}, {"id": 2, "target": "payments.py"}),
            normalizer.normalize(None, {"id": 3, "target": "analytics.py"}),
        ]

        aggregated = aggregator.aggregate(results)
        assert aggregated["status"] == "partial"
        assert aggregated["succeeded"] == 1
        assert aggregated["failed"] == 2
        assert len(aggregated["failures"]) == 2
        assert aggregated["next_steps"] is not None
        assert len(aggregated["next_steps"]) == 2

    def test_all_failed(self):
        normalizer = ResultNormalizer()
        aggregator = ResultAggregator()

        results = [
            normalizer.normalize(None, {"id": 1, "target": "a.py"}),
            normalizer.normalize({"status": "error", "error": "fail"}, {"id": 2, "target": "b.py"}),
        ]

        aggregated = aggregator.aggregate(results)
        assert aggregated["status"] == "failed"
        assert aggregated["succeeded"] == 0
        assert aggregated["failed"] == 2

    def test_aggregate_counts_files_from_multiple_results(self):
        normalizer = ResultNormalizer()
        aggregator = ResultAggregator()

        results = [
            normalizer.normalize({"file_path": "test_a.py", "tests": 5}, {"id": 1, "target": "a.py"}),
            normalizer.normalize({"file_path": "test_b.py", "tests": 3}, {"id": 2, "target": "b.py"}),
        ]

        aggregated = aggregator.aggregate(results)
        assert len(aggregated["files_created"]) == 2
        assert aggregated["metrics"]["tests"] == 8

    @pytest.mark.asyncio
    async def test_dry_run(self, tmp_project):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "auth.py"), "w") as f:
                f.write("# code\n")

            engine = DelegationEngine()
            result = await engine.execute(
                instruction="add tests for all files",
                agent_type="unit_test_writer",
                working_dir=tmpdir,
                dry_run=True,
            )
            assert result["status"] == "plan"
            assert result["total_tasks"] >= 1
            assert "tasks" in result
            assert "estimated_parallel_waves" in result
