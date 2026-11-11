import tempfile
import unittest
from pathlib import Path

from company.store import TaskStore

class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_list_task(self):
        task = self.store.create_task("Test task")
        self.assertEqual(task["status"], "planned")
        self.assertEqual(task["execution_mode"], "dry_run")
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_empty_task_rejected(self):
        with self.assertRaises(ValueError):
            self.store.create_task("  ")

    def test_approval_is_recorded_without_execution(self):
        task = self.store.create_task("Approval test")
        approved = self.store.record_approval(task["task_id"], "owner", "Review complete")
        self.assertEqual(approved["status"], "approved_for_next_step")
        self.assertEqual(approved["events"][-1]["event_type"], "human_approval_recorded")

    def test_unknown_task_rejected(self):
        with self.assertRaises(KeyError):
            self.store.record_approval("missing", "owner")

if __name__ == "__main__":
    unittest.main()
