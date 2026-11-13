import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from company.harness.escalation import HumanReviewQueue
from company.harness.state_machine import read_trace
from company.store import TaskStore
from company.worker import process_one_task


class SimpleProvider:
    def generate(self, system_prompt, user_prompt):
        return "Analysis-only response."


class HumanReviewStateIntegrationTests(unittest.TestCase):
    def test_high_risk_task_enters_durable_queue_and_escalated_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = TaskStore(root / "tasks.sqlite3")
            task = store.create_task("Push config to production switch after maintenance.")
            store.assign_agents(task["task_id"], ["chief_of_staff"])
            with patch.dict(os.environ, {
                "AI_COMPANY_REVIEW_DB": str(root / "review.sqlite3"),
                "AI_COMPANY_TRACE_DIR": str(root / "traces"),
                "AI_COMPANY_WORKSPACE": str(root / "workspace"),
            }, clear=False):
                result = process_one_task(store=store, provider=SimpleProvider())
                reviews = HumanReviewQueue().list()
                trace = read_trace(task["task_id"], root / "traces")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0]["reason"], "high_risk_requires_human")
            self.assertEqual(trace[-1]["to"], "escalated")


if __name__ == "__main__":
    unittest.main()
