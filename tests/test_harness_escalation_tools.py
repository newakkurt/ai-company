import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from company.agent_runner import run_task
from company.dead_letter import archive_if_exhausted
from company.harness.context_gate import (
    estimate_model_gb, fits_in_budget, select_context,
)
from company.harness.escalation import (
    MAX_ATTEMPTS, HumanReviewQueue, classify_risk, run_with_retries, verify_output,
)
from company.harness.routing import PrivacyRoutingError, Tier
from company.harness.tools import ToolBox
from company.store import TaskStore


class EscalationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue = HumanReviewQueue(Path(self.tmp.name) / "review.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_failing_task_is_attempted_at_most_three_times_then_escalated(self):
        func = Mock(side_effect=RuntimeError("nope"))
        outcome = run_with_retries(func, task_id="t1", description="routine job", queue=self.queue,
                                   max_attempts=99)
        self.assertEqual(func.call_count, MAX_ATTEMPTS)
        self.assertEqual((outcome.status, outcome.attempts), ("escalated", 3))
        pending = self.queue.list()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["reason"], "retry_budget_exhausted")

    def test_success_on_second_attempt_does_not_escalate(self):
        func = Mock(side_effect=[RuntimeError("x"), "good"])
        outcome = run_with_retries(func, task_id="t2", queue=self.queue)
        self.assertEqual((outcome.status, outcome.result, outcome.attempts), ("ok", "good", 2))
        self.assertEqual(self.queue.list(), [])

    def test_verification_failure_counts_as_an_attempt(self):
        func = Mock(return_value="")
        outcome = run_with_retries(func, task_id="t3", queue=self.queue,
                                   verify=lambda out: verify_output(out, min_chars=5))
        self.assertEqual(func.call_count, 3)
        self.assertEqual(outcome.status, "escalated")
        self.assertIn("verification_failed:output_too_short", outcome.errors[0])

    def test_high_risk_work_is_escalated_without_running(self):
        func = Mock()
        outcome = run_with_retries(func, task_id="t4", description="Müşteriye iade yap ve hukuki yanıt ver",
                                   queue=self.queue)
        func.assert_not_called()
        self.assertEqual(outcome.status, "escalated")
        self.assertEqual(set(classify_risk("iade ve dava")), {"financial", "legal"})
        # Read-only metric names do not escalate ...
        self.assertEqual(classify_risk("Report funnel stages, churn/refund and refund rate"), [])
        self.assertEqual(classify_risk("Aylık iade oranı raporu"), [])
        # ... but actions on money still do.
        self.assertEqual(classify_risk("Process a refund for order 42"), ["financial"])
        self.assertEqual(classify_risk("Report churn/refund, then issue a refund"), ["financial"])
        self.assertEqual(classify_risk("müşteriye iade yap"), ["financial"])

    def test_queue_is_idempotent_redacted_and_decidable(self):
        first = self.queue.enqueue("t5", "why", {"mail": "ali@example.com"})
        self.assertEqual(self.queue.enqueue("t5", "why"), first)
        self.assertNotIn("ali@example.com", self.queue.get(first)["payload"])
        self.assertEqual(self.queue.decide(first, "approved", "owner")["status"], "approved")
        with self.assertRaises(KeyError):
            self.queue.decide(first, "rejected", "owner")
        with self.assertRaises(ValueError):
            self.queue.decide(first, "maybe", "owner")

    def test_verify_output_blocks_secret_leaks(self):
        result = verify_output("here is gsk_abcdefghijklmnopqrstuvwx")
        self.assertFalse(result.ok)
        self.assertIn("secret_leak:api_key", result.reasons)

    def test_dead_letter_archival_enqueues_human_review(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"AI_COMPANY_REVIEW_DB": str(Path(tmp) / "r.db"),
                                        "AI_COMPANY_TRACE_DIR": str(Path(tmp) / "tr")}):
            store = TaskStore(Path(tmp) / "c.db")
            task_id = store.create_task("Exercise escalation")["task_id"]
            store.assign_agents(task_id, ["ceo"])
            store.claim_next_task()
            store.fail_task(task_id, "SyntheticError")
            with store._connect() as db:
                for attempt in (1, 2):
                    store._event(db, task_id, "agent_task_retried", "scheduler", {"attempt": attempt})
                db.execute("UPDATE tasks SET updated_at='2000-01-01T00:00:00+00:00' WHERE task_id=?",
                           (task_id,))
            self.assertTrue(archive_if_exhausted(store, task_id))
            pending = HumanReviewQueue().list()
            self.assertEqual([p["task_id"] for p in pending], [task_id])


class ToolBoxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.queue = HumanReviewQueue(self.root / "review.db")
        self.box = ToolBox(self.root, self.queue, allow_shell=True, task_id="tb")

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_read_edit_roundtrip_with_line_numbers(self):
        self.assertEqual(self.box.call("write_file", {"path": "n.txt", "content": "a\nb\nc\n"})["status"], "ok")
        self.assertIn("2\tb", self.box.call("read_file", {"path": "n.txt"})["content"])
        self.assertEqual(self.box.call("edit_file", {"path": "n.txt", "old": "b", "new": "B"})["status"], "ok")
        self.assertIn("2\tB", self.box.call("read_file", {"path": "n.txt"})["content"])

    def test_edit_requires_unique_match_and_overwrite_flag(self):
        self.box.call("write_file", {"path": "d.txt", "content": "x x"})
        self.assertEqual(self.box.call("edit_file", {"path": "d.txt", "old": "x", "new": "y"})["status"], "error")
        self.assertEqual(self.box.call("write_file", {"path": "d.txt", "content": "z"})["status"], "error")
        self.assertEqual(self.box.call("write_file", {"path": "d.txt", "content": "z", "overwrite": True})["status"], "ok")

    def test_sandbox_and_secret_protection(self):
        self.assertEqual(self.box.call("read_file", {"path": "../x"})["status"], "error")
        self.assertEqual(self.box.call("write_file", {"path": ".env", "content": "A=1"})["status"], "error")
        self.assertEqual(self.box.call("write_file", {"path": "k.txt",
                                                      "content": "gsk_abcdefghijklmnopqrstuvwx"})["status"], "error")

    def test_read_redacts_sensitive_values(self):
        (self.root / "cfg.txt").write_text("snmp-agent community read TopSecret1\n")
        out = self.box.call("read_file", {"path": "cfg.txt"})
        self.assertNotIn("TopSecret1", out["content"])
        self.assertIn("secret_assignment", out["redacted"])

    def test_shell_is_off_by_default(self):
        self.assertEqual(ToolBox(self.root, allow_shell=False).call("run_bash", {"command": "ls"})["status"],
                         "disabled")

    def test_shell_allow_deny_and_approval_queue(self):
        self.assertEqual(self.box.call("run_bash", {"command": "echo hello"})["output"].strip(), "hello")
        self.assertEqual(self.box.call("run_bash", {"command": "rm -rf /"})["status"], "denied")
        result = self.box.call("run_bash", {"command": "touch made.txt"})
        self.assertEqual(result["status"], "approval_required")
        self.assertFalse((self.root / "made.txt").exists())
        self.assertEqual(self.queue.list()[0]["reason"], "shell_command_needs_approval")

    def test_approved_command_runs(self):
        box = ToolBox(self.root, self.queue, allow_shell=True, approver=lambda c, v: True)
        self.assertEqual(box.call("run_bash", {"command": "touch made.txt"})["status"], "ok")
        self.assertTrue((self.root / "made.txt").exists())

    def test_shell_environment_does_not_leak_secrets(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "should-not-leak-1234"}):
            out = self.box.call("run_bash", {"command": "echo $GEMINI_API_KEY"})
        self.assertNotIn("should-not-leak", out["output"])

    def test_unknown_tool_and_bad_args_do_not_raise(self):
        self.assertEqual(self.box.call("nope")["status"], "error")
        self.assertEqual(self.box.call("read_file", {"bogus": 1})["status"], "error")


