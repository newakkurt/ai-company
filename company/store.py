"""SQLite development store and secured Supabase PostgREST cloud store."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import base64
import hashlib
import os
import sqlite3
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "company.db"
# A claimed task is considered abandoned after this many quiet minutes. It must
# comfortably exceed the slowest single LLM call (retries and timeouts included),
# otherwise a second worker re-claims a task that is still being processed.
STALE_LEASE_MINUTES = 15
MAX_PRODUCT_ARTIFACT_BYTES = 1_500_000


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
        """Idempotent per (task, agent): returns False when an output already exists.

        This narrows the race between overlapping workers; a UNIQUE(task_id, agent_id)
        constraint in the database is still the authoritative guard.
        """
        existing = self._request("agent_outputs", params={
            "select": "output_id", "task_id": f"eq.{task_id}",
            "agent_id": f"eq.{agent_id}", "limit": "1",
        })
        if existing:
            self._request("assignments", "PATCH", {
                "task_id": f"eq.{task_id}", "agent_id": f"eq.{agent_id}",
            }, {"status": "completed"}, "return=minimal")
            return False
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

    def requeue_stale_tasks(self, stale_minutes: int = STALE_LEASE_MINUTES):
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

    def fail_task(self, task_id: str, error_type: str, error_summary: str | None = None):
        now = utc_now()
        self._request("tasks", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "eq.running",
        }, {"status": "failed", "updated_at": now}, "return=minimal")
        self._request("assignments", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "in.(suggested,running)",
        }, {"status": "failed"}, "return=minimal")
        details = {"error_type": error_type, "retry_policy": "manual_review"}
        if error_summary:
            details["error_summary"] = error_summary[:240]
        self._event(task_id, "agent_task_failed", "worker", details)

    def requeue_failed_task(self, task_id: str, max_retries: int = 2, min_age_minutes: int = 30) -> bool:
        """Bounded retry of a failed dry-run task. Saved agent outputs are reused on resume."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=min_age_minutes)).isoformat()
        rows = self._request("tasks", params={
            "select": "task_id", "task_id": f"eq.{task_id}", "status": "eq.failed",
            "execution_mode": "eq.dry_run", "updated_at": f"lt.{cutoff}", "limit": "1",
        })
        if not rows:
            return False
        retries = self._request("events", params={
            "select": "event_id", "task_id": f"eq.{task_id}",
            "event_type": "eq.agent_task_retried",
        })
        if len(retries) >= max_retries:
            return False
        changed = self._request("tasks", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "eq.failed",
        }, {"status": "planned", "updated_at": utc_now()}, "return=representation")
        if not changed:
            return False
        self._request("assignments", "PATCH", {
            "task_id": f"eq.{task_id}", "status": "eq.failed",
        }, {"status": "suggested"}, "return=minimal")
        self._event(task_id, "agent_task_retried", "scheduler", {
            "attempt": len(retries) + 1, "max_retries": max_retries,
        })
        return True

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



    def reserve_mail_send(self, message_id: str, sender: str, max_total: int, max_sender: int) -> bool:
        if not message_id or not sender:
            return False
        existing = self._request("mail_send_log", params={
            "select": "message_id", "message_id": f"eq.{message_id}", "limit": "1",
        })
        if existing:
            return False
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        rows = self._request("mail_send_log", params={
            "select": "message_id,sender_email", "status": "in.(reserved,sent)",
            "reserved_at": f"gte.{day_start}", "limit": "1000",
        })
        if len(rows) >= max_total:
            return False
        if sum(1 for row in rows if row.get("sender_email", "").casefold() == sender.casefold()) >= max_sender:
            return False
        created = self._request("mail_send_log", "POST", {"on_conflict": "message_id"}, {
            "message_id": message_id, "sender_email": sender.casefold(),
            "status": "reserved", "reserved_at": now.isoformat(),
        }, "resolution=ignore-duplicates,return=representation")
        return bool(created)

    def update_mail_send(self, message_id: str, status: str, error_type: str | None = None):
        if status not in ("sent", "failed"):
            raise ValueError("Invalid mail send status")
        return self._request("mail_send_log", "PATCH", {
            "message_id": f"eq.{message_id}", "status": "eq.reserved",
        }, {"status": status, "sent_at": utc_now() if status == "sent" else None,
            "error_type": error_type}, "return=minimal")

    def save_product_release(self, release: dict, artifact: bytes):
        if not isinstance(artifact, bytes) or not artifact or len(artifact) > MAX_PRODUCT_ARTIFACT_BYTES:
            raise ValueError("Product artifact is empty or exceeds the 1.5 MB storage limit")
        digest = hashlib.sha256(artifact).hexdigest()
        if release.get("checksum") and release["checksum"] != digest:
            raise ValueError("Product artifact checksum does not match release metadata")
        manifest = {k: v for k, v in release.items()
                    if k not in {"download_path", "checksum_path", "backup_path"}}
        item = {
            "product_id": release["product_id"],
            "name": release["name"],
            "version": release["version"],
            "summary": release.get("summary", ""),
            "release_status": release.get("release_status", "review_required"),
            "manifest_json": manifest,
            "artifact_base64": base64.b64encode(artifact).decode("ascii"),
            "sha256": digest,
            "artifact_bytes": len(artifact),
            "created_at": release.get("created_at") or utc_now(),
        }
        self._request("product_releases", "POST", {"on_conflict": "product_id"}, item,
                     "resolution=merge-duplicates,return=minimal")
        return self.get_product_release(item["product_id"])

    def get_product_release(self, product_id: str):
        rows = self._request("product_releases", params={
            "select": "*", "product_id": f"eq.{product_id}", "limit": "1",
        })
        return rows[0] if rows else None

    def list_product_releases(self, limit: int = 50):
        return self._request("product_releases", params={
            "select": "product_id,name,version,summary,release_status,sha256,artifact_bytes,created_at",
            "order": "created_at.desc", "limit": str(max(1, min(limit, 100))),
        })

    def create_approval_request(self, action: str, scope: dict, requested_by: str, expires_hours: int = 24):
        now = datetime.now(timezone.utc)
        item = {
            "approval_id": f"approval-{uuid.uuid4().hex}",
            "action": action,
            "scope_json": scope or {},
            "requested_by": requested_by,
            "status": "pending",
            "requested_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=expires_hours)).isoformat(),
        }
        self._request("approval_requests", "POST", body=item, prefer="return=minimal")
        return self.get_approval_request(item["approval_id"])

    def get_approval_request(self, approval_id: str):
        rows = self._request("approval_requests", params={
            "select": "*", "approval_id": f"eq.{approval_id}", "limit": "1",
        })
        return rows[0] if rows else None

    def list_approval_requests(self, status: str | None = None, limit: int = 100):
        params = {"select": "*", "order": "requested_at.desc",
                  "limit": str(max(1, min(limit, 200)))}
        if status:
            params["status"] = f"eq.{status}"
        return self._request("approval_requests", params=params)

    def decide_approval_request(self, approval_id: str, decision: str, actor: str, note: str = ""):
        if decision not in ("approved", "rejected"):
            raise ValueError("Decision must be approved or rejected")
        item = self.get_approval_request(approval_id)
        if item is None:
            raise KeyError(f"Approval request not found: {approval_id}")
        if item["status"] != "pending":
            raise ValueError(f"Approval request is not pending: {item['status']}")
        now = utc_now()
        changed = self._request("approval_requests", "PATCH", {
            "approval_id": f"eq.{approval_id}", "status": "eq.pending",
            "expires_at": f"gt.{now}",
        }, {"status": decision, "decided_at": now, "decided_by": actor,
            "decision_note": note[:1000]}, "return=representation")
        if not changed:
            raise ValueError("Approval request expired or was already decided")
        return changed[0]

    def consume_approval_request(self, approval_id: str, action: str, scope: dict):
        item = self.get_approval_request(approval_id)
        if item is None:
            raise KeyError(f"Approval request not found: {approval_id}")
        if item["action"] != action:
            raise ValueError("Approval action does not match requested action")
        if (item.get("scope_json") or {}) != (scope or {}):
            raise ValueError("Approval scope does not match this operation")
        if item["status"] != "approved":
            raise ValueError(f"Approval is not usable: {item['status']}")
        now = utc_now()
        changed = self._request("approval_requests", "PATCH", {
            "approval_id": f"eq.{approval_id}", "status": "eq.approved",
            "expires_at": f"gt.{now}",
        }, {"status": "consumed", "consumed_at": now}, "return=representation")
        if not changed:
            raise ValueError("Approval expired or was already consumed")
        return changed[0]

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
                CREATE TABLE IF NOT EXISTS mail_send_log (
                    message_id TEXT PRIMARY KEY, sender_email TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'reserved'
                        CHECK(status IN ('reserved','sent','failed')),
                    reserved_at TEXT NOT NULL, sent_at TEXT, error_type TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mail_send_log_daily
                    ON mail_send_log(reserved_at, status, sender_email);
                CREATE TABLE IF NOT EXISTS product_releases (
                    product_id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL,
                    summary TEXT NOT NULL, release_status TEXT NOT NULL DEFAULT 'review_required',
                    manifest_json TEXT NOT NULL, artifact_base64 TEXT NOT NULL,
                    sha256 TEXT NOT NULL, artifact_bytes INTEGER NOT NULL CHECK(artifact_bytes > 0 AND artifact_bytes <= 1500000),
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_product_releases_created
                    ON product_releases(created_at);
                CREATE TABLE IF NOT EXISTS approval_requests (
                    approval_id TEXT PRIMARY KEY, action TEXT NOT NULL, scope_json TEXT NOT NULL,
                    requested_by TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','approved','rejected','consumed','expired')),
                    requested_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                    decided_at TEXT, decided_by TEXT, decision_note TEXT, consumed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_approval_requests_status_created
                    ON approval_requests(status, requested_at);
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
        """Idempotent per (task, agent): returns False when an output already exists."""
        with self._connect() as db:
            if db.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone() is None:
                raise KeyError(f"Task not found: {task_id}")
            if db.execute(
                "SELECT 1 FROM agent_outputs WHERE task_id=? AND agent_id=?", (task_id, agent_id)
            ).fetchone():
                db.execute(
                    "UPDATE assignments SET status='completed' WHERE task_id=? AND agent_id=?",
                    (task_id, agent_id)
                )
                return False
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

    def requeue_stale_tasks(self, stale_minutes: int = STALE_LEASE_MINUTES):
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

    def fail_task(self, task_id: str, error_type: str, error_summary: str | None = None):
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
            details = {"error_type": error_type, "retry_policy": "manual_review"}
            if error_summary:
                details["error_summary"] = error_summary[:240]
            self._event(db, task_id, "agent_task_failed", "worker", details)

    def requeue_failed_task(self, task_id: str, max_retries: int = 2, min_age_minutes: int = 30) -> bool:
        """Bounded retry of a failed dry-run task. Saved agent outputs are reused on resume."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=min_age_minutes)).isoformat()
        with self._connect() as db:
            row = db.execute(
                "SELECT status, updated_at FROM tasks WHERE task_id=? AND execution_mode='dry_run'",
                (task_id,)
            ).fetchone()
            if row is None or row["status"] != "failed" or row["updated_at"] >= cutoff:
                return False
            retries = db.execute(
                "SELECT COUNT(*) FROM events WHERE task_id=? AND event_type='agent_task_retried'",
                (task_id,)
            ).fetchone()[0]
            if retries >= max_retries:
                return False
            changed = db.execute(
                "UPDATE tasks SET status='planned', updated_at=? WHERE task_id=? AND status='failed'",
                (utc_now(), task_id)
            ).rowcount
            if not changed:
                return False
            db.execute(
                "UPDATE assignments SET status='suggested' WHERE task_id=? AND status='failed'",
                (task_id,)
            )
            self._event(db, task_id, "agent_task_retried", "scheduler", {
                "attempt": retries + 1, "max_retries": max_retries,
            })
            return True

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



    def reserve_mail_send(self, message_id: str, sender: str, max_total: int, max_sender: int) -> bool:
        if not message_id or not sender:
            return False
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self._connect() as db:
            existing = db.execute(
                "SELECT message_id FROM mail_send_log WHERE message_id=?", (message_id,)
            ).fetchone()
            if existing:
                return False
            rows = db.execute(
                "SELECT sender_email FROM mail_send_log WHERE status IN ('reserved','sent') AND reserved_at>=?",
                (day_start,),
            ).fetchall()
            if len(rows) >= max_total:
                return False
            if sum(1 for row in rows if row["sender_email"].casefold() == sender.casefold()) >= max_sender:
                return False
            db.execute(
                "INSERT INTO mail_send_log(message_id,sender_email,status,reserved_at) VALUES(?,?,'reserved',?)",
                (message_id, sender.casefold(), now.isoformat()),
            )
        return True

    def update_mail_send(self, message_id: str, status: str, error_type: str | None = None):
        if status not in ("sent", "failed"):
            raise ValueError("Invalid mail send status")
        with self._connect() as db:
            db.execute(
                """UPDATE mail_send_log SET status=?, sent_at=?, error_type=?
                   WHERE message_id=? AND status='reserved'""",
                (status, utc_now() if status == "sent" else None, error_type, message_id),
            )
        return True

    def save_product_release(self, release: dict, artifact: bytes):
        if not isinstance(artifact, bytes) or not artifact or len(artifact) > MAX_PRODUCT_ARTIFACT_BYTES:
            raise ValueError("Product artifact is empty or exceeds the 1.5 MB storage limit")
        digest = hashlib.sha256(artifact).hexdigest()
        if release.get("checksum") and release["checksum"] != digest:
            raise ValueError("Product artifact checksum does not match release metadata")
        manifest = {k: v for k, v in release.items()
                    if k not in {"download_path", "checksum_path", "backup_path"}}
        with self._connect() as db:
            db.execute(
                """INSERT INTO product_releases
                   (product_id,name,version,summary,release_status,manifest_json,
                    artifact_base64,sha256,artifact_bytes,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(product_id) DO UPDATE SET
                     manifest_json=excluded.manifest_json,
                     artifact_base64=excluded.artifact_base64,
                     sha256=excluded.sha256,
                     artifact_bytes=excluded.artifact_bytes""",
                (release["product_id"], release["name"], release["version"],
                 release.get("summary", ""), release.get("release_status", "review_required"),
                 json.dumps(manifest, ensure_ascii=False),
                 base64.b64encode(artifact).decode("ascii"), digest, len(artifact),
                 release.get("created_at") or utc_now()),
            )
        return self.get_product_release(release["product_id"])

    def get_product_release(self, product_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM product_releases WHERE product_id=?", (product_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["manifest_json"] = json.loads(item["manifest_json"])
        return item

    def list_product_releases(self, limit: int = 50):
        with self._connect() as db:
            rows = db.execute(
                """SELECT product_id,name,version,summary,release_status,sha256,
                          artifact_bytes,created_at
                   FROM product_releases ORDER BY created_at DESC LIMIT ?""",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_approval_request(self, action: str, scope: dict, requested_by: str, expires_hours: int = 24):
        now = datetime.now(timezone.utc)
        approval_id = f"approval-{uuid.uuid4().hex}"
        expires_at = (now + timedelta(hours=expires_hours)).isoformat()
        with self._connect() as db:
            db.execute(
                """INSERT INTO approval_requests
                   (approval_id, action, scope_json, requested_by, status, requested_at, expires_at)
                   VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
                (approval_id, action, json.dumps(scope or {}, ensure_ascii=False),
                 requested_by, now.isoformat(), expires_at),
            )
        return self.get_approval_request(approval_id)

    def get_approval_request(self, approval_id: str):
        with self._connect() as db:
            row = db.execute("SELECT * FROM approval_requests WHERE approval_id=?", (approval_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["scope_json"] = json.loads(item["scope_json"])
        return item

    def list_approval_requests(self, status: str | None = None, limit: int = 100):
        with self._connect() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM approval_requests WHERE status=? ORDER BY requested_at DESC LIMIT ?",
                    (status, max(1, min(limit, 200))),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM approval_requests ORDER BY requested_at DESC LIMIT ?",
                    (max(1, min(limit, 200)),),
                ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["scope_json"] = json.loads(item["scope_json"])
            items.append(item)
        return items

    def decide_approval_request(self, approval_id: str, decision: str, actor: str, note: str = ""):
        if decision not in ("approved", "rejected"):
            raise ValueError("Decision must be approved or rejected")
        with self._connect() as db:
            row = db.execute(
                "SELECT status, expires_at FROM approval_requests WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Approval request not found: {approval_id}")
            if row["status"] != "pending":
                raise ValueError(f"Approval request is not pending: {row['status']}")
            now = datetime.now(timezone.utc)
            expiry = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
            if expiry <= now:
                db.execute("UPDATE approval_requests SET status='expired' WHERE approval_id=?", (approval_id,))
                raise ValueError("Approval request has expired")
            db.execute(
                """UPDATE approval_requests SET status=?, decided_at=?, decided_by=?, decision_note=?
                   WHERE approval_id=? AND status='pending'""",
                (decision, now.isoformat(), actor, note[:1000], approval_id),
            )
        return self.get_approval_request(approval_id)

    def consume_approval_request(self, approval_id: str, action: str, scope: dict):
        with self._connect() as db:
            row = db.execute("SELECT * FROM approval_requests WHERE approval_id=?", (approval_id,)).fetchone()
            if row is None:
                raise KeyError(f"Approval request not found: {approval_id}")
            item = dict(row)
            item["scope_json"] = json.loads(item["scope_json"])
            if item["action"] != action:
                raise ValueError("Approval action does not match requested action")
            if item["scope_json"] != (scope or {}):
                raise ValueError("Approval scope does not match this operation")
            if item["status"] != "approved":
                raise ValueError(f"Approval is not usable: {item['status']}")
            now = datetime.now(timezone.utc)
            expiry = datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00"))
            if expiry <= now:
                db.execute("UPDATE approval_requests SET status='expired' WHERE approval_id=?", (approval_id,))
                raise ValueError("Approval has expired")
            changed = db.execute(
                """UPDATE approval_requests SET status='consumed', consumed_at=?
                   WHERE approval_id=? AND status='approved'""",
                (now.isoformat(), approval_id),
            ).rowcount
            if not changed:
                raise ValueError("Approval was already consumed")
        return self.get_approval_request(approval_id)

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
