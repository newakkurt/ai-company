import unittest

import app


class CloudApiImportTests(unittest.TestCase):
    def test_health_endpoint_reports_thirteen_agents(self):
        result = app.healthz()
        self.assertTrue(result["ok"])
        self.assertEqual(result["agents"], 13)

    def test_provider_is_not_assumed_configured(self):
        # CI must not need an API key or a local Ollama instance.
        self.assertIn("ready", app.provider_status())


if __name__ == "__main__":
    unittest.main()
