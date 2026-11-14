import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from company.harness.runtime import generate_with_context


class ContextToolRuntimeTests(unittest.TestCase):
    def test_allowed_tool_runs_in_sandbox_then_model_verifies_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample.txt").write_text("VLAN 120 is configured\n", encoding="utf-8")
            provider = Mock()
            provider.generate.side_effect = [
                'TOOL_CALL_JSON: {"name":"read_file","arguments":{"path":"sample.txt"}}',
                "The file confirms VLAN 120 is configured.",
            ]
            agent = SimpleNamespace(id="content_communications")
            with patch.dict(os.environ, {
                "AI_COMPANY_WORKSPACE": str(root),
                "AI_COMPANY_REVIEW_DB": str(root / "review.db"),
            }):
                result = generate_with_context(provider, agent, "system", "Task ID: t1\nread config file")
            self.assertIn("VLAN 120", result)
            self.assertEqual(provider.generate.call_count, 2)

    def test_tool_not_selected_for_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock()
            provider.generate.return_value = (
                'TOOL_CALL_JSON: {"name":"run_bash","arguments":{"command":"echo unsafe"}}'
            )
            agent = SimpleNamespace(id="content_communications")
            with patch.dict(os.environ, {
                "AI_COMPANY_WORKSPACE": tmp,
                "AI_COMPANY_REVIEW_DB": str(Path(tmp) / "review.db"),
            }):
                result = generate_with_context(provider, agent, "system", "Task ID: t2\nread config file")
            self.assertIn("not allowed", result)
            provider.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class RiskScopeTests(unittest.TestCase):
    def test_gate_scans_task_description_not_specialist_output(self):
        from company.harness.runtime import _risk_scope
        prompt = (
            "Task ID: t-1\nTask description: Write a LinkedIn post\n"
            "Execution mode: dry_run. Analysis only.\n\nSpecialist analysis:\n[x]\niade ve hukuk"
        )
        scope = _risk_scope(prompt)
        self.assertEqual(scope, "Write a LinkedIn post")

    def test_description_that_asks_for_a_risky_action_is_still_scanned(self):
        from company.harness.escalation import classify_risk
        from company.harness.runtime import _risk_scope
        prompt = "Task ID: t-2\nTask description: Issue a refund to the customer\nExecution mode: dry_run."
        self.assertEqual(classify_risk(_risk_scope(prompt)), ["financial"])

    def test_prompt_without_description_block_is_scanned_in_full(self):
        from company.harness.runtime import _risk_scope
        self.assertEqual(_risk_scope("Tool result: chargeback"), "Tool result: chargeback")
