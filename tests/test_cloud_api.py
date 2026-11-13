import unittest
from unittest.mock import patch

import app


class CloudApiImportTests(unittest.TestCase):
    def test_health_endpoint_reports_fourteen_agents(self):
        result = app.healthz()
        self.assertTrue(result["ok"])
        self.assertEqual(result["agents"], 14)

    def test_provider_is_not_assumed_configured(self):
        # CI must not need an API key or a local Ollama instance.
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "AI_COMPANY_OLLAMA_URL": ""}):
            self.assertFalse(app.provider_status()["ready"])

    def test_readiness_exposes_safe_provider_and_database_state(self):
        with patch("app.database_status", return_value={
            "backend": "supabase", "connected": True, "error": None
        }), patch("app.provider_status", return_value={
            "gemini": True, "ollama": False, "model": "gemini-2.5-flash", "ready": True
        }), patch("app.worker_status", return_value={
            "enabled": True, "running": True, "mode": "embedded_supabase_poll", "poll_seconds": 15
        }):
            result = app.readiness()
        self.assertTrue(result["ready"])
        self.assertEqual(result["agents"], 14)
        self.assertEqual(result["database"]["backend"], "supabase")
        self.assertTrue(result["provider"]["gemini"])
        self.assertFalse(result["external_actions_enabled"])
        self.assertTrue(result["worker"]["running"])
        self.assertIn("bmc_webhook_configured", result["commerce"])
        self.assertIn("smtp_configured", result["commerce"])

    def test_readiness_is_not_ready_when_worker_enabled_but_stopped(self):
        with patch("app.database_status", return_value={
            "backend": "supabase", "connected": True, "error": None
        }), patch("app.provider_status", return_value={
            "gemini": True, "ollama": False, "model": "gemini-3.8-flash", "ready": True
        }), patch("app.worker_status", return_value={
            "enabled": True, "running": False, "mode": "embedded_supabase_poll", "poll_seconds": 15
        }):
            result = app.readiness()
        self.assertFalse(result["ready"])

    def test_readiness_is_not_ready_without_model(self):
        with patch("app.database_status", return_value={
            "backend": "supabase", "connected": True, "error": None
        }), patch("app.provider_status", return_value={
            "gemini": False, "ollama": False, "model": "gemini-2.5-flash", "ready": False
        }), patch("app.worker_status", return_value={
            "enabled": True, "running": True, "mode": "embedded_supabase_poll", "poll_seconds": 15
        }):
            result = app.readiness()
        self.assertFalse(result["ready"])




class CommerceStatusTests(unittest.TestCase):
    def test_commerce_status_reports_presence_without_values(self):
        with patch.dict("os.environ", {
            "BMC_WEBHOOK_SECRET": "secret-value",
            "BMC_EXTRA_PRODUCT_MAP": "{\"shop-id\":\"product\"}",
            "MAIL_SMTP_HOST": "smtp.example",
            "MAIL_USER": "owner@example.com",
            "MAIL_PASSWORD": "mail-secret",
            "MAIL_FROM": "owner@example.com",
            "AI_COMPANY_MAIL_MODE": "draft",
        }, clear=True):
            status = app.commerce_status()
        self.assertTrue(status["bmc_webhook_configured"])
        self.assertTrue(status["bmc_shop_mapping_configured"])
        self.assertTrue(status["smtp_configured"])
        self.assertEqual(status["mail_mode"], "draft")
        self.assertNotIn("secret-value", repr(status))
        self.assertNotIn("mail-secret", repr(status))

if __name__ == "__main__":
    unittest.main()
