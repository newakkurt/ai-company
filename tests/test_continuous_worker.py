import tempfile
import unittest
from pathlib import Path

from company.agents import load_agents
from company.llm import GeminiAPIError
from company.store import TaskStore
from company.worker import configured_provider_route, process_one_task


class FakeProvider:
    def generate(self, system_prompt, user_prompt):
        return "Synthetic dry-run analysis. No external action was taken."


class CountingProvider(FakeProvider):
    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt, user_prompt):
        self.calls += 1
        return super().generate(system_prompt, user_prompt)


class BrokenProvider:
    def generate(self, system_prompt, user_prompt):
        raise GeminiAPIError("Gemini API returned HTTP 403; check key access, model, and quota.")


class ContinuousWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.temp_dir.name) / "worker.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_task(self):
        task = self.store.create_task("Test continuous analysis worker in dry-run mode")
        self.store.assign_agents(task["task_id"], [agent.id for agent in load_agents()])
        return task["task_id"]

    def test_provider_route_reports_groq_only_without_secret_values(self):
        from unittest.mock import patch

        with patch.dict("os.environ", {"GROQ_API_KEY": "hidden", "GROQ_MODEL": "openai/gpt-oss-20b"}, clear=True):
            route, model = configured_provider_route()
        self.assertEqual(route, "groq")
        self.assertEqual(model, "openai/gpt-oss-20b")

    def test_provider_route_reports_gemini_with_groq_fallback(self):
        from unittest.mock import patch

        with patch.dict("os.environ", {"GEMINI_API_KEY": "hidden-g", "GROQ_API_KEY": "hidden-r"}, clear=True):
            route, _ = configured_provider_route()
        self.assertEqual(route, "gemini_primary_groq_fallback")

    def test_worker_claims_runs_and_persists_all_agent_outputs(self):
        task_id = self.make_task()

        result = process_one_task(store=self.store, provider=FakeProvider())

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["output_count"], 14)
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(len(task["agent_outputs"]), 14)
        self.assertTrue(all(a["status"] == "completed" for a in task["assignments"]))
        self.assertEqual(process_one_task(store=self.store, provider=FakeProvider())["status"], "idle")

    def test_stale_task_resumes_without_duplicate_agent_outputs(self):
        task_id = self.make_task()
        self.assertEqual(self.store.claim_next_task(), task_id)
        first_agent = load_agents()[0]
        self.store.record_agent_output(task_id, first_agent.id, "Checkpoint from the interrupted run.")

        with self.store._connect() as db:
            db.execute(
                "UPDATE tasks SET updated_at=? WHERE task_id=?",
                ("2000-01-01T00:00:00+00:00", task_id),
            )

        provider = CountingProvider()
        result = process_one_task(store=self.store, provider=provider)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["output_count"], 14)
        self.assertEqual(provider.calls, 13)
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(len(task["agent_outputs"]), 14)
        self.assertEqual(len({item["agent_id"] for item in task["agent_outputs"]}), 14)
        self.assertIn("agent_task_requeued", [event["event_type"] for event in task["events"]])


    def test_failed_job_is_persisted_and_not_silently_requeued(self):
        task_id = self.make_task()

        result = process_one_task(store=self.store, provider=BrokenProvider())

        self.assertEqual(result["status"], "failed")
        task = self.store.get_task(task_id)
        self.assertEqual(task["status"], "failed")
        self.assertEqual(len(task["agent_outputs"]), 0)
        self.assertTrue(all(a["status"] == "failed" for a in task["assignments"]))
        failed_event = next(event for event in task["events"] if event["event_type"] == "agent_task_failed")
        self.assertEqual(failed_event["details"]["error_type"], "GeminiAPIError")
        self.assertIn("HTTP 403", failed_event["details"]["error_summary"])
        self.assertEqual(process_one_task(store=self.store, provider=FakeProvider())["status"], "idle")


if __name__ == "__main__":
    unittest.main()
