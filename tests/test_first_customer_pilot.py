import unittest
from pathlib import Path


class FirstCustomerPilotTests(unittest.TestCase):
    def test_pilot_scope_and_commercial_guardrails(self):
        offer = (
            Path(__file__).resolve().parents[1]
            / "products"
            / "netcmd-ai-network-copilot"
            / "first-customer-pilot.md"
        )
        self.assertTrue(offer.is_file())
        text = offer.read_text(encoding="utf-8")
        for required in (
            "One customer site.",
            "Up to 10 network devices",
            "No direct device connection",
            "Three business days",
            "Secrets removed",
            "not a live checkout",
            "USD 69/month",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
