import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from company.agent_runner import run_task
from company.store import TaskStore


class AgentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "runner.db")
        self.task = self.store.create_task("Review the network security architecture")

    def tearDown(self):
        self.tmp.cleanup()

    def test_runner_assigns_and_saves_analysis_without_execution(self):
        provider = Mock()
        provider.generate.return_value = "Objective: review only."
        results = run_task(self.task["task_id"], store=self.store, provider=provider)
        saved = self.store.get_task(self.task["task_id"])
        self.assertEqual(len(results), len(saved["assignments"]))
        self.assertGreaterEqual(len(saved["agent_outputs"]), 1)
        self.assertEqual(saved["execution_mode"], "dry_run")
        self.assertEqual(saved["status"], "planned")
        self.assertTrue(all(a["status"] == "suggested" for a in saved["assignments"]))

    def test_runner_rejects_unknown_task(self):
        with self.assertRaises(KeyError):
            run_task("missing-task", store=self.store, provider=Mock())


if __name__ == "__main__":
    unittest.main()
