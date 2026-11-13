import unittest
from unittest.mock import patch

from company.harness.state_machine import record_transition, read_trace, verify_trace


class FakeEventStore:
    def __init__(self):
        self.rows = []

    def _request(self, table, method="GET", params=None, body=None, prefer=None):
        assert table == "events"
        if method == "POST":
            self.rows.append(dict(body))
            return []
        params = params or {}
        return [
            row for row in self.rows
            if row["task_id"] == params.get("task_id", "").removeprefix("eq.")
            and row["event_type"] == "harness_transition"
        ]


class HostedTraceTests(unittest.TestCase):
    def test_hash_chained_trace_is_stored_and_verified_from_supabase_events(self):
        store = FakeEventStore()
        env = {
            "SUPABASE_URL": "https://project.supabase.co",
            "SUPABASE_ANON_KEY": "public-test-key",
            "SUPABASE_DB_GATE_KEY": "server-test-gate",
        }
        with patch.dict("os.environ", env), patch("company.store.SupabaseTaskStore", return_value=store):
            record_transition("task-hosted", "planned", "running", "worker_claim", {"mode": "analysis_only"})
            record_transition("task-hosted", "running", "completed", "worker_done", {"count": 1})
            records = read_trace("task-hosted")
            valid, reason = verify_trace("task-hosted")
        self.assertEqual(len(records), 2)
        self.assertTrue(valid, reason)
        self.assertEqual(records[-1]["to"], "completed")


if __name__ == "__main__":
    unittest.main()
