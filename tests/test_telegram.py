import tempfile
import unittest
from pathlib import Path
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
