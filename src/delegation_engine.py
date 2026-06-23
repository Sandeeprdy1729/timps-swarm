import asyncio
import logging
import re
import time
from typing import Any, Callable, Optional

from src.decomposer import TaskDecomposer

logger = logging.getLogger(__name__)


class ResultNormalizer:
    def normalize(self, raw_output: Any, task: dict) -> dict:
        normalized = {
            "task_id": task["id"],
            "target": task.get("target", "unknown"),
            "status": "completed",
            "files_created": [],
            "metrics": {},
            "summary": "",
            "raw": raw_output,
        }
        if raw_output is None:
            normalized["status"] = "failed"
            normalized["summary"] = "Agent returned no output"
            return normalized
        try:
            if isinstance(raw_output, dict):
                self._normalize_dict(raw_output, normalized)
            elif isinstance(raw_output, str):
                self._normalize_string(raw_output, normalized)
            else:
                normalized["summary"] = str(raw_output)[:200]
        except Exception as e:
            normalized["status"] = "failed"
            normalized["summary"] = f"Failed to parse output: {e}"
        return normalized

    def _normalize_dict(self, output: dict, normalized: dict):
        if output.get("status") == "error" or "error" in output:
            normalized["status"] = "failed"
            normalized["summary"] = output.get("error", "Unknown error")[:200]
            return
        for key in ["file_path", "artifact_path", "output_file", "path", "file"]:
            if key in output and output[key]:
                normalized["files_created"].append(output[key])
        for metric_key in ["tests", "test_count", "coverage", "lines", "functions"]:
            if metric_key in output:
                normalized["metrics"][metric_key] = output[metric_key]
        parts = []
        if normalized["files_created"]:
            parts.append(f"Created {len(normalized['files_created'])} file(s)")
        for k, v in normalized["metrics"].items():
            parts.append(f"{k}: {v}")
        if output.get("summary"):
            parts.append(output["summary"])
        normalized["summary"] = "; ".join(parts) if parts else "Completed"

    def _normalize_string(self, output: str, normalized: dict):
        normalized["summary"] = output[:300]
        patterns = [
            r'(?:Created|Wrote|Generated|Saved|Output)[:\s]+(\S+\.\w+)',
            r'`([^`]+\.\w+)`',
            r'(\S+\.py)\b',
            r'(\S+\.js)\b',
            r'(\S+\.ts)\b',
        ]
        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, output):
                path = match.group(1)
                if path not in seen and not path.startswith("http"):
                    normalized["files_created"].append(path)
                    seen.add(path)
        test_match = re.search(r'(\d+)\s*test', output, re.IGNORECASE)
        if test_match:
            normalized["metrics"]["tests"] = int(test_match.group(1))
        coverage_match = re.search(r'(\d+)%\s*coverage', output, re.IGNORECASE)
        if coverage_match:
            normalized["metrics"]["coverage"] = f"{coverage_match.group(1)}%"


class ResultAggregator:
    def aggregate(self, normalized_results: list[dict]) -> dict:
        succeeded = [r for r in normalized_results if r["status"] == "completed"]
        failed = [r for r in normalized_results if r["status"] == "failed"]
        timed_out = [r for r in normalized_results if r["status"] == "timeout"]

        all_files = []
        for r in succeeded:
            for f in r["files_created"]:
                all_files.append(f)

        total_metrics = {}
        for r in succeeded:
            for k, v in r["metrics"].items():
                if isinstance(v, (int, float)):
                    total_metrics[k] = total_metrics.get(k, 0) + v

        next_steps = []
        for r in failed:
            next_steps.append(f"{r['target']}: {r['summary'][:100]}")

        if not failed and not timed_out:
            overall_status = "completed"
        elif succeeded:
            overall_status = "partial"
        else:
            overall_status = "failed"

        summary_parts = [f"Completed {len(succeeded)}/{len(normalized_results)} tasks"]
        if all_files:
            summary_parts.append(f"({len(all_files)} files created)")
        if total_metrics.get("tests"):
            summary_parts.append(f"({total_metrics['tests']} total test cases)")
        if failed:
            summary_parts.append(f". Failed: {', '.join(r['target'] for r in failed)}")

        return {
            "status": overall_status,
            "total": len(normalized_results),
            "succeeded": len(succeeded),
            "failed": len(failed),
            "timed_out": len(timed_out),
            "files_created": all_files,
            "metrics": total_metrics,
            "failures": [{"target": r["target"], "error": r["summary"]} for r in failed],
            "timeouts": [{"target": r["target"]} for r in timed_out],
            "summary": "".join(summary_parts),
            "next_steps": next_steps if next_steps else None,
            "per_target": {
                r["target"]: {"status": r["status"], "summary": r["summary"]}
                for r in normalized_results
            },
            "details": normalized_results,
        }


