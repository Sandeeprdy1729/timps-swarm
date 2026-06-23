import glob
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv",
             "dist", "build", ".next", ".nuxt", "target", ".mypy_cache",
             "generated", ".timps", "adapters"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".min.js", ".min.css", ".map",
                 ".lock", ".log", ".svg", ".png", ".jpg", ".jpeg",
                 ".gif", ".ico", ".woff", ".woff2", ".ttf", ".eot"}

SCAN_PATTERNS = {
    "test": ["**/*.py", "**/*.js", "**/*.ts", "**/*.go"],
    "docstring": ["**/*.py"],
    "type hint": ["**/*.py"],
    "review": ["**/*.py", "**/*.js", "**/*.ts"],
    "handler": ["**/handlers/**", "**/routes/**", "**/controllers/**", "**/api/**/*.py"],
    "model": ["**/models/**", "**/schemas/**"],
    "service": ["**/services/**", "**/utils/**", "**/helpers/**"],
    "endpoint": ["**/routes/**", "**/controllers/**", "**/views/**"],
    "migration": ["**/migrations/**"],
    "config": ["**/*.cfg", "**/*.conf", "**/*.yaml", "**/*.yml", "**/*.json", "**/*.toml"],
    "schema": ["**/*.sql", "**/schemas/**/*.json", "**/models/**/*.py"],
}


class TaskDecomposer:
    def decompose(
        self,
        instruction: str,
        agent_type: str,
        working_dir: str,
        max_items: int = 50,
    ) -> list[dict]:
        scan_results = self._try_filesystem_scan(instruction, working_dir)
        if scan_results:
            return self._scan_results_to_tasks(scan_results, instruction, agent_type, max_items)
        return self._llm_decompose(instruction, agent_type, working_dir, max_items)

    def _try_filesystem_scan(self, instruction: str, working_dir: str) -> Optional[list[str]]:
        instruction_lower = instruction.lower()
        matched_files: set[str] = set()
        for keyword, patterns in SCAN_PATTERNS.items():
            if keyword in instruction_lower:
                for pattern in patterns:
                    full_pattern = os.path.join(working_dir, pattern)
                    for filepath in glob.glob(full_pattern, recursive=True):
                        if self._should_skip(filepath):
                            continue
                        matched_files.add(filepath)
        for word in instruction_lower.split():
            if "/" in word or "\\" in word:
                path = os.path.join(working_dir, word.strip("./"))
                if os.path.exists(path):
                    if os.path.isdir(path):
                        for f in glob.glob(os.path.join(path, "**/*"), recursive=True):
                            if os.path.isfile(f) and not self._should_skip(f):
                                matched_files.add(f)
                    else:
                        matched_files.add(path)
        return sorted(matched_files) if matched_files else None

    def _should_skip(self, filepath: str) -> bool:
        parts = Path(filepath).parts
        for part in parts:
            if part in SKIP_DIRS:
                return True
        return any(filepath.endswith(s) for s in SKIP_SUFFIXES)

    def _scan_results_to_tasks(
        self, files: list[str], instruction: str, agent_type: str, max_items: int
    ) -> list[dict]:
        tasks = []
        for i, filepath in enumerate(files[:max_items]):
            filename = os.path.basename(filepath)
            specific_desc = instruction.rstrip(".!?") + f" for {filename}"
            tasks.append({
                "id": i + 1,
                "description": specific_desc,
                "agent": agent_type,
                "target": filepath,
                "dependencies": [],
                "context": {"file_path": filepath, "file_name": filename},
            })
        return tasks

    def _llm_decompose(self, instruction: str, agent_type: str, working_dir: str, max_items: int) -> list[dict]:
        file_tree = self._get_compact_file_tree(working_dir)
        prompt = (
            f"You are a task decomposition engine. Break this instruction into concrete sub-tasks.\n\n"
            f"Instruction: {instruction}\n"
            f"Agent to use: {agent_type}\n"
            f"Project file tree:\n{file_tree[:4000]}\n\n"
            f"Rules:\n"
            f"- Create at most {max_items} sub-tasks\n"
            f"- Each task must be independently executable by the {agent_type} agent\n"
            f"- If tasks have dependencies, list them\n"
            f"- Be specific — include file paths when possible\n"
            f"- Return ONLY valid JSON, no explanation\n\n"
            f"Output format:\n"
            f'{{"tasks": [{{"id": 1, "description": "specific instruction for this sub-task", '
            f'"target": "path/to/file.py or null", "dependencies": []}}]}}'
        )
        try:
            from src._helpers import _llm
            response = _llm(prompt, temperature=0.1)
        except Exception as exc:
            logger.warning("LLM decomposition failed: %s", exc)
            return self._fallback_single(instruction, agent_type)
        try:
            parsed = json.loads(response)
            tasks = []
            for t in parsed.get("tasks", []):
                tasks.append({
                    "id": t["id"],
                    "description": t["description"],
                    "agent": agent_type,
                    "target": t.get("target"),
                    "dependencies": t.get("dependencies", []),
                    "context": {},
                })
            return tasks
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse LLM decomposition, falling back to single task")
            return self._fallback_single(instruction, agent_type)

    def _fallback_single(self, instruction: str, agent_type: str) -> list[dict]:
        return [{
            "id": 1,
            "description": instruction,
            "agent": agent_type,
            "target": None,
            "dependencies": [],
            "context": {},
        }]

    def _get_compact_file_tree(self, working_dir: str) -> str:
        try:
            result = subprocess.run(
                ["find", working_dir, "-maxdepth", "3", "-type", "f",
                 "-not", "-path", "*/node_modules/*",
                 "-not", "-path", "*/.git/*",
                 "-not", "-path", "*/__pycache__/*"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout[:4000]
        except Exception:
            return ""