class ContextGateTests(unittest.TestCase):
    GUIDE = {"Yetki sınırları": "limits " * 20, "İnsan kontrolü": "human " * 20,
             "Güvenlik": "security " * 20, "Maliyet": "cost " * 20, "Kanıt ve doğruluk": "evidence " * 20}

    def test_only_relevant_tools_and_guidelines_are_loaded(self):
        plan = select_context("config dosyasını oku ve parola var mı incele", tier=Tier.SMALL_LOCAL,
                              guidelines=self.GUIDE)
        names = [n for n, _ in plan.tools]
        self.assertIn("read_file", names)
        self.assertNotIn("run_bash", names)
        titles = [t for t, _ in plan.guidelines]
        self.assertIn("Yetki sınırları", titles)
        self.assertIn("Güvenlik", titles)
        self.assertNotIn("Maliyet", titles)

    def test_small_tier_has_tool_and_token_caps(self):
        text = "oku yaz düzenle çalıştır test hatırla"
        small = select_context(text, tier=Tier.SMALL_LOCAL, guidelines=self.GUIDE)
        large = select_context(text, tier=Tier.LARGE_LOCAL, guidelines=self.GUIDE)
        self.assertLessEqual(len(small.tools), 3)
        self.assertGreater(len(large.tools), len(small.tools))
        self.assertTrue(any(kind == "tool" for kind, _ in small.dropped))

    def test_real_constitution_sections_are_loaded(self):
        plan = select_context("secret token güvenlik", tier=Tier.LARGE_LOCAL)
        self.assertTrue(plan.guidelines)

    def test_memory_budget_prevents_co_loading_two_large_models(self):
        big = estimate_model_gb(32, 4)
        self.assertLess(big, 28)
        self.assertTrue(fits_in_budget(0, big, budget_gb=32))
        self.assertFalse(fits_in_budget(big, big, budget_gb=32))
        self.assertTrue(fits_in_budget(big, estimate_model_gb(4, 4), budget_gb=48))


class RunnerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "runner.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_runner_redacts_leaked_secret_before_persisting(self):
        task = self.store.create_task("Review network security architecture")
        provider = Mock(spec=["generate"])
        provider.generate.return_value = "Use key gsk_abcdefghijklmnopqrstuvwx for the demo"
        run_task(task["task_id"], store=self.store, provider=provider)
        saved = self.store.get_task(task["task_id"])
        self.assertTrue(saved["agent_outputs"])
        self.assertNotIn("gsk_abcdefghijklmnopqrstuvwx", str(saved["agent_outputs"]))

    def test_runner_passes_task_kind_to_tiered_provider_and_blocks_sensitive_cloud(self):
        from company.harness.routing import TieredProvider
        cloud = Mock()
        cloud.generate.return_value = "cloud"
        cloud.supports_search = True
        cloud.configured = True
        router = TieredProvider(None, None, cloud)
        task = self.store.create_task("Sipariş sahibi TC 10000000146 için güvenlik incelemesi")
        with self.assertRaises(PrivacyRoutingError):
            run_task(task["task_id"], store=self.store, provider=router)
        cloud.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class WorkerHarnessIntegrationTests(unittest.TestCase):
    """End-to-end through process_one_task: trace + human queue, no network."""

    def test_sensitive_task_without_local_model_is_traced_failed_and_escalated(self):
        from company.harness.routing import TieredProvider
        from company.harness.state_machine import read_trace, verify_trace
        from company.worker import process_one_task
        cloud = Mock()
        cloud.supports_search, cloud.configured = True, True
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "AI_COMPANY_REVIEW_DB": str(Path(tmp) / "r.db"),
                "AI_COMPANY_TRACE_DIR": str(Path(tmp) / "tr")}):
            store = TaskStore(Path(tmp) / "w.db")
            task = store.create_task("Müşteri TC 10000000146 için güvenlik incelemesi yap")
            store.assign_agents(task["task_id"], ["ceo"])
            result = process_one_task(store=store, provider=TieredProvider(None, None, cloud))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error_type"], "PrivacyRoutingError")
            cloud.generate.assert_not_called()
            self.assertEqual([i["task_id"] for i in HumanReviewQueue().list()], [task["task_id"]])
            states = [(r["from"], r["to"]) for r in read_trace(task["task_id"])]
            self.assertEqual(states, [("planned", "running"), ("running", "failed"), ("failed", "escalated")])
            self.assertEqual(verify_trace(task["task_id"]), (True, "ok"))

    def test_successful_task_is_traced_to_completed(self):
        from company.harness.state_machine import read_trace, verify_trace
        from company.worker import process_one_task
        provider = Mock(spec=["generate"])
        provider.generate.return_value = "Synthetic dry-run analysis."
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "AI_COMPANY_REVIEW_DB": str(Path(tmp) / "r.db"),
                "AI_COMPANY_TRACE_DIR": str(Path(tmp) / "tr")}):
            store = TaskStore(Path(tmp) / "w.db")
            task = store.create_task("Ağ güvenliği mimari incelemesi")
            store.assign_agents(task["task_id"], ["ceo"])
            self.assertEqual(process_one_task(store=store, provider=provider)["status"], "completed")
            self.assertEqual([r["to"] for r in read_trace(task["task_id"])], ["running", "completed"])
            self.assertTrue(verify_trace(task["task_id"])[0])
