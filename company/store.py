"""Local SQLite task and audit store. No external services or command execution."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import uuid

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "company.db"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class TaskStore:
    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    approval_required INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
            """)

    def create_task(self, description: str) -> dict:
        description = description.strip()
        if not description:
            raise ValueError("Task description cannot be empty")
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        now = utc_now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO tasks
                (task_id, description, status, owner, execution_mode,
                 approval_required, created_at, updated_at)
                VALUES (?, ?, 'planned', 'ceo-orchestrator', 'dry_run', 1, ?, ?)""",
                (task_id, description, now, now)
            )
            self._event(db, task_id, "task_created", "user", {"mode": "dry_run"})
        return self.get_task(task_id)

    def _event(self, db, task_id, event_type, actor, details):
        db.execute(
            """INSERT INTO events
            (event_id, task_id, event_type, actor, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (uuid.uuid4().hex, task_id, event_type, actor,
             json.dumps(details, ensure_ascii=False), utc_now())
        )

    def get_task(self, task_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                return None
            item = dict(row)
            item["approval_required"] = bool(item["approval_required"])
            item["events"] = [
                {**dict(e), "details": json.loads(e["details_json"])}
                for e in db.execute(
                    "SELECT * FROM events WHERE task_id=? ORDER BY created_at",
                    (task_id,)
                ).fetchall()
            ]
            return item

    def list_tasks(self, limit: int = 20):
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def record_approval(self, task_id: str, actor: str, note: str = ""):
        """Record human approval only; this never executes the task."""
        with self._connect() as db:
            row = db.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(f"Task not found: {task_id}")
            if row["status"] not in ("planned", "approval_required"):
                raise ValueError(f"Cannot approve task in status: {row['status']}")
            now = utc_now()
            db.execute(
                "UPDATE tasks SET status='approved_for_next_step', updated_at=? WHERE task_id=?",
                (now, task_id)
            )
            self._event(db, task_id, "human_approval_recorded", actor, {
                "note": note,
                "scope": "approval is only for the next explicitly described step; no execution is triggered"
            })
        return self.get_task(task_id)
