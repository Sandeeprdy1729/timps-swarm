import os
import tempfile

import pytest

from src.decomposer import TaskDecomposer


class TestFilesystemScan:
    def test_finds_python_files_by_keyword_test(self, tmp_project):
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose(
            instruction="add tests for all files",
            agent_type="unit_test_writer",
            working_dir=tmp_project,
        )
        targets = {os.path.basename(t["target"]) for t in tasks}
        assert "auth.py" in targets
        assert "users.py" in targets
        assert "orders.py" in targets

    def test_skips_node_modules_and_git(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for excluded in ["node_modules", ".git", "__pycache__", ".venv"]:
                os.makedirs(os.path.join(tmpdir, excluded))
                with open(os.path.join(tmpdir, excluded, "should_skip.py"), "w") as f:
                    f.write("# should not appear\n")
            with open(os.path.join(tmpdir, "real.py"), "w") as f:
                f.write("# real code\n")

            decomposer = TaskDecomposer()
            tasks = decomposer.decompose(
                instruction="review all python files",
                agent_type="code_generator",
                working_dir=tmpdir,
            )
            assert len(tasks) == 1
            assert "real.py" in tasks[0]["target"]

    def test_handler_keyword_finds_handler_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src", "handlers"))
            os.makedirs(os.path.join(tmpdir, "src", "routes"))
            os.makedirs(os.path.join(tmpdir, "src", "utils"))

            for d in ["handlers", "routes", "utils"]:
                for name in ["auth.py", "users.py"]:
                    path = os.path.join(tmpdir, "src", d, name)
                    with open(path, "w") as f:
                        f.write("# code\n")

            decomposer = TaskDecomposer()
            # Use "handler" keyword without other matching keywords
            tasks = decomposer.decompose(
                instruction="fix all handler files",
                agent_type="unit_test_writer",
                working_dir=tmpdir,
            )
            # Filter to only real files (not directories)
            file_tasks = [t for t in tasks if t.get("target") and os.path.isfile(t["target"])]
            assert len(file_tasks) == 4
            dirs = {os.path.basename(os.path.dirname(t["target"])) for t in file_tasks}
            assert dirs == {"handlers", "routes"}

    def test_max_items_capped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(100):
                with open(os.path.join(tmpdir, f"file_{i}.py"), "w") as f:
                    f.write("# code\n")

            decomposer = TaskDecomposer()
            tasks = decomposer.decompose(
                instruction="review all files",
                agent_type="code_generator",
                working_dir=tmpdir,
                max_items=10,
            )
            assert len(tasks) == 10

    def test_empty_directory_returns_empty(self, mock_llm):
        mock_llm.return_value = '{"tasks": []}'
        with tempfile.TemporaryDirectory() as tmpdir:
            decomposer = TaskDecomposer()
            tasks = decomposer.decompose(
                instruction="review all files",
                agent_type="unit_test_writer",
                working_dir=tmpdir,
            )
            assert tasks == []

    def test_no_matching_keyword_triggers_llm_fallback(self, mock_llm):
        mock_llm.return_value = "invalid json {{{"
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "auth.py"), "w") as f:
                f.write("# code\n")

            decomposer = TaskDecomposer()
            tasks = decomposer.decompose(
                instruction="audit the authentication flow for security issues",
                agent_type="pr_reviewer",
                working_dir=tmpdir,
            )
            # Fallback to single task when no keywords match
            assert len(tasks) == 1
            assert tasks[0]["agent"] == "pr_reviewer"

    def test_skip_dirs_configurable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for d in ["dist", "build", ".next", "generated"]:
                os.makedirs(os.path.join(tmpdir, d))
                with open(os.path.join(tmpdir, d, "file.py"), "w") as f:
                    f.write("# code\n")
            with open(os.path.join(tmpdir, "valid.py"), "w") as f:
                f.write("# code\n")

            decomposer = TaskDecomposer()
            tasks = decomposer.decompose(
                instruction="review all files",
                agent_type="code_generator",
                working_dir=tmpdir,
            )
            assert len(tasks) == 1
            assert "valid.py" in tasks[0]["target"]


class TestTaskStructure:
    def test_each_task_has_required_fields(self, tmp_project):
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose(
            instruction="add tests for all files",
            agent_type="unit_test_writer",
            working_dir=tmp_project,
        )
        for task in tasks:
            assert "id" in task
            assert "description" in task
            assert "agent" in task
            assert "target" in task
            assert "dependencies" in task
            assert "context" in task
            assert isinstance(task["dependencies"], list)
            assert isinstance(task["context"], dict)

    def test_task_description_includes_filename(self, tmp_project):
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose(
            instruction="add tests for all files",
            agent_type="unit_test_writer",
            working_dir=tmp_project,
        )
        for task in tasks:
            assert os.path.basename(task["target"]) in task["description"]

    def test_tasks_have_no_dependencies_by_default(self, tmp_project):
        decomposer = TaskDecomposer()
        tasks = decomposer.decompose(
            instruction="add tests for all files",
            agent_type="unit_test_writer",
            working_dir=tmp_project,
        )
        for task in tasks:
            assert task["dependencies"] == []
