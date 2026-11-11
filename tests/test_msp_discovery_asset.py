from pathlib import Path
import unittest


class MspDiscoveryAssetTests(unittest.TestCase):
    def test_prospect_pack_has_sources_and_uncontacted_status(self):
        path = Path(__file__).parents[1] / "sales" / "msp-discovery-qualification-pack.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn("These are uncontacted prospects", content)
        self.assertGreaterEqual(content.count("https://"), 5)
        self.assertIn("IT Spine", content)
        self.assertIn("Sivana Bilişim", content)
        self.assertIn("NETSUN Bilişim", content)
        self.assertIn("N Destek", content)
        self.assertIn("NetWorker", content)

    def test_sales_guardrails_are_explicit(self):
        path = Path(__file__).parents[1] / "sales" / "msp-discovery-qualification-pack.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn("not an active subscription", content)
        self.assertIn("No device access", content)
        self.assertIn("not sent automatically", content)
        self.assertIn("Human review", content)


if __name__ == "__main__":
    unittest.main()
