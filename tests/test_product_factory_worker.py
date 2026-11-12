import json
import unittest
from unittest.mock import patch

from company.worker import process_one_task


class FactoryWorkerTests(unittest.TestCase):
    def test_weekly_factory_task_builds_and_persists_release_metadata(self):
        task_id = "auto-digital-product-factory-2026w46"

        class FakeStore:
            def __init__(self):
                self.saved = None
                self.completed = None

            def claim_next_task(self):
                return task_id

            def get_task(self, _task_id):
                return {"task_id": task_id}

            def record_agent_output(self, _task_id, agent_id, output):
                self.saved = (agent_id, output)

            def save_product_release(self, release, artifact):
                self.release_saved = (release["product_id"], artifact)
                return {"product_id": release["product_id"]}

            def complete_task(self, _task_id, output_count):
                self.completed = output_count

            def fail_task(self, *_args, **_kwargs):
                raise AssertionError("task should not fail")

        store = FakeStore()
        specialist_results = [{"agent_id": "product_business", "output": "Pain evidence"}]
        release = {"product_id": "prd-012345abcdef", "release_status": "review_required",
                   "download_path": "/tmp/release.zip"}
        with patch("company.worker.run_task", return_value=specialist_results):
            with patch("company.worker.build_product", return_value=release) as build:
                with patch("company.worker._safe_notify"):
                    with patch("builtins.open", unittest.mock.mock_open(read_data=b"fake-zip")):
                        result = process_one_task(store=store, provider=object())

        build.assert_called_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(store.saved[0], "product_factory")
        self.assertEqual(store.release_saved, ("prd-012345abcdef", b"fake-zip"))
        self.assertEqual(json.loads(store.saved[1].split("):\n", 1)[-1]), release)
        self.assertEqual(store.completed, 2)


if __name__ == "__main__":
    unittest.main()
