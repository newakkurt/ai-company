import json
import tempfile
import unittest
from pathlib import Path

from company.dead_letter import archive_if_exhausted
from company.store import TaskStore


class DeadLetterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.temp.name) / "company.sqlite3")
        task = self.store.create_task("Exercise bounded dead-letter archival")
        self.task_id = task["task_id"]
        self.store.assign_agents(self.task_id, ["ceo"])
        self.store.claim_next_task()
        self.store.fail_task(self.task_id, "SyntheticProviderError")
        with self.store._connect() as db:
            for attempt in (1, 2):
                self.store._event(db, self.task_id, "agent_task_retried", "scheduler",
                                  {"attempt": attempt, "max_retries": 2})
            db.execute("UPDATE tasks SET updated_at=? WHERE task_id=?",
                       ("2000-01-01T00:00:00+00:00", self.task_id))

    def tearDown(self):
        self.temp.cleanup()

    def test_exhausted_task_is_archived_once(self):
        self.assertTrue(archive_if_exhausted(self.store, self.task_id))
        self.assertFalse(archive_if_exhausted(self.store, self.task_id))
        with self.store._connect() as db:
            row = db.execute("SELECT retry_count,last_error FROM dead_letter_tasks WHERE task_id=?",
                             (self.task_id,)).fetchone()
        self.assertEqual(row["retry_count"], 2)
        self.assertEqual(json.loads(row["last_error"])["error_type"], "SyntheticProviderError")

    def test_task_is_not_archived_before_retry_budget_exhausted(self):
        with self.store._connect() as db:
            db.execute("DELETE FROM events WHERE task_id=? AND event_type='agent_task_retried'",
                       (self.task_id,))
        self.assertFalse(archive_if_exhausted(self.store, self.task_id))


if __name__ == "__main__":
    unittest.main()