class DelegationEngine:
    def __init__(self):
        self.decomposer = TaskDecomposer()
        self.normalizer = ResultNormalizer()
        self.aggregator = ResultAggregator()
        self._context_sharer = None

    def _get_context_sharer(self):
        if self._context_sharer is None:
            try:
                from src.context_sharing import CodingAgentContext
                self._context_sharer = CodingAgentContext()
            except ImportError:
                self._context_sharer = None
        return self._context_sharer

    async def execute(
        self,
        instruction: str,
        agent_type: str,
        working_dir: str,
        max_parallel: int = 10,
        dry_run: bool = False,
        progress_callback=None,
    ) -> dict:
        start_time = time.time()

        if progress_callback:
            progress_callback(5, 100, "Capturing repository context...")
        repo_context = {}
        context_sharer = self._get_context_sharer()
        if context_sharer:
            try:
                repo_context = context_sharer.capture_repo_context(working_dir)
            except Exception as exc:
                logger.warning("Context capture failed: %s", exc)

        if progress_callback:
            progress_callback(15, 100, "Decomposing instruction into sub-tasks...")
        sub_tasks = self.decomposer.decompose(
            instruction, agent_type, working_dir, max_items=100,
        )

        if dry_run:
            return {
                "status": "plan",
                "total_tasks": len(sub_tasks),
                "tasks": sub_tasks,
                "estimated_parallel_waves": self._count_waves(sub_tasks, max_parallel),
            }

        if progress_callback:
            progress_callback(25, 100, f"Planning execution: {len(sub_tasks)} sub-tasks...")
        waves = self._resolve_execution_waves(sub_tasks, max_parallel)

        all_normalized = []
        for wave_num, wave in enumerate(waves):
            if progress_callback:
                progress = 25 + int((wave_num / max(len(waves), 1)) * 70)
                progress_callback(
                    progress, 100,
                    f"Executing wave {wave_num + 1}/{len(waves)} "
                    f"({len(wave)} tasks in parallel)...",
                )
            wave_results = await self._execute_wave(wave, repo_context, max_parallel, progress_callback)
            for r, task in zip(wave_results, wave):
                all_normalized.append(self.normalizer.normalize(r.get("output"), task))

        if progress_callback:
            progress_callback(98, 100, "Aggregating results...")

        aggregated = self.aggregator.aggregate(all_normalized)
        aggregated["wall_time_seconds"] = round(time.time() - start_time, 2)
        aggregated["waves_executed"] = len(waves)
        aggregated["total_tasks"] = len(sub_tasks)

        try:
            from src.token_budget import get_token_budget_manager
            aggregated["cost"] = get_token_budget_manager().get_run_summary()
        except Exception:
            pass

        if progress_callback:
            progress_callback(100, 100, "Complete!")
        return aggregated

    def _resolve_execution_waves(self, tasks: list[dict], max_parallel: int) -> list[list[dict]]:
        completed_ids: set[int] = set()
        waves: list[list[dict]] = []
        max_iterations = len(tasks) + 1
        iteration = 0

        while len(completed_ids) < len(tasks) and iteration < max_iterations:
            iteration += 1
            ready = []
            for task in tasks:
                if task["id"] in completed_ids:
                    continue
                deps = set(task.get("dependencies", []))
                if deps.issubset(completed_ids):
                    ready.append(task)
            if not ready:
                remaining = [t for t in tasks if t["id"] not in completed_ids]
                if remaining:
                    waves.append(remaining)
                break
            for i in range(0, len(ready), max_parallel):
                waves.append(ready[i:i + max_parallel])
            completed_ids.update(t["id"] for t in ready)
        return waves

    async def _execute_wave(
        self, wave: list[dict], repo_context: dict, max_parallel: int, progress_callback=None
    ) -> list[dict]:
        semaphore = asyncio.Semaphore(max_parallel)
        results = [None] * len(wave)

        async def run_one(index: int, task: dict):
            async with semaphore:
                start = time.time()
                target_name = task.get("target", "task-" + str(task["id"]))
                if progress_callback:
                    progress_callback(None, None, None, "Starting " + target_name + "...")
                failure_recovery = None
                try:
                    from src.failure_recovery import FailureRecovery
                    failure_recovery = FailureRecovery()
                except ImportError:
                    pass

                agent_fn = self._get_agent_function(task["agent"])
                if not agent_fn:
                    results[index] = {
                        "task_id": task["id"], "target": task.get("target"),
                        "status": "error", "error": "Unknown agent: " + task["agent"],
                        "output": None,
                    }
                    return results[index]

                args = {
                    "task": task["description"],
                    "file_path": task.get("target"),
                    "_repo_context": repo_context,
                    "_parent_instruction": task["description"],
                }

                try:
                    if failure_recovery:
                        recover_result = await failure_recovery.execute_with_recovery(
                            agent_fn, args, task, progress_callback,
                        )
                        elapsed = round(time.time() - start, 1)
                        if recover_result["status"] == "completed":
                            if progress_callback:
                                progress_callback(None, None, None, "Complete " + target_name + " (" + str(elapsed) + "s)")
                            results[index] = {
                                "task_id": task["id"], "target": task.get("target"),
                                "status": "completed", "elapsed_seconds": elapsed,
                                "output": recover_result["output"],
                            }
                        else:
                            if progress_callback:
                                progress_callback(None, None, None, "Failed " + target_name + " (" + str(elapsed) + "s)")
                            results[index] = {
                                "task_id": task["id"], "target": task.get("target"),
                                "status": "error", "elapsed_seconds": elapsed,
                                "error": recover_result.get("error", "Unknown"),
                                "output": None,
                            }
                    else:
                        result = await asyncio.to_thread(agent_fn, args)
                        elapsed = round(time.time() - start, 1)
                        if progress_callback:
                            progress_callback(None, None, None, "Complete " + target_name + " (" + str(elapsed) + "s)")
                        results[index] = {
                            "task_id": task["id"], "target": task.get("target"),
                            "status": "completed", "elapsed_seconds": elapsed,
                            "output": result,
                        }
                except asyncio.TimeoutError:
                    elapsed = round(time.time() - start, 1)
                    if progress_callback:
                        progress_callback(None, None, None, "Timeout " + target_name + " (" + str(elapsed) + "s)")
                    results[index] = {
                        "task_id": task["id"], "target": task.get("target"),
                        "status": "timeout", "elapsed_seconds": elapsed,
                        "output": None,
                    }
                except Exception as e:
                    elapsed = round(time.time() - start, 1)
                    if progress_callback:
                        progress_callback(None, None, None, "Error " + target_name + " (" + str(elapsed) + "s)")
                    results[index] = {
                        "task_id": task["id"], "target": task.get("target"),
                        "status": "error", "elapsed_seconds": elapsed,
                        "error": str(e), "output": None,
                    }

        await asyncio.gather(*[run_one(i, t) for i, t in enumerate(wave)])
        return results

    def _get_agent_function(self, agent_name: str) -> Optional[Callable]:
        try:
            from src.graph import _resolve_node_fn
            fn = _resolve_node_fn(agent_name)
            if fn:
                return fn
        except (ImportError, AttributeError):
            pass
        agent_map = {
            "unit_test_writer": None,
            "docstring_generator": None,
        }
        if agent_name in agent_map:
            try:
                from src.developer_swarm_agents import DEVELOPER_AGENTS
                return DEVELOPER_AGENTS.get(agent_name)
            except ImportError:
                pass
        try:
            from src.expert_agents import EXPERT_AGENT_MAP
            if agent_name in EXPERT_AGENT_MAP:
                return EXPERT_AGENT_MAP[agent_name]
        except ImportError:
            pass
        try:
            from src.knowledge_swarm_agents import KNOWLEDGE_AGENTS
            if agent_name in KNOWLEDGE_AGENTS:
                return KNOWLEDGE_AGENTS[agent_name]
        except ImportError:
            pass
        try:
            from src.priority_agents import PRIORITY_AGENTS
            if agent_name in PRIORITY_AGENTS:
                return PRIORITY_AGENTS[agent_name]
        except ImportError:
            pass
        try:
            from src.computer_agents import (
                system_optimizer_node, file_organizer_node, environment_doctor_node,
                security_guard_node, network_medic_node, battery_analyst_node,
                update_manager_node, log_interpreter_node, privacy_cleaner_node,
                media_librarian_node, backup_sentinel_node, context_switcher_node,
            )
            health_map = {
                "system_optimizer": system_optimizer_node,
                "file_organizer": file_organizer_node,
                "environment_doctor": environment_doctor_node,
                "security_guard": security_guard_node,
                "network_medic": network_medic_node,
                "battery_analyst": battery_analyst_node,
                "update_manager": update_manager_node,
                "log_interpreter": log_interpreter_node,
                "privacy_cleaner": privacy_cleaner_node,
                "media_librarian": media_librarian_node,
                "backup_sentinel": backup_sentinel_node,
                "context_switcher": context_switcher_node,
            }
            if agent_name in health_map:
                return health_map[agent_name]
        except ImportError:
            pass
        return None

    def _count_waves(self, tasks: list[dict], max_parallel: int) -> int:
        independent = sum(1 for t in tasks if not t.get("dependencies"))
        has_deps = any(t.get("dependencies") for t in tasks)
        return max(1, (independent + max_parallel - 1) // max_parallel) + (1 if has_deps else 0)
