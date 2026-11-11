import unittest
from unittest.mock import patch

import app


class CloudApiImportTests(unittest.TestCase):
    def test_health_endpoint_reports_thirteen_agents(self):
        result = app.healthz()
        self.assertTrue(result["ok"])
        self.assertEqual(result["agents"], 13)

    def test_provider_is_not_assumed_configured(self):
        # CI must not need an API key or a local Ollama instance.
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "AI_COMPANY_OLLAMA_URL": ""}):
            self.assertFalse(app.provider_status()["ready"])

    def test_readiness_exposes_safe_provider_and_database_state(self):
        with patch("app.database_status", return_value={
            "backend": "supabase", "connected": True, "error": None
        }), patch("app.provider_status", return_value={
            "gemini": True, "ollama": False, "model": "gemini-2.5-flash", "ready": True
        }):
            result = app.readiness()
        self.assertTrue(result["ready"])
        self.assertEqual(result["agents"], 13)
        self.assertEqual(result["database"]["backend"], "supabase")
        self.assertTrue(result["provider"]["gemini"])
        self.assertFalse(result["external_actions_enabled"])

    def test_readiness_is_not_ready_without_model(self):
        with patch("app.database_status", return_value={
            "backend": "supabase", "connected": True, "error": None
        }), patch("app.provider_status", return_value={
            "gemini": False, "ollama": False, "model": "gemini-2.5-flash", "ready": False
        }):
            result = app.readiness()
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
