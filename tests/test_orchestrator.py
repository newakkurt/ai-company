import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from company.orchestrator import create_task

class OrchestratorTests(unittest.TestCase):
    def test_task_is_planned_and_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("company.orchestrator.TASK_DIR", Path(tmp)):
                record = create_task("NetCmd backlog analysis")
                self.assertEqual(record["status"], "planned")
                self.assertEqual(record["execution_mode"], "dry_run")
                self.assertTrue((Path(tmp) / f"{record['task_id']}.json").exists())

    def test_empty_task_rejected(self):
        with self.assertRaises(ValueError):
            create_task("   ")

if __name__ == "__main__":
    unittest.main()
