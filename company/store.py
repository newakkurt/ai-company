"""SQLite development store and secured Supabase PostgREST cloud store."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sqlite3
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "company.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupabaseTaskStore:
    """Server-side PostgREST client protected by a private pre-request API-key gate."""

    def __init__(self):
        self.base_url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
        self.anon_key = os.environ["SUPABASE_ANON_KEY"]
        self.db_gate_key = os.environ["SUPABASE_DB_GATE_KEY"]

    def _request(self, table, method="GET", params=None, body=None, prefer=None):
        query = urlencode(params or {}, doseq=True)
        url = f"{self.base_url}/{table}" + (f"?{query}" if query else "")
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "x-ai-company-key": self.db_gate_key,
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=25) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase database request failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Supabase database is temporarily unreachable") from exc
        if not raw:
            return []
        return json.loads(raw.decode("utf-8"))

    def _event(self, task_id, event_type, actor, details):
        self._request("events", "POST", body={
            "event_id": uuid.uuid4().hex,
            "task_id": task_id,
            "event_type": event_type,
            "actor": actor,
            "details_json": details,
            "created_at": utc_now(),
        }, prefer="return=minimal")

    def create_task(self, description: str, task_id: str | None = None) -> dict:
        description = description.strip()
        if not description:
            raise ValueError("Task description cannot be empty")
        task_id = task_id or f"task-{uuid.uuid4().hex[:10]}"
        now = utc_now()
        self._request("tasks", "POST", {"on_conflict": "task_id"}, {
            "task_id": task_id, "description": description, "status": "planned",
            "owner": "ceo", "execution_mode": "dry_run", "approval_required": True,
            "created_at": now, "updated_at": now,
        }, "resolution=ignore-duplicates,return=minimal")
        self._event(task_id, "task_created", "user", {"mode": "dry_run"})
        return self.get_task(task_id)

    def get_payment_event(self, event_id: str):
        rows = self._request("payment_events", params={
            "select": "event_id,event_type,subscription_id,processed,received_at",
            "event_id": f"eq.{event_id}", "limit": "1",
        })
        return rows[0] if rows else None

    def record_payment_event(self, event_id: str, event_type: str, subscription_id: str | None):
        self._request("payment_events", "POST", {"on_conflict": "event_id"}, {
            "event_id": event_id, "event_type": event_type,
            "subscription_id": subscription_id, "processed": True,
            "received_at": utc_now(),
        }, "resolution=ignore-duplicates,return=minimal")

    def get_membership(self, subscription_id: str):
        rows = self._request("memberships", params={
            "select": "*", "subscription_id": f"eq.{subscription_id}", "limit": "1",
        })
        return rows[0] if rows else None

    def upsert_membership(self, membership: dict):
        self._request("memberships", "POST", {"on_conflict": "subscription_id"}, membership,
                      "resolution=merge-duplicates,return=minimal")
        return self.get_membership(membership["subscription_id"])

    def assign_agents(self, task_id: str, agent_ids: list[str]):
        now = utc_now()
        rows = [{
            "assignment_id": uuid.uuid4().hex, "task_id": task_id,
            "agent_id": agent_id, "status": "suggested", "assigned_at": now,
        } for agent_id in dict.fromkeys(agent_ids)]
        if rows:
            self._request("assignments", "POST", {"on_conflict": "task_id,agent_id"},
                          rows, "resolution=ignore-duplicates,return=minimal")
        self._event(task_id, "agent_assignments_suggested", "ceo", {
            "agent_ids": list(dict.fromkeys(agent_ids)), "execution": "not_started"
        })
        self._request("tasks", "PATCH", {"task_id": f"eq.{task_id}"},
                      {"updated_at": now}, "return=minimal")
        return self.list_assignments(task_id)

    def list_assignments(self, task_id: str):
        return self._request("assignments", params={
            "select": "agent_id,status,assigned_at", "task_id": f"eq.{task_id}",
            "order": "assigned_at.asc,agent_id.asc",
        })

    def record_agent_output(self, task_id: str, agent_id: str, output_text: str):
        self._request("agent_outputs", "POST", body={
            "output_id": uuid.uuid4().hex, "task_id": task_id, "agent_id": agent_id,
            "output_text": output_text, "created_at": utc_now(),
        }, prefer="return=minimal")
        self._event(task_id, "agent_analysis_saved", agent_id, {
            "output_chars": len(output_text), "execution": "analysis_only"
        })
        self._request("tasks", "PATCH", {"task_id": f"eq.{task_id}"},
                      {"updated_at": utc_now()}, "return=minimal")
        self._request("assignments", "PATCH", {
            "task_id": f"eq.{task_id}", "agent_id": f"eq.{agent_id}",
        }, {"status": "completed"}, "return=minimal")
        return True

    def list_agent_outputs(self, task_id: str):
        return self._request("agent_outputs", params={
            "select": "agent_id,output_text,created_at", "task_id": f"eq.{task_id}",
            "order": "created_at.asc",
        })

    def claim_next_task(self):
        """Atomically claim one analysis-only task; concurrent pollers cannot claim it twice."""
        self.requeue_stale_tasks()
        rows = self._request("tasks", params={
            "select": "task_id", "status": "eq.planned",
            "execution_mode": "eq.dry_run", "order": "created_at.asc",
            "limit": "1",
        })
        if not rows:
            return None
        task_id = rows[0]["task_id"]
        claimed = self._request("tasks", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "eq.planned",
            "execution_mode": "eq.dry_run",
        }, {"status": "running", "updated_at": utc_now()}, "return=representation")
        if not claimed:
            return None
        now = utc_now()
        self._request("assignments", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "eq.suggested",
        }, {"status": "running"}, "return=minimal")
        self._event(task_id, "agent_task_claimed", "worker", {"mode": "analysis_only"})
        return task_id

    def requeue_stale_tasks(self, stale_minutes: int = 60):
        """Recover interrupted dry-run tasks after a quiet lease window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)).isoformat()
        rows = self._request("tasks", params={
            "select": "task_id", "status": "eq.running",
            "execution_mode": "eq.dry_run", "updated_at": f"lt.{cutoff}",
            "order": "updated_at.asc", "limit": "20",
        })
        requeued = 0
        for row in rows:
            task_id = row["task_id"]
            changed = self._request("tasks", "PATCH", {
                "task_id": f"eq.{task_id}", "status": "eq.running",
                "updated_at": f"lt.{cutoff}", "execution_mode": "eq.dry_run",
            }, {"status": "planned", "updated_at": utc_now()}, "return=representation")
            if changed:
                self._event(task_id, "agent_task_requeued", "worker", {
                    "reason": "stale_worker_lease", "stale_minutes": stale_minutes,
                    "resume_policy": "skip_agents_with_persisted_outputs",
                })
                requeued += 1
        return requeued

    def complete_task(self, task_id: str, output_count: int):
        now = utc_now()
        self._request("tasks", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "eq.running",
        }, {"status": "completed", "updated_at": now}, "return=minimal")
        self._request("assignments", "PATCH", {"task_id": f"eq.{task_id}"},
                      {"status": "completed"}, "return=minimal")
        self._event(task_id, "agent_task_completed", "worker", {
            "output_count": output_count, "mode": "analysis_only"
        })

    def fail_task(self, task_id: str, error_type: str):
        now = utc_now()
        self._request("tasks", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "eq.running",
        }, {"status": "failed", "updated_at": now}, "return=minimal")
        self._request("assignments", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "in.(suggested,running)",
        }, {"status": "failed"}, "return=minimal")
        self._event(task_id, "agent_task_failed", "worker", {
            "error_type": error_type, "retry_policy": "manual_review"
        })

    def remember(self, title: str, body: str, tags: list[str] | None = None):
        title, body = title.strip(), body.strip()
        if not title or not body:
            raise ValueError("Knowledge title and body are required")
        note_id = f"note-{uuid.uuid4().hex[:10]}"
        self._request("knowledge_notes", "POST", body={
            "note_id": note_id, "title": title, "body": body,
            "tags": tags or [], "created_at": utc_now(),
        }, prefer="return=minimal")
        return note_id

    def search_knowledge(self, query: str = "", limit: int = 20):
        rows = self._request("knowledge_notes", params={
            "select": "note_id,title,body,tags,created_at", "order": "created_at.desc",
            "limit": str(max(1, min(limit * 5, 200))),
        })
        terms = [term.casefold() for term in query.split() if term.strip()]
        results = []
        for item in rows:
            haystack = (item["title"] + " " + item["body"] + " " + " ".join(item.get("tags") or [])).casefold()
            if all(term in haystack for term in terms):
                results.append(item)
            if len(results) >= limit:
                break
        return results

    def get_task(self, task_id: str):
        rows = self._request("tasks", params={
            "select": "*", "task_id": f"eq.{task_id}", "limit": "1",
        })
        if not rows:
            return None
        item = rows[0]
        item["approval_required"] = bool(item["approval_required"])
        item["events"] = self._request("events", params={
            "select": "*", "task_id": f"eq.{task_id}", "order": "created_at.asc",
        })
        for event in item["events"]:
            event["details"] = event.pop("details_json", {}) or {}
        item["assignments"] = self.list_assignments(task_id)
        item["agent_outputs"] = self.list_agent_outputs(task_id)
        return item

    def list_tasks(self, limit: int = 20):
        rows = self._request("tasks", params={
            "select": "*", "order": "created_at.desc",
            "limit": str(max(1, min(limit, 100))),
        })
        for row in rows:
            row["approval_required"] = bool(row["approval_required"])
        return rows

    def record_approval(self, task_id: str, actor: str, note: str = ""):
        item = self.get_task(task_id)
        if item is None:
            raise KeyError(f"Task not found: {task_id}")
        if item["status"] not in ("planned", "approval_required"):
            raise ValueError(f"Cannot approve task in status: {item['status']}")
        self._request("tasks", "PATCH", {"task_id": f"eq.{task_id}"},
                      {"status": "approved_for_next_step", "updated_at": utc_now()},
                      "return=minimal")
        self._event(task_id, "human_approval_recorded", actor, {
            "note": note,
            "scope": "approval is only for the next explicitly described step; no execution is triggered",
        })
        return self.get_task(task_id)


