import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from company.worker import notify_due_followups

class FakeStore:
    def __init__(self):
        self.patched=[]
    def _request(self, table, method="GET", params=None, body=None, prefer=None):
        if method=="GET":
            return [{"followup_id":"fu-1","company_id":"co-1","note":"Check proposal","last_notified_at":None}]
        if method=="PATCH":
            self.patched.append((table,params,body))
            return []
        return []

class FollowupReminderTests(unittest.TestCase):
    def test_due_followup_notifies_owner_and_marks_timestamp(self):
        store=FakeStore()
        now=datetime(2026,11,12,9,0,tzinfo=timezone.utc)
        with patch("company.worker.notify_owner",return_value=True) as notify:
            count=notify_due_followups(store=store,now=now)
        self.assertEqual(count,1)
        notify.assert_called_once()
        self.assertIn("Check proposal",notify.call_args.args[0])
        self.assertEqual(store.patched[0][2]["last_notified_at"],now.isoformat())

    def test_failed_notification_is_not_marked(self):
        store=FakeStore()
        with patch("company.worker.notify_owner",return_value=False):
            count=notify_due_followups(store=store)
        self.assertEqual(count,0)
        self.assertEqual(store.patched,[])

if __name__=="__main__":
    unittest.main()
