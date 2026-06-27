import multiprocessing
import multiprocessing.queues
import os
import platform
import signal
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class IsolatedResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    elapsed_seconds: float = 0.0
    timed_out: bool = False
    oom_killed: bool = False


DEFAULT_LIMITS = {
    "cpu_seconds": 120,
    "memory_mb": 512,
    "wall_clock_seconds": 180,
}


def _set_resource_limits(cpu_seconds: int, memory_mb: int):
    if platform.system() == "Linux":
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 5))
        memory_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    elif platform.system() == "Darwin":
        import resource
        try:
            memory_bytes = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except (ValueError, OSError):
            pass


def _isolated_agent_worker(
    agent_fn_module: str,
    agent_fn_name: str,
    args: dict,
    result_queue: multiprocessing.queues.Queue,
    cpu_seconds: int,
    memory_mb: int,
):
    _set_resource_limits(cpu_seconds, memory_mb)
    try:
        import importlib
        module = importlib.import_module(agent_fn_module)
        agent_fn = getattr(module, agent_fn_name)
        result = agent_fn(args)
        result_queue.put(IsolatedResult(success=True, output=result))
    except MemoryError:
        result_queue.put(IsolatedResult(success=False, error="Out of memory", oom_killed=True))
    except Exception as e:
        result_queue.put(IsolatedResult(success=False, error=str(e)))


class ProcessIsolation:
    def __init__(
        self,
        cpu_seconds: int = DEFAULT_LIMITS["cpu_seconds"],
        memory_mb: int = DEFAULT_LIMITS["memory_mb"],
        wall_clock_seconds: int = DEFAULT_LIMITS["wall_clock_seconds"],
    ):
        self.cpu_seconds = cpu_seconds
        self.memory_mb = memory_mb
        self.wall_clock_seconds = wall_clock_seconds

    def execute(
        self,
        agent_fn: Callable,
        args: dict,
        agent_name: str = "unknown",
    ) -> IsolatedResult:
        module_name = agent_fn.__module__
        func_name = agent_fn.__name__

        result_queue = multiprocessing.Queue(maxsize=1)
        process = multiprocessing.Process(
            target=_isolated_agent_worker,
            args=(module_name, func_name, args, result_queue,
                  self.cpu_seconds, self.memory_mb),
            name=f"timps-agent-{agent_name}",
            daemon=True,
        )

        start_time = time.time()
        process.start()
        process.join(timeout=self.wall_clock_seconds)
        elapsed = time.time() - start_time

        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            return IsolatedResult(
                success=False,
                error=f"Timed out after {self.wall_clock_seconds}s",
                timed_out=True,
                elapsed_seconds=elapsed,
            )

        if process.exitcode and process.exitcode < 0:
            signal_name = signal.Signals(-process.exitcode).name
            if -process.exitcode == signal.SIGKILL:
                return IsolatedResult(
                    success=False,
                    error=f"Killed by SIGKILL (likely OOM). {signal_name}",
                    oom_killed=True,
                    elapsed_seconds=elapsed,
                )
            else:
                return IsolatedResult(
                    success=False,
                    error=f"Killed by signal: {signal_name}",
                    elapsed_seconds=elapsed,
                )

        try:
            result = result_queue.get_nowait()
            result.elapsed_seconds = elapsed
            return result
        except Exception:
            return IsolatedResult(
                success=False,
                error=f"Process exited with code {process.exitcode} but no result",
                elapsed_seconds=elapsed,
            )

    async def execute_async(
        self,
        agent_fn: Callable,
        args: dict,
        agent_name: str = "unknown",
    ) -> IsolatedResult:
        import asyncio
        return await asyncio.to_thread(self.execute, agent_fn, args, agent_name)
