import unittest
from datetime import datetime, timedelta, timezone

from company.harness.escalation import HumanReviewQueue


class FakeApprovalStore:
    def __init__(self):
        self.rows = []

    def _request(self, table, method="GET", params=None, body=None, prefer=None):
        assert table == "approval_requests"
        params = params or {}
        if method == "POST":
            self.rows.append(dict(body))
            return []
        if method == "PATCH":
            matched = []
            for row in self.rows:
                if row["approval_id"] == params.get("approval_id", "").removeprefix("eq.") \
                        and row["action"] == "human_review" and row["status"] == "pending":
                    row.update(body)
                    matched.append(dict(row))
            return matched
        rows = [
            row for row in self.rows
            if row["action"] == "human_review"
            and (params.get("status") is None or row["status"] == params["status"].removeprefix("eq."))
            and (params.get("approval_id") is None or row["approval_id"] == params["approval_id"].removeprefix("eq."))
        ]
        return rows[:int(params.get("limit", "100"))]


class HostedReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeApprovalStore()
        self.queue = HumanReviewQueue(store=self.store)

    def test_hosted_queue_is_durable_idempotent_and_redacted(self):
        first = self.queue.enqueue("task-1", "retry_budget_exhausted", {"email": "owner@example.com"}, ["runtime"], 3)
        second = self.queue.enqueue("task-1", "retry_budget_exhausted", {"email": "owner@example.com"}, ["runtime"], 3)
        self.assertEqual(first, second)
        pending = self.queue.list()
        self.assertEqual(len(pending), 1)
        self.assertNotIn("owner@example.com", pending[0]["payload"])
        self.assertEqual(pending[0]["attempts"], 3)

    def test_hosted_decision_is_single_use(self):
        review_id = self.queue.enqueue("task-2", "human_required", {"note": "check"})
        decided = self.queue.decide(review_id, "approved", "owner", "reviewed")
        self.assertEqual(decided["status"], "approved")
        self.assertEqual(self.queue.list(), [])
        with self.assertRaises(KeyError):
            self.queue.decide(review_id, "rejected", "owner")


if __name__ == "__main__":
    unittest.main()
