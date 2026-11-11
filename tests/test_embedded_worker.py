import os
import threading
import unittest
from unittest.mock import patch

import app


class EmbeddedWorkerTests(unittest.TestCase):
    def tearDown(self):
        app.stop_embedded_worker()

    def test_embedded_worker_starts_with_existing_service_secrets(self):
        started = threading.Event()

        def fake_loop(stop_event, poll_seconds):
            started.set()
            stop_event.wait(3)

        env = {
            "AI_COMPANY_EMBEDDED_WORKER": "true",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "test-anon",
            "SUPABASE_DB_GATE_KEY": "test-gate",
            "GEMINI_API_KEY": "test-gemini",
        }
        with patch.dict(os.environ, env), patch("app.run_forever", side_effect=fake_loop):
            app.start_embedded_worker()
            self.assertTrue(started.wait(1))
            status = app.worker_status()
            self.assertTrue(status["enabled"])
            self.assertTrue(status["running"])
            self.assertEqual(status["mode"], "embedded_supabase_poll")
            app.stop_embedded_worker()
            self.assertFalse(app.worker_status()["running"])

    def test_worker_does_not_start_when_disabled(self):
        with patch.dict(os.environ, {"AI_COMPANY_EMBEDDED_WORKER": "false"}):
            app.start_embedded_worker()
            self.assertFalse(app.worker_status()["enabled"])
            self.assertFalse(app.worker_status()["running"])

    def test_worker_does_not_start_without_required_secrets(self):
        env = {
            "AI_COMPANY_EMBEDDED_WORKER": "true",
            "SUPABASE_URL": "",
            "SUPABASE_ANON_KEY": "",
            "SUPABASE_DB_GATE_KEY": "",
            "GEMINI_API_KEY": "",
        }
        with patch.dict(os.environ, env):
            app.start_embedded_worker()
            self.assertTrue(app.worker_status()["enabled"])
            self.assertFalse(app.worker_status()["running"])


if __name__ == "__main__":
    unittest.main()
