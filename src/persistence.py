import json
import os
import sqlite3
import time
from contextlib import contextmanager
from threading import Lock
from typing import Any, Optional

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'running',
    instruction TEXT,
    agent_type TEXT,
    working_dir TEXT,
    started_at REAL NOT NULL,
    finished_at REAL,
    wall_time_seconds REAL,
    total_tasks INTEGER DEFAULT 0,
    succeeded_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    waves_executed INTEGER DEFAULT 0,
    summary TEXT,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS run_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_id INTEGER NOT NULL,
    target TEXT,
    agent TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at REAL,
    finished_at REAL,
    elapsed_seconds REAL,
    attempts INTEGER DEFAULT 1,
    output_json TEXT,
    error TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    agent_name TEXT,
    run_id TEXT,
    task_id TEXT,
    provider TEXT
);

CREATE TABLE IF NOT EXISTS observer_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at REAL NOT NULL,
    tool TEXT NOT NULL,
    args_fingerprint TEXT NOT NULL,
    call_count INTEGER NOT NULL,
    time_span_seconds REAL,
    action_taken TEXT,
    sub_agents_spawned INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_token_usage_run ON token_usage(run_id);
CREATE INDEX IF NOT EXISTS idx_run_tasks_run ON run_tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_observer_patterns_tool ON observer_patterns(tool);
"""


class TimpsDB:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            timps_dir = os.path.expanduser("~/.timps")
            os.makedirs(timps_dir, exist_ok=True)
            db_path = os.path.join(timps_dir, "timps.db")
        self.db_path = db_path
        self._lock = Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        conn = self._get_conn()
        current_version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        ).fetchone()[0]
        if current_version < SCHEMA_VERSION:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @contextmanager
    def transaction(self):
        conn = self._get_conn()
        with self._lock:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def create_run(self, run_id: str, instruction: str, agent_type: str,
                   working_dir: str, total_tasks: int = 0) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO runs (id, instruction, agent_type, working_dir,
                                  started_at, total_tasks, status)
                VALUES (?, ?, ?, ?, ?, ?, 'running')
            """, (run_id, instruction, agent_type, working_dir,
                  time.time(), total_tasks))

    def update_run(self, run_id: str, **kwargs) -> None:
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [run_id]
        with self.transaction() as conn:
            conn.execute(f"UPDATE runs SET {set_clause} WHERE id = ?", values)

    def finish_run(self, run_id: str, status: str, result: dict) -> None:
        with self.transaction() as conn:
            conn.execute("""
                UPDATE runs SET status = ?, finished_at = ?, result_json = ?
                WHERE id = ?
            """, (status, time.time(), json.dumps(result, default=str), run_id))

    def get_run(self, run_id: str) -> Optional[dict]:
        with self.transaction() as conn:
            run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not run:
                return None
            tasks = conn.execute(
                "SELECT * FROM run_tasks WHERE run_id = ? ORDER BY task_id",
                (run_id,)
            ).fetchall()
            return {**dict(run), "tasks": [dict(t) for t in tasks]}

    def get_recent_runs(self, limit: int = 20) -> list[dict]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def create_task(self, run_id: str, task_id: int, target: str,
                    agent: str) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO run_tasks (run_id, task_id, target, agent, started_at)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, task_id, target, agent, time.time()))

    def update_task(self, run_id: str, task_id: int, **kwargs) -> None:
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [run_id, task_id]
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE run_tasks SET {set_clause} WHERE run_id = ? AND task_id = ?",
                values
            )

    def record_token_usage(
        self, model: str, input_tokens: int, output_tokens: int,
        cost_usd: float, agent_name: str = "", run_id: str = "",
        task_id: str = "", provider: str = ""
    ) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO token_usage (timestamp, model, input_tokens, output_tokens,
                                          cost_usd, agent_name, run_id, task_id, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (time.time(), model, input_tokens, output_tokens,
                  cost_usd, agent_name, run_id, task_id, provider))

    def get_cost_summary(self, days: int = 7) -> dict:
        with self.transaction() as conn:
            since = time.time() - (days * 86400)
            total = conn.execute("""
                SELECT COALESCE(SUM(cost_usd), 0) as total_cost,
                       COUNT(*) as total_calls,
                       COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                       COALESCE(SUM(output_tokens), 0) as total_output_tokens
                FROM token_usage WHERE timestamp > ?
            """, (since,)).fetchone()
            by_model = conn.execute("""
                SELECT model, COUNT(*) as calls,
                       SUM(input_tokens) as input_tokens,
                       SUM(output_tokens) as output_tokens,
                       SUM(cost_usd) as cost_usd
                FROM token_usage
                WHERE timestamp > ?
                GROUP BY model ORDER BY cost_usd DESC
            """, (since,)).fetchall()
            by_day = conn.execute("""
                SELECT date(timestamp, 'unixepoch', 'localtime') as day,
                       SUM(cost_usd) as cost_usd, COUNT(*) as calls
                FROM token_usage
                WHERE timestamp > ? GROUP BY day ORDER BY day DESC
            """, (since,)).fetchall()
            return {
                "period_days": days,
                "total_cost_usd": round(total["total_cost"], 4),
                "total_calls": total["total_calls"],
                "total_input_tokens": total["total_input_tokens"],
                "total_output_tokens": total["total_output_tokens"],
                "by_model": [dict(r) for r in by_model],
                "by_day": [dict(r) for r in by_day],
            }

    def save_pattern(self, tool: str, fingerprint: str, call_count: int,
                     time_span: float, action_taken: str,
                     sub_agents_spawned: int = 0) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO observer_patterns
                (detected_at, tool, args_fingerprint, call_count,
                 time_span_seconds, action_taken, sub_agents_spawned)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (time.time(), tool, fingerprint, call_count,
                  time_span, action_taken, sub_agents_spawned))

    def get_top_patterns(self, limit: int = 20) -> list[dict]:
        with self.transaction() as conn:
            rows = conn.execute("""
                SELECT tool, args_fingerprint,
                       COUNT(*) as times_detected,
                       AVG(call_count) as avg_call_count,
                       SUM(sub_agents_spawned) as total_spawned
                FROM observer_patterns
                GROUP BY tool, args_fingerprint
                ORDER BY times_detected DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def set_preference(self, key: str, value: Any) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO preferences (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value, updated_at = excluded.updated_at
            """, (key, json.dumps(value), time.time()))

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT value FROM preferences WHERE key = ?", (key,)
            ).fetchone()
            if row:
                return json.loads(row["value"])
            return default

    def vacuum(self):
        with self.transaction() as conn:
            conn.execute("VACUUM")

    def get_db_size_mb(self) -> float:
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path) / (1024 * 1024)
        return 0.0

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


_db_instance: Optional[TimpsDB] = None


def get_db() -> TimpsDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = TimpsDB()
    return _db_instance
