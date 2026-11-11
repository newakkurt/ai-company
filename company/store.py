"""Local SQLite task, assignment, agent-output, knowledge, and audit store."""
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
                    task_id TEXT PRIMARY KEY, description TEXT NOT NULL,
                    status TEXT NOT NULL, owner TEXT NOT NULL, execution_mode TEXT NOT NULL,
                    approval_required INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    event_type TEXT NOT NULL, actor TEXT NOT NULL,
                    details_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assignments (
                    assignment_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    agent_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'suggested',
                    assigned_at TEXT NOT NULL, UNIQUE(task_id, agent_id)
                );
                CREATE TABLE IF NOT EXISTS agent_outputs (
                    output_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    agent_id TEXT NOT NULL, output_text TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_notes (
                    note_id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
                    tags TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
                CREATE INDEX IF NOT EXISTS idx_assignments_task ON assignments(task_id);
                CREATE INDEX IF NOT EXISTS idx_agent_outputs_task ON agent_outputs(task_id);
                CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge_notes(created_at);
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
                VALUES (?, ?, 'planned', 'ceo', 'dry_run', 1, ?, ?)""",
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

    def assign_agents(self, task_id: str, agent_ids: list[str]):
        """Record suggested owners only; this does not launch agents."""
        now = utc_now()
        with self._connect() as db:
            if db.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone() is None:
                raise KeyError(f"Task not found: {task_id}")
            for agent_id in dict.fromkeys(agent_ids):
                db.execute(
                    """INSERT OR IGNORE INTO assignments
                    (assignment_id, task_id, agent_id, status, assigned_at)
                    VALUES (?, ?, ?, 'suggested', ?)""",
                    (uuid.uuid4().hex, task_id, agent_id, now)
                )
            self._event(db, task_id, "agent_assignments_suggested", "ceo",
                        {"agent_ids": list(dict.fromkeys(agent_ids)), "execution": "not_started"})
            db.execute("UPDATE tasks SET updated_at=? WHERE task_id=?", (now, task_id))
        return self.list_assignments(task_id)

    def list_assignments(self, task_id: str):
        with self._connect() as db:
            rows = db.execute(
                "SELECT agent_id, status, assigned_at FROM assignments WHERE task_id=? ORDER BY assigned_at, agent_id",
                (task_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def record_agent_output(self, task_id: str, agent_id: str, output_text: str):
        with self._connect() as db:
            if db.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone() is None:
                raise KeyError(f"Task not found: {task_id}")
            now = utc_now()
            db.execute(
                "INSERT INTO agent_outputs (output_id, task_id, agent_id, output_text, created_at) VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, task_id, agent_id, output_text, now)
            )
            self._event(db, task_id, "agent_analysis_saved", agent_id,
                        {"output_chars": len(output_text), "execution": "analysis_only"})
        return True

    def list_agent_outputs(self, task_id: str):
        with self._connect() as db:
            rows = db.execute(
                "SELECT agent_id, output_text, created_at FROM agent_outputs WHERE task_id=? ORDER BY created_at",
                (task_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def remember(self, title: str, body: str, tags: list[str] | None = None):
        title, body = title.strip(), body.strip()
        if not title or not body:
            raise ValueError("Knowledge title and body are required")
        note_id = f"note-{uuid.uuid4().hex[:10]}"
        with self._connect() as db:
            db.execute(
                "INSERT INTO knowledge_notes (note_id,title,body,tags,created_at) VALUES (?,?,?,?,?)",
                (note_id, title, body, json.dumps(tags or [], ensure_ascii=False), utc_now())
            )
        return note_id

    def search_knowledge(self, query: str = "", limit: int = 20):
        with self._connect() as db:
            rows = db.execute(
                "SELECT note_id,title,body,tags,created_at FROM knowledge_notes ORDER BY created_at DESC"
            ).fetchall()
        terms = [term.casefold() for term in query.split() if term.strip()]
        results = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item["tags"])
            haystack = (item["title"] + " " + item["body"] + " " + " ".join(item["tags"])).casefold()
            if all(term in haystack for term in terms):
                results.append(item)
            if len(results) >= limit:
                break
        return results

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
                    "SELECT * FROM events WHERE task_id=? ORDER BY created_at", (task_id,)
                ).fetchall()
            ]
            item["assignments"] = [
                dict(a) for a in db.execute(
                    "SELECT agent_id, status, assigned_at FROM assignments WHERE task_id=? ORDER BY assigned_at, agent_id",
                    (task_id,)
                ).fetchall()
            ]
            item["agent_outputs"] = self.list_agent_outputs(task_id)
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
