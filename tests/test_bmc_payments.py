import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path

from app import _verify_bmc_signature
from company.store import TaskStore


class BmcPaymentStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "payments.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_signature_verification_uses_raw_body_hmac(self):
        body = b'{"event_id":123,"type":"membership.started"}'
        secret = "test-secret"
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(_verify_bmc_signature(body, secret, signature))
        self.assertFalse(_verify_bmc_signature(body, secret, "0" * 64))
        self.assertFalse(_verify_bmc_signature(body, "", signature))

    def test_paid_membership_task_creation_is_idempotent(self):
        task_id = "bmc-sub-12345"
        first = self.store.create_task("Paid NetCmd PRO onboarding", task_id=task_id)
        second = self.store.create_task("Paid NetCmd PRO onboarding", task_id=task_id)
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_payment_event_deduplication_and_membership_upsert(self):
        self.store.record_payment_event("bmc-777", "membership.started", "777")
        self.store.record_payment_event("bmc-777", "membership.started", "777")
        self.assertIsNotNone(self.store.get_payment_event("bmc-777"))
        item = {
            "subscription_id": "777", "supporter_email": "buyer@example.com",
            "supporter_name": "Buyer", "membership_level_id": 99,
            "membership_level_name": "NetCmd PRO", "amount": 69.0,
            "currency": "USD", "status": "active", "current_period_end": None,
            "task_id": "bmc-sub-777", "updated_at": "2026-11-11T00:00:00+00:00",
        }
        self.store.upsert_membership(item)
        updated = {**item, "status": "canceled"}
        self.store.upsert_membership(updated)
        self.assertEqual(self.store.get_membership("777")["status"], "canceled")


if __name__ == "__main__":
    unittest.main()
