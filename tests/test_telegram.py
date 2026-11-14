import tempfile
import unittest
from pathlib import Path
import unittest.mock
from unittest.mock import Mock

from company.store import TaskStore
from company.telegram import TelegramIntake

class TelegramIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "telegram.db")
        self.bot = TelegramIntake(token="test-token", allowed_chat_ids=["12345"], store=self.store)
        self.bot.send_message = Mock()

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_unapproved_chat(self):
        handled = self.bot.handle_update({
            "message": {"chat": {"id": 999}, "text": "/task do something"}
        })
        self.assertFalse(handled)
        self.assertEqual(self.store.list_tasks(), [])
        self.bot.send_message.assert_not_called()

    def test_task_command_creates_dry_run_task(self):
        handled = self.bot.handle_update({
            "message": {"chat": {"id": 12345}, "text": "/task Review the NetCmd roadmap"}
        })
        self.assertTrue(handled)
        tasks = self.store.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["description"], "Review the NetCmd roadmap")
        self.assertEqual(tasks[0]["execution_mode"], "dry_run")
        self.bot.send_message.assert_called_once()

    def test_empty_task_does_not_create_record(self):
        self.bot.handle_update({
            "message": {"chat": {"id": 12345}, "text": "/task   "}
        })
        self.assertEqual(self.store.list_tasks(), [])
        self.bot.send_message.assert_called_once()

    def test_pending_chat_id_discovery_returns_ids_only(self):
        self.bot._api = Mock(return_value=[
            {"update_id": 1, "message": {"chat": {"id": 12345}, "text": "/start"}},
            {"update_id": 2, "message": {"chat": {"id": 12345}, "text": "hello"}},
            {"update_id": 3, "message": {"chat": {"id": -555}, "text": "group"}}
        ])
        self.assertEqual(self.bot.pending_chat_ids(), ["-555", "12345"])

    def test_missing_allowlist_is_rejected(self):
        with self.assertRaises(ValueError):
            TelegramIntake(token="test-token", allowed_chat_ids=[], store=self.store)

if __name__ == "__main__":
    unittest.main()


class TelegramApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "approvals.db")
        self.bot = TelegramIntake(token="t", allowed_chat_ids=["12345"], store=self.store)
        self.bot.send_message = Mock()
        self.bot._api = Mock(return_value={})
        self.item = self.store.create_approval_request(
            "publish_product", {"product_id": "prd-1", "sha256": "ab" * 32}, "factory")

    def tearDown(self):
        self.tmp.cleanup()

    def cb(self, code, sender=12345, chat=12345, approval_id=None):
        return {"callback_query": {"id": "cb1", "from": {"id": sender}, "message": {"chat": {"id": chat}},
                                   "data": f"apv:{code}:{approval_id or self.item['approval_id']}"}}

    def test_one_tap_approve_records_decision_and_is_still_consumable_once(self):
        self.assertTrue(self.bot.handle_update(self.cb("ok")))
        self.assertEqual(self.store.get_approval_request(self.item["approval_id"])["status"], "approved")
        scope = {"product_id": "prd-1", "sha256": "ab" * 32}
        self.store.consume_approval_request(self.item["approval_id"], "publish_product", scope)
        with self.assertRaises(ValueError):
            self.store.consume_approval_request(self.item["approval_id"], "publish_product", scope)

    def test_reject_and_double_tap(self):
        self.bot.handle_update(self.cb("no"))
        self.assertEqual(self.store.get_approval_request(self.item["approval_id"])["status"], "rejected")
        self.bot.handle_update(self.cb("ok"))  # second tap must not flip the decision
        self.assertEqual(self.store.get_approval_request(self.item["approval_id"])["status"], "rejected")

    def test_unauthorized_sender_or_chat_is_ignored(self):
        self.assertFalse(self.bot.handle_update(self.cb("ok", sender=999)))
        self.assertFalse(self.bot.handle_update(self.cb("ok", chat=999)))
        self.assertEqual(self.store.get_approval_request(self.item["approval_id"])["status"], "pending")

    def test_malformed_callback_data_changes_nothing(self):
        for data in ("apv:ok:not-an-approval", "x:ok:approval-1", "apv:maybe:approval-1"):
            update = {"callback_query": {"id": "c", "from": {"id": 12345},
                                         "message": {"chat": {"id": 12345}}, "data": data}}
            self.bot.handle_update(update)
        self.assertEqual(self.store.get_approval_request(self.item["approval_id"])["status"], "pending")

    def test_approvals_command_lists_pending_with_buttons(self):
        self.bot.handle_update({"message": {"chat": {"id": 12345}, "text": "/approvals"}})
        payload = self.bot._api.call_args.args[1]
        self.assertIn("reply_markup", payload)
        self.assertIn(self.item["approval_id"], payload["reply_markup"])

    def test_notify_message_has_buttons_and_redacts_scope(self):
        from company.notifier import notify_approval_request
        sent = []
        with unittest.mock.patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_OWNER_CHAT_ID": "12345"}):
            ok = notify_approval_request(
                {**self.item, "scope_json": {"note": "ali@example.com"}},
                sender=lambda token, chat, text, markup=None: sent.append((text, markup)) or True)
        self.assertTrue(ok)
        text, markup = sent[0]
        self.assertNotIn("ali@example.com", text)
        self.assertEqual(len(markup["inline_keyboard"][0]), 2)


class TelegramOwnerDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.tmp.name) / "dashboard.db")
        self.bot = TelegramIntake(token="test-token", allowed_chat_ids=["12345"], store=self.store)
        self.bot.send_message = Mock()

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, command):
        return self.bot.handle_update({
            "message": {"chat": {"id": 12345}, "text": command}
        })

    def test_status_reports_configuration_without_secrets(self):
        with unittest.mock.patch.dict("os.environ", {
            "GEMINI_API_KEY": "do-not-disclose",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "anon-secret",
            "SUPABASE_DB_GATE_KEY": "gate-secret",
            "AI_COMPANY_EMBEDDED_WORKER": "false",
            "AI_COMPANY_EMBEDDED_TELEGRAM": "true",
        }, clear=True):
            self.send("/status")
        message = self.bot.send_message.call_args.args[1]
        self.assertIn("AI anahtarı: var", message)
        self.assertIn("Supabase ayarları: tam", message)
        self.assertNotIn("do-not-disclose", message)
        self.assertNotIn("anon-secret", message)
        self.assertNotIn("gate-secret", message)

    def test_agents_command_lists_registered_roles(self):
        self.send("/agents")
        message = self.bot.send_message.call_args.args[1]
        self.assertIn("Uzman ajanlar (14)", message)
        self.assertIn("ceo", message)

    def test_tasks_command_shows_recent_task_without_sensitive_fields(self):
        self.store.create_task("Review the network automation roadmap")
        self.send("/tasks")
        message = self.bot.send_message.call_args.args[1]
        self.assertIn("Review the network automation roadmap", message)
        self.assertNotIn("test-token", message)

    def test_report_counts_tasks_and_disclaims_revenue(self):
        self.store.create_task("Review the network automation roadmap")
        self.send("/report")
        message = self.bot.send_message.call_args.args[1]
        self.assertIn("Görev özeti", message)
        self.assertIn("planned: 1", message)
        self.assertIn("gelir veya satış doğrulaması değildir", message)

    def test_new_help_lists_owner_commands(self):
        self.send("/help")
        message = self.bot.send_message.call_args.args[1]
        for command in ("/status", "/agents", "/tasks", "/report", "/approvals"):
            self.assertIn(command, message)
