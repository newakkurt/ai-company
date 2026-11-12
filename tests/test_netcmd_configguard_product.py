import sys
import unittest
from pathlib import Path

PRODUCT_SRC = Path(__file__).resolve().parents[1] / "products" / "netcmd-configguard-lite" / "src"
sys.path.insert(0, str(PRODUCT_SRC))
from netcmd_configguard import audit, detect_vendor, render_markdown

class ConfigGuardProductTests(unittest.TestCase):
    def test_huawei_markers(self):
        cfg="stelnet server enable\nntp-service unicast-server 192.0.2.10\nsnmp-agent usm-user v3 monitor\nundo http server enable\n"
        report=audit(cfg)
        self.assertEqual(report["vendor"],"huawei")
        self.assertEqual(report["summary"]["passed"],4)
    def test_cisco_markers(self):
        cfg="hostname EDGE\nip ssh version 2\naaa new-model\nno ip http server\n"
        self.assertEqual(detect_vendor(cfg),"cisco")
        self.assertEqual(audit(cfg)["summary"]["passed"],3)
    def test_aruba_and_report(self):
        report=audit("ip ssh\nno web-management\n","aruba")
        self.assertEqual(report["summary"]["passed"],2)
        self.assertIn("ARB-001",render_markdown(report))
    def test_ambiguous_input_fails_closed(self):
        with self.assertRaises(ValueError): audit("hostname SWITCH-01")
    def test_unknown_vendor_fails(self):
        with self.assertRaises(ValueError): audit("x","juniper")

if __name__=="__main__": unittest.main()
