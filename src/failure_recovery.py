import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

RETRY_STRATEGIES = ["simplify", "rephrase", "minimal"]

ERROR_STRATEGY = {
    "timeout": "simplify",
    "rate_limit": "backoff",
    "context_length": "simplify",
    "json_parse": "rephrase",
    "auth": "fail_fast",
    "connection": "backoff",
}


class FailureRecovery:
    MAX_RETRIES = 3

    def __init__(self):
        self.retry_log: list[dict] = []

    async def execute_with_recovery(
        self,
        agent_fn: Callable,
        args: dict,
        task: dict,
        progress_callback=None,
    ) -> dict:
        last_error = None
        last_output = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            modified_args = self._modify_args_for_retry(args, attempt, last_error)

            if progress_callback and attempt > 1:
                strategy = RETRY_STRATEGIES[attempt - 1]
                progress_callback(
                    None, None, None,
                    f"Retry {attempt}/{self.MAX_RETRIES} "
                    f"({strategy}) for {task.get('target', 'task')}",
                )

            try:
                result = await asyncio.to_thread(agent_fn, modified_args)
                if self._is_valid_result(result):
                    self.retry_log.append({
                        "task_id": task["id"],
                        "attempts": attempt,
                        "status": "recovered" if attempt > 1 else "success",
                    })
                    return {"status": "completed", "output": result, "attempts": attempt, "recovered": attempt > 1}
                else:
                    last_error = "Invalid result format"
                    last_output = result
            except asyncio.TimeoutError:
                last_error = "timeout"
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                error_str = str(e).lower()
                last_error = self._classify_error(error_str)
                last_output = str(e)
                if last_error == "auth":
                    break
                if last_error in ("rate_limit", "connection"):
                    await asyncio.sleep(2 ** attempt + 1)

        self.retry_log.append({
            "task_id": task["id"],
            "attempts": self.MAX_RETRIES,
            "status": "failed",
            "last_error": last_error,
        })
        return {"status": "failed", "error": last_error, "attempts": self.MAX_RETRIES, "last_output": last_output}

    def _modify_args_for_retry(self, args: dict, attempt: int, last_error: Optional[str]) -> dict:
        modified = dict(args)
        if attempt == 1 and last_error in ("timeout", "context_length"):
            modified.pop("_repo_context", None)
            modified.pop("_parent_instruction", None)
        elif attempt == 2 and last_error == "json_parse":
            modified["task"] = (
                modified.get("task", "")
                + "\n\nIMPORTANT: Return your response as valid JSON. "
                "Do not include any text outside the JSON object."
            )
        elif attempt >= 3:
            minimal = {"task": modified.get("task", "")}
            if "file_path" in modified:
                minimal["file_path"] = modified["file_path"]
            modified = minimal
        modified["_retry_attempt"] = attempt
        modified["_previous_error"] = last_error
        return modified

    def _classify_error(self, error_string: str) -> str:
        if "timeout" in error_string or "timed out" in error_string:
            return "timeout"
        if "rate limit" in error_string or "429" in error_string:
            return "rate_limit"
        if "auth" in error_string or "401" in error_string or "403" in error_string:
            return "auth"
        if "context_length" in error_string or "token" in error_string:
            return "context_length"
        if "connection" in error_string or "network" in error_string:
            return "connection"
        if "json" in error_string or "parse" in error_string:
            return "json_parse"
        return "unknown"

    def _is_valid_result(self, result) -> bool:
        if result is None:
            return False
        if isinstance(result, dict) and result.get("status") == "error":
            return False
        if isinstance(result, str) and len(result.strip()) < 10:
            return False
        return True

    def get_recovery_stats(self) -> dict:
        total = len(self.retry_log)
        if not total:
            return {"total_retried": 0, "successfully_recovered": 0, "ultimately_failed": 0, "recovery_rate": "N/A"}
        recovered = sum(1 for r in self.retry_log if r["status"] == "recovered")
        failed = sum(1 for r in self.retry_log if r["status"] == "failed")
        return {
            "total_retried": total,
            "successfully_recovered": recovered,
            "ultimately_failed": failed,
            "recovery_rate": f"{(recovered / total * 100):.0f}%" if total else "N/A",
        }
