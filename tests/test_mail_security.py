import tempfile
import unittest
from pathlib import Path

from company.mailbox import MailConfig, authentication_passed
from company.store import TaskStore


class MailSecurityTests(unittest.TestCase):
    def test_auto_reply_requires_trusted_dmarc_and_spf_or_dkim(self):
        cfg = MailConfig(trusted_auth_servers=("mx.google.com",))
        good = {"authentication_results": [
            "mx.google.com; dkim=pass header.d=example.com; spf=pass; dmarc=pass"
        ]}
        self.assertTrue(authentication_passed(good, cfg))
        self.assertFalse(authentication_passed({
            "authentication_results": [
                "evil.test; dkim=pass; spf=pass; dmarc=pass",
                "mx.google.com; dkim=pass; spf=pass; dmarc=pass",
            ]
        }, cfg))
        self.assertFalse(authentication_passed({
            "authentication_results": ["mx.google.com; dkim=pass; spf=pass; dmarc=fail"]
        }, cfg))
        self.assertFalse(authentication_passed({"authentication_results": []}, cfg))

    def test_mail_send_reservations_survive_store_restarts_and_enforce_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mail.db"
            first = TaskStore(path)
            self.assertTrue(first.reserve_mail_send("msg-1", "a@example.com", 2, 1))
            self.assertFalse(first.reserve_mail_send("msg-1", "a@example.com", 2, 1))
            second = TaskStore(path)
            self.assertFalse(second.reserve_mail_send("msg-2", "a@example.com", 2, 1))
            self.assertTrue(second.reserve_mail_send("msg-3", "b@example.com", 2, 1))
            second.update_mail_send("msg-3", "sent")
            self.assertFalse(second.reserve_mail_send("msg-4", "c@example.com", 2, 1))

    def test_failed_send_is_not_resent_for_the_same_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TaskStore(Path(tmp) / "mail.db")
            self.assertTrue(store.reserve_mail_send("msg-fail", "a@example.com", 5, 2))
            store.update_mail_send("msg-fail", "failed", "SMTPError")
            self.assertFalse(store.reserve_mail_send("msg-fail", "a@example.com", 5, 2))


if __name__ == "__main__":
    unittest.main()
