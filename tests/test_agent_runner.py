import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call

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
        self.assertTrue(all(a["status"] == "completed" for a in saved["assignments"]))

    def test_ceo_runs_last_and_receives_specialist_analysis(self):
        provider = Mock()
        provider.generate.side_effect = lambda system, prompt: "CEO summary" if system.startswith("You are CEO") else "Specialist result"
        results = run_task(self.task["task_id"], store=self.store, provider=provider)
        self.assertEqual(results[-1]["agent_id"], "ceo")
        ceo_prompt = provider.generate.call_args_list[-1].args[1]
        self.assertIn("Specialist result", ceo_prompt)


    def test_all_14_roles_can_run_and_ceo_synthesizes_last(self):
        from company.agents import load_agents
        agent_ids = [agent.id for agent in load_agents()]
        self.store.assign_agents(self.task["task_id"], agent_ids)
        provider = Mock()
        provider.generate.return_value = "Role analysis."
        results = run_task(self.task["task_id"], store=self.store, provider=provider)
        self.assertEqual(len(results), 14)
        self.assertEqual(results[-1]["agent_id"], "ceo")
        self.assertEqual(len(self.store.get_task(self.task["task_id"])["agent_outputs"]), 14)

    def test_runner_rejects_unknown_task(self):
        with self.assertRaises(KeyError):
            run_task("missing-task", store=self.store, provider=Mock())


if __name__ == "__main__":
    unittest.main()
