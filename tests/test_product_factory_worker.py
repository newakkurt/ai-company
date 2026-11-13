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
        expected_metadata = {k: v for k, v in release.items()
                             if k not in {"download_path", "checksum_path", "backup_path"}}
        self.assertEqual(json.loads(store.saved[1].split("):\n", 1)[-1]), expected_metadata)
        self.assertEqual(store.completed, 2)

    def test_built_release_requests_exact_scope_publish_approval(self):
        from company.worker import _request_publish_approval

        class Store:
            def create_approval_request(self, action, scope, requested_by, hours):
                self.args = (action, scope, requested_by, hours)
                return {"approval_id": "approval-" + "a" * 32, "action": action, "scope_json": scope,
                        "requested_by": requested_by, "expires_at": "2026-11-16T00:00:00+00:00"}

        store, sent = Store(), []
        release = {"product_id": "prd-012345abcdef", "checksum": "ab" * 32, "name": "Network Ops Starter",
                   "version": "0.1.0", "qa": {"syntax_parse": "pass", "runtime_tests": "not_run",
                                              "security": "static_scan_only"}}
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_OWNER_CHAT_ID": "1"}), \
                patch("company.notifier._post", side_effect=lambda *a: sent.append(a) or True):
            _request_publish_approval(store, release)
        self.assertEqual(store.args, ("publish_product",
                                      {"product_id": "prd-012345abcdef", "sha256": "ab" * 32},
                                      "product_factory", 72))
        self.assertIn("çalışma testi=not_run", sent[0][2])
        self.assertIn("apv:ok:approval-", str(sent[0][3]))

    def test_publish_approval_failure_never_breaks_the_task(self):
        from company.worker import _request_publish_approval
        _request_publish_approval(object(), {"product_id": "x"})  # must not raise


if __name__ == "__main__":
    unittest.main()
