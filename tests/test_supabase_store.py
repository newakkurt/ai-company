import json
import os
import unittest
from unittest.mock import patch

from company.store import SupabaseTaskStore


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class SupabaseTaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "public-test-key",
            "SUPABASE_DB_GATE_KEY": "private-test-key",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = SupabaseTaskStore()

    @patch("company.store.urlopen")
    def test_request_sends_server_gate_header(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse([{"task_id": "task-1"}])
        result = self.store._request("tasks", params={"select": "*"})
        self.assertEqual(result[0]["task_id"], "task-1")
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_header("X-ai-company-key"), "private-test-key")
        self.assertEqual(request.get_header("Apikey"), "public-test-key")

    @patch("company.store.urlopen")
    def test_create_task_persists_task_and_audit_event(self, mocked_urlopen):
        mocked_urlopen.side_effect = [
            FakeResponse([]),  # task insert
            FakeResponse([]),  # task-created event
            FakeResponse([{
                "task_id": "task-test", "description": "Test cloud persistence",
                "status": "planned", "owner": "ceo", "execution_mode": "dry_run",
                "approval_required": True, "created_at": "2026-11-11T00:00:00+00:00",
                "updated_at": "2026-11-11T00:00:00+00:00",
            }]),  # task select
            FakeResponse([]),  # events select
            FakeResponse([]),  # assignments select
            FakeResponse([]),  # agent outputs select
        ]
        with patch("company.store.uuid.uuid4") as uuid4:
            uuid4.return_value.hex = "testtask000000000000000000000000"
            task = self.store.create_task("Test cloud persistence")
        self.assertEqual(task["task_id"], "task-testtask00")
        self.assertTrue(task["approval_required"])
        self.assertEqual(mocked_urlopen.call_count, 6)


if __name__ == "__main__":
    unittest.main()
