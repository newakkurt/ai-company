import unittest
from pathlib import Path


class SampleDemoReportTests(unittest.TestCase):
    def test_demo_report_is_explicitly_fictional_and_read_only(self):
        report = (
            Path(__file__).resolve().parents[1]
            / "products"
            / "netcmd-ai-network-copilot"
            / "sample-demo-report.md"
        )
        self.assertTrue(report.is_file())
        text = report.read_text(encoding="utf-8")
        for required in (
            "Demonstration data only",
            "fictional",
            "TEST-NET-1",
            "Not assessed",
            "No secrets",
            "separate written change request",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
