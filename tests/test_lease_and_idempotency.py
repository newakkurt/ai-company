import inspect
import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from company.agent_runner import run_task
from company.llm import GeminiAPIError, GeminiProvider
from company.store import STALE_LEASE_MINUTES, SupabaseTaskStore, TaskStore


class StoreLeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "lease.db"
        self.store = TaskStore(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _age_task(self, task_id, minutes):
        old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        db = sqlite3.connect(self.db_path)
        try:
            db.execute("UPDATE tasks SET updated_at=? WHERE task_id=?", (old, task_id))
            db.commit()
        finally:
            db.close()

    def test_both_stores_share_one_lease_window(self):
        self.assertEqual(STALE_LEASE_MINUTES, 15)
        for cls in (TaskStore, SupabaseTaskStore):
            default = inspect.signature(cls.requeue_stale_tasks).parameters["stale_minutes"].default
            self.assertEqual(default, STALE_LEASE_MINUTES, cls.__name__)

    def test_running_task_inside_lease_is_not_reclaimed(self):
        task = self.store.create_task("lease test")
        self.assertEqual(self.store.claim_next_task(), task["task_id"])
        self._age_task(task["task_id"], STALE_LEASE_MINUTES - 5)
        self.assertIsNone(self.store.claim_next_task())
        self.assertEqual(self.store.get_task(task["task_id"])["status"], "running")

    def test_running_task_past_lease_is_requeued_and_claimable(self):
        task = self.store.create_task("lease test")
        self.store.claim_next_task()
        self._age_task(task["task_id"], STALE_LEASE_MINUTES + 5)
        self.assertEqual(self.store.claim_next_task(), task["task_id"])


class IdempotentOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "outputs.db")
        self.task = self.store.create_task("Review the network security architecture")
        self.task_id = self.task["task_id"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_second_write_for_same_agent_is_ignored(self):
        self.store.assign_agents(self.task_id, ["ceo", "qa_testing"])
        self.assertTrue(self.store.record_agent_output(self.task_id, "qa_testing", "first"))
        self.assertFalse(self.store.record_agent_output(self.task_id, "qa_testing", "second"))
        outputs = self.store.list_agent_outputs(self.task_id)
        self.assertEqual([o["output_text"] for o in outputs], ["first"])
        assignment = next(a for a in self.store.list_assignments(self.task_id) if a["agent_id"] == "qa_testing")
        self.assertEqual(assignment["status"], "completed")

    def test_runner_skips_role_saved_by_another_worker_mid_run(self):
        self.store.assign_agents(self.task_id, ["ceo", "qa_testing", "security_compliance"])
        calls = []

        def generate(system_prompt, user_prompt, *args, **kwargs):
            calls.append(system_prompt)
            if len(calls) == 1:  # a second worker finishes security_compliance meanwhile
                self.store.record_agent_output(self.task_id, "security_compliance", "from other worker")
            return "own output"

        provider = Mock()
        provider.generate.side_effect = generate
        results = run_task(self.task_id, store=self.store, provider=provider)

        self.assertEqual(len(calls), 2)  # qa_testing + CEO only; security_compliance not re-generated
        outputs = self.store.list_agent_outputs(self.task_id)
        security = [o for o in outputs if o["agent_id"] == "security_compliance"]
        self.assertEqual([o["output_text"] for o in security], ["from other worker"])
        self.assertEqual(len(outputs), 3)
        self.assertEqual(results[-1]["agent_id"], "ceo")
        self.assertIn("from other worker", provider.generate.call_args_list[-1].args[1])


class RetryAfterTests(unittest.TestCase):
    def _http_429(self, retry_after):
        return HTTPError("https://example.invalid", 429, "Too Many Requests",
                         {"Retry-After": retry_after}, io.BytesIO(b"{}"))

    def test_long_retry_after_fails_fast_so_fallback_can_run(self):
        provider = GeminiProvider(api_key="k")
        with patch("company.llm.urlopen", side_effect=self._http_429("900")) as urlopen, \
                patch("company.llm.time.sleep") as sleep:
            with self.assertRaises(GeminiAPIError) as ctx:
                provider.generate("s", "u")
        sleep.assert_not_called()
        self.assertEqual(urlopen.call_count, 1)
        self.assertIn("HTTP 429", str(ctx.exception))

    def test_short_retry_after_is_still_honoured(self):
        provider = GeminiProvider(api_key="k")
        ok = Mock()
        ok.__enter__ = lambda s: s
        ok.__exit__ = lambda s, *a: False
        ok.read.return_value = b'{"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}'
        with patch("company.llm.urlopen", side_effect=[self._http_429("3"), ok]), \
                patch("company.llm.time.sleep") as sleep:
            self.assertEqual(provider.generate("s", "u"), "ok")
        sleep.assert_called_once_with(3)


if __name__ == "__main__":
    unittest.main()
