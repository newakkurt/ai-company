import unittest
from pathlib import Path

from audit_config import build_report, detect_vendor, evaluate


class AuditConfigTests(unittest.TestCase):
    def test_detects_cisco_and_reports_matching_evidence(self):
        config = "hostname LAB\naaa new-model\nntp server 192.0.2.1\n"
        self.assertEqual(detect_vendor(config), "cisco")
        results = evaluate(config, "auto")
        self.assertEqual(results[0]["status"], "EVIDENCED")
        self.assertEqual(results[0]["evidence_lines"], [2])

    def test_missing_evidence_is_not_claimed_as_failure(self):
        results = evaluate("hostname EMPTY\ninterface Gi1/0/1\n", "cisco")
        self.assertTrue(all(item["status"] == "NOT_EVIDENCED" for item in results))

    def test_unknown_vendor_is_explicit(self):
        results = evaluate("some unrecognized text", "auto")
        self.assertEqual(results[0]["status"], "UNKNOWN")

    def test_report_does_not_copy_secret_or_config_lines(self):
        secret = "username admin secret SUPER_SECRET_VALUE"
        report = build_report(Path("private-config.txt"), "cisco", secret)
        self.assertNotIn("SUPER_SECRET_VALUE", report)
        self.assertNotIn(secret, report)
        self.assertIn("NOT_EVIDENCED", report)

    def test_huawei_snmpv3_indicator(self):
        results = evaluate("snmp-agent usm-user v3 audituser", "huawei")
        snmp = next(item for item in results if item["control"] == "SNMPv3")
        self.assertEqual(snmp["status"], "EVIDENCED")


if __name__ == "__main__":
    unittest.main()
