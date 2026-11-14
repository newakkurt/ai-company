import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from company.agent_runner import build_system_prompt, run_task
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

    def test_content_role_writes_the_requested_artifact_not_only_a_plan(self):
        from company.agents import load_agents
        content_agent = next(agent for agent in load_agents() if agent.id == "content_communications")
        prompt = build_system_prompt(content_agent)
        self.assertIn("write the complete requested artifact itself", prompt)
        self.assertIn("Do not substitute a plan", prompt)
        self.assertIn("Never infer product capabilities", prompt)

    def test_non_content_roles_keep_structured_report_guidance(self):
        from company.agents import load_agents
        ceo = next(agent for agent in load_agents() if agent.id == "ceo")
        prompt = build_system_prompt(ceo)
        self.assertIn("Objective, Findings, Proposed next steps", prompt)

    def test_runner_rejects_unknown_task(self):
        with self.assertRaises(KeyError):
            run_task("missing-task", store=self.store, provider=Mock())


if __name__ == "__main__":
    unittest.main()



class CeoContextBudgetTests(unittest.TestCase):
    def test_context_is_bounded_but_every_specialist_is_represented(self):
        from company.agent_runner import build_specialist_context
        results = [{"agent_id": f"a{i}", "output": "x" * 6000} for i in range(4)]
        text = build_specialist_context(results, budget=4000)
        self.assertLessEqual(len(text), 4000 + 4 * 120)  # budget plus short markers
        for i in range(4):
            self.assertIn(f"[a{i}]", text)
        self.assertIn("omitted", text)

    def test_short_outputs_are_not_truncated(self):
        from company.agent_runner import build_specialist_context
        text = build_specialist_context([{"agent_id": "a", "output": "short report"}], budget=4000)
        self.assertIn("short report", text)
        self.assertNotIn("omitted", text)

    def test_budget_env_override_has_a_floor(self):
        from company.agent_runner import ceo_context_budget
        with patch.dict(os.environ, {"AI_COMPANY_CEO_CONTEXT_CHARS": "10"}):
            self.assertEqual(ceo_context_budget(), 2000)
        with patch.dict(os.environ, {"AI_COMPANY_CEO_CONTEXT_CHARS": "bad"}):
            self.assertEqual(ceo_context_budget(), 7000)


class WebEvidenceInjectionTests(unittest.TestCase):
    def _run(self, supports_search, agents=("research_intelligence", "qa_testing")):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = TaskStore(Path(tmp.name) / "e.db")
        task = store.create_task("Research demand for network config tools")
        store.assign_agents(task["task_id"], list(agents))
        provider = Mock()
        provider.supports_search = supports_search
        provider.tiered = False
        provider.generate.return_value = "analysis"
        with patch("company.research_sources.demand_evidence_block",
                   return_value=("Live public evidence (retrieved X)\n- item | https://e.test/1", 1)):
            run_task(task["task_id"], store=store, provider=provider)
        return provider.generate.call_args_list

    def test_research_role_gets_evidence_when_provider_cannot_search(self):
        calls = self._run(False)
        prompts = [c.args[1] for c in calls]
        self.assertEqual(sum("Live public evidence" in p for p in prompts), 1)

    def test_network_infrastructure_role_gets_evidence_too(self):
        calls = self._run(False, agents=("network_infrastructure", "qa_testing"))
        self.assertEqual(sum("Live public evidence" in c.args[1] for c in calls), 1)

    def test_no_injection_when_provider_has_native_search(self):
        calls = self._run(True)
        self.assertFalse(any("Live public evidence" in c.args[1] for c in calls))