class TaskStore:
    """Use Supabase in hosted environments and SQLite for local development."""

    def __new__(cls, db_path: Path | str = DB_PATH):
        if all(os.getenv(k) for k in (
            "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_DB_GATE_KEY"
        )):
            return SupabaseTaskStore()
        return super().__new__(cls)

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
                CREATE TABLE IF NOT EXISTS payment_events (
                    event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
                    subscription_id TEXT, processed INTEGER NOT NULL DEFAULT 1,
                    received_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memberships (
                    subscription_id TEXT PRIMARY KEY, supporter_email TEXT,
                    supporter_name TEXT, membership_level_id INTEGER NOT NULL,
                    membership_level_name TEXT, amount REAL NOT NULL, currency TEXT NOT NULL,
                    status TEXT NOT NULL, current_period_end TEXT, task_id TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
                CREATE INDEX IF NOT EXISTS idx_assignments_task ON assignments(task_id);
                CREATE INDEX IF NOT EXISTS idx_agent_outputs_task ON agent_outputs(task_id);
                CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge_notes(created_at);
            """)

    def create_task(self, description: str, task_id: str | None = None) -> dict:
        description = description.strip()
        if not description:
            raise ValueError("Task description cannot be empty")
        task_id = task_id or f"task-{uuid.uuid4().hex[:10]}"
        now = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO tasks
                (task_id, description, status, owner, execution_mode,
                 approval_required, created_at, updated_at)
                VALUES (?, ?, 'planned', 'ceo', 'dry_run', 1, ?, ?)""",
                (task_id, description, now, now)
            )
            if cursor.rowcount:
                self._event(db, task_id, "task_created", "user", {"mode": "dry_run"})
        return self.get_task(task_id)

    def get_payment_event(self, event_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM payment_events WHERE event_id=?", (event_id,)).fetchone()
            return dict(row) if row else None

    def record_payment_event(self, event_id: str, event_type: str, subscription_id: str | None):
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO payment_events (event_id,event_type,subscription_id,processed,received_at) VALUES (?,?,?,?,?)",
                (event_id, event_type, subscription_id, 1, utc_now())
            )

    def get_membership(self, subscription_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM memberships WHERE subscription_id=?", (subscription_id,)).fetchone()
            return dict(row) if row else None

    def upsert_membership(self, membership: dict):
        fields = ("subscription_id","supporter_email","supporter_name","membership_level_id",
                  "membership_level_name","amount","currency","status","current_period_end","task_id","updated_at")
        values = [membership.get(field) for field in fields]
        with self._connect() as db:
            db.execute(
                """INSERT INTO memberships (subscription_id,supporter_email,supporter_name,membership_level_id,
                membership_level_name,amount,currency,status,current_period_end,task_id,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(subscription_id) DO UPDATE SET
                supporter_email=excluded.supporter_email,supporter_name=excluded.supporter_name,
                membership_level_id=excluded.membership_level_id,membership_level_name=excluded.membership_level_name,
                amount=excluded.amount,currency=excluded.currency,status=excluded.status,
                current_period_end=excluded.current_period_end,task_id=excluded.task_id,updated_at=excluded.updated_at""",
                values
            )
        return self.get_membership(membership["subscription_id"])

    def _event(self, db, task_id, event_type, actor, details):
        db.execute(
            """INSERT INTO events
            (event_id, task_id, event_type, actor, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (uuid.uuid4().hex, task_id, event_type, actor,
             json.dumps(details, ensure_ascii=False), utc_now())
        )

    def assign_agents(self, task_id: str, agent_ids: list[str]):
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
            db.execute("UPDATE tasks SET updated_at=? WHERE task_id=?", (now, task_id))
            db.execute(
                "UPDATE assignments SET status='completed' WHERE task_id=? AND agent_id=?",
                (task_id, agent_id)
            )
        return True

    def list_agent_outputs(self, task_id: str):
        with self._connect() as db:
            rows = db.execute(
                "SELECT agent_id, output_text, created_at FROM agent_outputs WHERE task_id=? ORDER BY created_at",
                (task_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def claim_next_task(self):
        """Atomically claim one analysis-only task; concurrent pollers cannot claim it twice."""
        self.requeue_stale_tasks()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT task_id FROM tasks
                   WHERE status='planned' AND execution_mode='dry_run'
                   ORDER BY created_at ASC LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            task_id = row["task_id"]
            now = utc_now()
            changed = db.execute(
                """UPDATE tasks SET status='running', updated_at=?
                   WHERE task_id=? AND status='planned' AND execution_mode='dry_run'""",
                (now, task_id)
            ).rowcount
            if not changed:
                return None
            db.execute("UPDATE assignments SET status='running' WHERE task_id=? AND status='suggested'", (task_id,))
            self._event(db, task_id, "agent_task_claimed", "worker", {"mode": "analysis_only"})
            return task_id

    def requeue_stale_tasks(self, stale_minutes: int = 60):
        """Recover interrupted dry-run tasks after a quiet lease window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)).isoformat()
        with self._connect() as db:
            rows = db.execute(
                """SELECT task_id FROM tasks
                   WHERE status='running' AND execution_mode='dry_run' AND updated_at < ?
                   ORDER BY updated_at ASC LIMIT 20""",
                (cutoff,)
            ).fetchall()
            now = utc_now()
            for row in rows:
                task_id = row["task_id"]
                changed = db.execute(
                    """UPDATE tasks SET status='planned', updated_at=?
                       WHERE task_id=? AND status='running'
                       AND execution_mode='dry_run' AND updated_at < ?""",
                    (now, task_id, cutoff)
                ).rowcount
                if changed:
                    self._event(db, task_id, "agent_task_requeued", "worker", {
                        "reason": "stale_worker_lease", "stale_minutes": stale_minutes,
                        "resume_policy": "skip_agents_with_persisted_outputs",
                    })
            return len(rows)

    def complete_task(self, task_id: str, output_count: int):
        with self._connect() as db:
            now = utc_now()
            db.execute(
                "UPDATE tasks SET status='completed', updated_at=? WHERE task_id=? AND status='running'",
                (now, task_id)
            )
            db.execute("UPDATE assignments SET status='completed' WHERE task_id=?", (task_id,))
            self._event(db, task_id, "agent_task_completed", "worker", {
                "output_count": output_count, "mode": "analysis_only"
            })

    def fail_task(self, task_id: str, error_type: str):
        with self._connect() as db:
            now = utc_now()
            db.execute(
                "UPDATE tasks SET status='failed', updated_at=? WHERE task_id=? AND status='running'",
                (now, task_id)
            )
            db.execute(
                "UPDATE assignments SET status='failed' WHERE task_id=? AND status IN ('suggested','running')",
                (task_id,)
            )
            self._event(db, task_id, "agent_task_failed", "worker", {
                "error_type": error_type, "retry_policy": "manual_review"
            })

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
