import unittest

from company.network_audit import audit_config, detect_vendor


class NetworkAuditTests(unittest.TestCase):
    def test_detect_huawei_and_flag_missing_controls(self):
        config = """sysname EDGE-01
interface GigabitEthernet0/0/1
 port link-type access
 undo shutdown
quit
"""
        self.assertEqual(detect_vendor(config), "huawei")
        result = audit_config(config)
        self.assertEqual(result.vendor, "huawei")
        ids = {item.check_id for item in result.findings}
        self.assertIn("management.ntp", ids)
        self.assertIn("management.logging", ids)
        self.assertIn("management.aaa", ids)
        self.assertIn("interfaces.missing_description", ids)
        self.assertEqual(result.to_dict()["mode"], "read_only_text_analysis")

    def test_cisco_telnet_evidence_is_preserved(self):
        config = """hostname EDGE-02
interface GigabitEthernet1/0/1
 switchport mode access
 no shutdown
!
line vty 0 4
 transport input telnet ssh
"""
        result = audit_config(config)
        self.assertEqual(result.vendor, "cisco")
        finding = next(item for item in result.findings if item.check_id == "management.telnet")
        self.assertTrue(any("transport input" in line for line in finding.evidence))

    def test_empty_config_rejected(self):
        with self.assertRaises(ValueError):
            audit_config("   ")


if __name__ == "__main__":
    unittest.main()
