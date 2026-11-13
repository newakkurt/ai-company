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
