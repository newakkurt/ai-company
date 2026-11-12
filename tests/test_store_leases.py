import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from company.store import TaskStore


class TaskLeaseHeartbeatTests(unittest.TestCase):
    def test_heartbeat_prevents_stale_requeue_and_completed_task_is_not_extended(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "leases.db")
            task = store.create_task("Run a long research task", task_id="task-heartbeat-1")
            task_id = task["task_id"] if isinstance(task, dict) else "task-heartbeat-1"
            self.assertEqual(store.claim_next_task(), task_id)
            with store._connect() as db:
                db.execute(
                    "UPDATE tasks SET updated_at=? WHERE task_id=?",
                    ((datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(), task_id),
                )
            self.assertTrue(store.heartbeat_task(task_id))
            self.assertEqual(store.requeue_stale_tasks(stale_minutes=15), 0)
            with store._connect() as db:
                db.execute(
                    "UPDATE tasks SET updated_at=? WHERE task_id=?",
                    ((datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(), task_id),
                )
            self.assertEqual(store.requeue_stale_tasks(stale_minutes=15), 1)
            self.assertFalse(store.heartbeat_task(task_id))


if __name__ == "__main__":
    unittest.main()
