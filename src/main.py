"""
FastAPI application — entry point for the TIMPS Swarm.

Endpoints:
  POST /swarm/run        — Start a new swarm execution
  GET  /swarm/status     — Current swarm state (polling)
  WS   /ws               — Real-time WebSocket stream for the dashboard
  GET  /health           — Health check
"""
import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Lazy import to avoid graph build at import time in tests
_graph = None

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("timps.main")

app = FastAPI(title="TIMPS Swarm API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Redis-backed state store (falls back to in-memory if Redis unavailable) ─

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None
_runs_fallback: dict[str, dict] = {}   # used only when Redis is down


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis as redis_lib
        client = redis_lib.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        logger.info("Redis connected: %s", _REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — using in-memory fallback", exc)
        _redis_client = None
    return _redis_client


def _runs_set(run_id: str, data: dict):
    r = _get_redis()
    if r:
        try:
            r.set(f"timps:run:{run_id}", json.dumps(data), ex=86400)  # expire after 24h
            r.zadd("timps:runs", {run_id: time.time()})
            return
        except Exception as exc:
            logger.warning("Redis write failed: %s", exc)
    _runs_fallback[run_id] = data


def _runs_get(run_id: str) -> Optional[dict]:
    r = _get_redis()
    if r:
        try:
            raw = r.get(f"timps:run:{run_id}")
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis read failed: %s", exc)
    return _runs_fallback.get(run_id)


def _runs_list() -> list[str]:
    r = _get_redis()
    if r:
        try:
            return list(reversed(r.zrange("timps:runs", 0, -1)))
        except Exception as exc:
            logger.warning("Redis list failed: %s", exc)
    return list(reversed(list(_runs_fallback.keys())))


_active_websockets: list[WebSocket] = []


# ── Models ─────────────────────────────────────────────────────────────────

class SwarmRequest(BaseModel):
    request: str
    language: Optional[str] = "python"
    max_iterations: Optional[int] = 10


class SwarmResponse(BaseModel):
    run_id: str
    status: str
    message: str


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_graph():
    global _graph
    if _graph is None:
        from src.graph import app as graph_app
        _graph = graph_app
    return _graph


async def _broadcast(message: dict):
    """Send state update to all connected WebSocket clients."""
    dead = []
    for ws in _active_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _active_websockets.remove(ws)


def _build_dashboard_payload(run_id: str, state: dict) -> dict:
    """Convert swarm state into dashboard-friendly format."""
    tasks = state.get("tasks", [])

    agent_names = [
        "orchestrator", "product_manager", "architect", "code_generator",
        "code_reviewer", "qa_tester", "security_auditor", "performance_optimizer",
        "documentation_writer", "devops",
    ]

    agent_colors = {
        "orchestrator": "#6366f1", "product_manager": "#8b5cf6",
        "architect": "#06b6d4", "code_generator": "#10b981",
        "code_reviewer": "#f59e0b", "qa_tester": "#ec4899",
        "security_auditor": "#ef4444", "performance_optimizer": "#f97316",
        "documentation_writer": "#84cc16", "devops": "#64748b",
    }

    agents = []
    for i, name in enumerate(agent_names):
        role_tasks = [t for t in tasks if t.get("assigned_to") == name]
        running = [t for t in role_tasks if t["status"] == "running"]
        completed = [t for t in role_tasks if t["status"] == "completed"]

        agents.append({
            "id": f"agent-{i}",
            "name": name,
            "role": name,
            "status": "running" if running else ("completed" if completed else "pending"),
            "current_task": running[0]["description"][:60] if running else None,
            "adapter_loaded": "base",
            "latency_ms": 0,
            "tokens_generated": 0,
            "last_active": datetime.utcnow().isoformat(),
            "color": agent_colors.get(name, "#94a3b8"),
        })

    completed_count = len([t for t in tasks if t["status"] == "completed"])
    failed_count = len([t for t in tasks if t["status"] == "failed"])
    running_count = len([t for t in tasks if t["status"] == "running"])
    total_tasks = len(tasks)

    # Real avg_latency: approximate from completed task timestamps
    latencies = []
    for t in tasks:
        if t.get("created_at") and t.get("completed_at"):
            try:
                created = datetime.fromisoformat(t["created_at"])
                completed = datetime.fromisoformat(t["completed_at"])
                latencies.append((completed - created).total_seconds() * 1000)
            except Exception:
                pass
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0

    return {
        "run_id": run_id,
        "agents": agents,
        "tasks": tasks[:50],
        "metrics": {
            "total_agents": len(agent_names),
            "active_agents": running_count,
            "completed_tasks": completed_count,
            "failed_tasks": failed_count,
            "avg_latency": avg_latency,
            "throughput": round(completed_count / max(state.get("iteration_count", 1), 1), 2),
            "queue_depth": len([t for t in tasks if t["status"] == "pending"]),
        },
        "history": [
            {
                "time": f"{i}",
                "throughput": min(completed_count, i + 1),
                "active": running_count,
                "errors": failed_count,
            }
            for i in range(20)
        ],
        "artifacts": state.get("code_artifacts", []),
        "iteration": state.get("iteration_count", 0),
        "completed": state.get("completed", False),
    }


# ── Background swarm runner ────────────────────────────────────────────────

async def _run_swarm_async(run_id: str, request: str, language: str, max_iterations: int):
    logger.info("Starting swarm run %s", run_id)
    _runs_set(run_id, {"status": "running", "state": {}})

    initial_state = {
        "user_request": request,
        "language": language,
        "tasks": [],
        "code_artifacts": [],
        "review_comments": [],
        "errors": [],
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "requirements": "",
        "architecture_plan": "",
        "test_results": "",
        "security_report": "",
        "performance_report": "",
        "documentation": "",
        "final_deliverable": "",
        "completed": False,
    }

    graph = _get_graph()

    try:
        async for event in graph.astream(initial_state):
            node_name = list(event.keys())[0] if event else "unknown"
            node_state = event.get(node_name, {})

            # Merge into accumulated state
            run_data = _runs_get(run_id) or {"status": "running", "state": {}}
            for k, v in node_state.items():
                if isinstance(v, list):
                    existing = run_data["state"].get(k, [])
                    run_data["state"][k] = existing + v
                else:
                    run_data["state"][k] = v

            run_data["state"]["last_node"] = node_name
            _runs_set(run_id, run_data)
            logger.info("Swarm %s — node: %s", run_id, node_name)

            payload = _build_dashboard_payload(run_id, run_data["state"])
            await _broadcast(payload)

        run_data = _runs_get(run_id) or {}
        run_data["status"] = "completed"
        _runs_set(run_id, run_data)
        logger.info("Swarm run %s completed ✓", run_id)

    except Exception as exc:
        logger.error("Swarm run %s failed: %s", run_id, exc, exc_info=True)
        run_data = _runs_get(run_id) or {}
        run_data["status"] = "failed"
        run_data["error"] = str(exc)
        _runs_set(run_id, run_data)
        await _broadcast({"run_id": run_id, "status": "failed", "error": str(exc)})


# ── API Endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    r = _get_redis()
    return {
        "status": "ok",
        "service": "timps-swarm",
        "timestamp": datetime.utcnow().isoformat(),
        "redis": "connected" if r else "unavailable (using in-memory fallback)",
    }


@app.post("/swarm/run", response_model=SwarmResponse)
async def run_swarm(request: SwarmRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(
        _run_swarm_async,
        run_id,
        request.request,
        request.language or "python",
        request.max_iterations or 10,
    )
    return SwarmResponse(
        run_id=run_id,
        status="started",
        message=f"Swarm run {run_id} started. Connect to /ws for real-time updates.",
    )


@app.get("/swarm/status")
async def swarm_status(run_id: Optional[str] = None):
    if run_id:
        data = _runs_get(run_id)
        if data:
            return _build_dashboard_payload(run_id, data.get("state", {}))

    # Return latest run or empty state
    run_ids = _runs_list()
    if run_ids:
        latest_id = run_ids[0]
        data = _runs_get(latest_id) or {}
        return _build_dashboard_payload(latest_id, data.get("state", {}))

    return _build_dashboard_payload("none", {})


@app.get("/swarm/runs")
async def list_runs():
    run_ids = _runs_list()
    results = []
    for rid in run_ids:
        data = _runs_get(rid) or {}
        tasks = data.get("state", {}).get("tasks", [])
        results.append({
            "run_id": rid,
            "status": data.get("status", "unknown"),
            "tasks_done": len([t for t in tasks if t["status"] == "completed"]),
        })
    return results


# ── WebSocket ──────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_websockets.append(websocket)
    logger.info("Dashboard WebSocket connected (%d total)", len(_active_websockets))

    try:
        # Send current state immediately on connect
        run_ids = _runs_list()
        if run_ids:
            latest_id = run_ids[0]
            data = _runs_get(latest_id) or {}
            payload = _build_dashboard_payload(latest_id, data.get("state", {}))
            await websocket.send_json(payload)

        # Keep alive until client disconnects
        while True:
            await asyncio.sleep(2)
            run_ids = _runs_list()
            if run_ids:
                latest_id = run_ids[0]
                data = _runs_get(latest_id) or {}
                payload = _build_dashboard_payload(latest_id, data.get("state", {}))
                await websocket.send_json(payload)

    except WebSocketDisconnect:
        logger.info("Dashboard WebSocket disconnected")
    finally:
        if websocket in _active_websockets:
            _active_websockets.remove(websocket)


# ── Entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEV", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
