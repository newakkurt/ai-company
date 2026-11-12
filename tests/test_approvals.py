import tempfile
import unittest
from pathlib import Path

from company.approvals import (
    ApprovalDeniedError,
    ApprovalRequiredError,
    action_requires_approval,
    consume_action_approval,
)
from company.store import TaskStore


class ApprovalEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "approvals.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_policy_marks_external_side_effects_as_approval_gated(self):
        self.assertFalse(action_requires_approval("read_public_docs"))
        self.assertTrue(action_requires_approval("deploy_production"))
        self.assertTrue(action_requires_approval("publish_social_post"))
        self.assertTrue(action_requires_approval("publish_product"))

    def test_protected_action_requires_matching_approval(self):
        with self.assertRaises(ApprovalRequiredError):
            consume_action_approval(self.store, "deploy_production", None, {"service": "api"})

    def test_approved_request_is_scope_bound_and_single_use(self):
        request = self.store.create_approval_request(
            "deploy_production", {"service": "api", "commit": "abc123"}, "owner_api"
        )
        decided = self.store.decide_approval_request(
            request["approval_id"], "approved", "owner_api", "Reviewed release"
        )
        self.assertEqual(decided["status"], "approved")

        consumed = consume_action_approval(
            self.store, "deploy_production", request["approval_id"],
            {"service": "api", "commit": "abc123"},
        )
        self.assertEqual(consumed["status"], "consumed")

        with self.assertRaises(ApprovalDeniedError):
            consume_action_approval(
                self.store, "deploy_production", request["approval_id"],
                {"service": "api", "commit": "abc123"},
            )

    def test_approval_cannot_be_reused_for_another_scope_or_action(self):
        request = self.store.create_approval_request(
            "deploy_production", {"service": "api"}, "owner_api"
        )
        self.store.decide_approval_request(request["approval_id"], "approved", "owner_api")
        with self.assertRaises(ApprovalDeniedError):
            consume_action_approval(
                self.store, "deploy_production", request["approval_id"], {"service": "database"}
            )

    def test_rejected_request_cannot_be_consumed(self):
        request = self.store.create_approval_request("spend_or_enable_paid_service", {}, "owner_api")
        self.store.decide_approval_request(request["approval_id"], "rejected", "owner_api", "No spend")
        with self.assertRaises(ApprovalDeniedError):
            consume_action_approval(
                self.store, "spend_or_enable_paid_service", request["approval_id"], {}
            )

    def test_unknown_action_is_blocked(self):
        with self.assertRaises(ApprovalDeniedError):
            action_requires_approval("unknown_external_action")


if __name__ == "__main__":
    unittest.main()
