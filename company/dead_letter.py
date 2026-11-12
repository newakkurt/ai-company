"""Bounded dead-letter archival for exhausted dry-run tasks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json


def archive_if_exhausted(store, task_id: str, max_retries: int = 2,
                         min_age_minutes: int = 30) -> bool:
    """Archive a failed task only after its bounded retry budget is exhausted."""
    task = store.get_task(task_id)
    if not task or task.get("status") != "failed":
        return False
    retries = sum(1 for event in task.get("events", [])
                  if event.get("event_type") == "agent_task_retried")
    if retries < max_retries:
        return False
    try:
        updated = datetime.fromisoformat(task["updated_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    if updated > datetime.now(timezone.utc) - timedelta(minutes=min_age_minutes):
        return False

    failed = [event for event in task.get("events", [])
              if event.get("event_type") == "agent_task_failed"]
    last_error = (failed[-1].get("details") or {}) if failed else {}
    snapshot = {
        "task_id": task_id,
        "status": task.get("status"),
        "owner": task.get("owner"),
        "execution_mode": task.get("execution_mode"),
        "assignments": task.get("assignments", []),
        "agent_outputs": task.get("agent_outputs", []),
        "events": task.get("events", []),
    }
    payload = {
        "task_id": task_id,
        "description": task.get("description", ""),
        "retry_count": retries,
        "last_error": last_error,
        "task_snapshot": snapshot,
    }

    if hasattr(store, "_request"):  # hosted Supabase store
        existing = store._request("dead_letter_tasks", params={
            "select": "task_id", "task_id": f"eq.{task_id}", "limit": "1",
        })
        if existing:
            return False
        store._request("dead_letter_tasks", "POST",
                       {"on_conflict": "task_id"}, payload,
                       "resolution=ignore-duplicates,return=minimal")
        store._event(task_id, "agent_task_dead_lettered", "scheduler",
                     {"retry_count": retries, "queue": "dead_letter_tasks"})
    else:  # local SQLite development store
        with store._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS dead_letter_tasks (
                task_id TEXT PRIMARY KEY REFERENCES tasks(task_id) ON DELETE CASCADE,
                description TEXT NOT NULL, retry_count INTEGER NOT NULL,
                last_error TEXT NOT NULL, task_snapshot TEXT NOT NULL,
                archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            existing = db.execute("SELECT 1 FROM dead_letter_tasks WHERE task_id=?",
                                  (task_id,)).fetchone()
            if existing:
                return False
            db.execute("""INSERT INTO dead_letter_tasks
                (task_id, description, retry_count, last_error, task_snapshot)
                VALUES (?, ?, ?, ?, ?)""",
                (task_id, payload["description"], retries,
                 json.dumps(last_error, ensure_ascii=False),
                 json.dumps(snapshot, ensure_ascii=False)))
            store._event(db, task_id, "agent_task_dead_lettered", "scheduler",
                         {"retry_count": retries, "queue": "dead_letter_tasks"})
    return True
