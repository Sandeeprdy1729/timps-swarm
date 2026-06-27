import asyncio
import logging
import signal
import sys
from typing import Callable, Optional

logger = logging.getLogger("timps.shutdown")


class GracefulShutdown:
    def __init__(self, drain_timeout_seconds: int = 30):
        self.drain_timeout = drain_timeout_seconds
        self._shutting_down = False
        self._in_flight: dict[str, asyncio.Task] = {}
        self._child_processes: list = []
        self._callbacks: list[Callable] = []

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        if self._shutting_down:
            logger.warning("Second interrupt received, forcing exit")
            sys.exit(1)

        self._shutting_down = True
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, initiating graceful shutdown...", sig_name)

        try:
            loop = asyncio.get_event_loop()
            asyncio.ensure_future(self._shutdown())
        except RuntimeError:
            self._sync_shutdown()

    def register_in_flight(self, task_id: str, task: asyncio.Task):
        self._in_flight[task_id] = task

    def unregister_in_flight(self, task_id: str):
        self._in_flight.pop(task_id, None)

    def register_child_process(self, process):
        self._child_processes.append(process)

    def on_shutdown(self, callback: Callable):
        self._callbacks.append(callback)

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    async def _shutdown(self):
        logger.info("Step 1/5: Stopping new requests...")

        logger.info(
            "Step 2/5: Draining %d in-flight tasks (timeout: %ds)...",
            len(self._in_flight), self.drain_timeout,
        )
        if self._in_flight:
            try:
                done, pending = await asyncio.wait(
                    list(self._in_flight.values()),
                    timeout=self.drain_timeout,
                )
                for task in pending:
                    task.cancel()
                    logger.warning("Canceled task after drain timeout")
            except Exception as e:
                logger.error("Error during drain: %s", e)

        logger.info("Step 3/5: Running shutdown callbacks...")
        for callback in self._callbacks:
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Shutdown callback error: %s", e)

        logger.info("Step 4/5: Cleaning up %d child processes...", len(self._child_processes))
        for process in self._child_processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()

        logger.info("Step 5/5: Closing resources...")
        self._close_resources()

        logger.info("Graceful shutdown complete")
        sys.exit(0)

    def _sync_shutdown(self):
        logger.info("Synchronous shutdown...")
        for process in self._child_processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass
        self._close_resources()
        sys.exit(0)

    def _close_resources(self):
        try:
            from src.persistence import get_db
            db = get_db()
            db.close()
            logger.info("SQLite connection closed")
        except Exception:
            pass

        try:
            from src.providers import registry
            for name in ["mcp", "gemini", "anthropic", "openai", "groq", "ollama", "timps"]:
                prov = registry.get(name)
                if prov and hasattr(prov, '_session') and prov._session:
                    prov._session.close()
            logger.info("HTTP sessions closed")
        except Exception:
            pass


_shutdown_instance: Optional[GracefulShutdown] = None


def get_shutdown() -> GracefulShutdown:
    global _shutdown_instance
    if _shutdown_instance is None:
        _shutdown_instance = GracefulShutdown()
    return _shutdown_instance
