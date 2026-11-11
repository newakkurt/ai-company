import unittest
from pathlib import Path


class CustomerEvidenceGuideTests(unittest.TestCase):
    def test_customer_evidence_guide_contains_safety_boundaries(self):
        guide = (
            Path(__file__).resolve().parents[1]
            / "products"
            / "netcmd-ai-network-copilot"
            / "customer-evidence-handling.md"
        )
        self.assertTrue(guide.is_file(), "Customer evidence guide must ship with the product pack")
        text = guide.read_text(encoding="utf-8")
        for required in (
            "Minimum evidence set",
            "Never collect passwords",
            "public GitHub repositories",
            "No approval means no change.",
            "Not verified",
            "Customer handover checklist",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
