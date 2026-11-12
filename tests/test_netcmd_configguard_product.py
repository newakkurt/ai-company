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
    def test_evidence_and_credential_redaction(self):
        report=audit("hostname EDGE\nsnmp-server community TOP_SECRET ro\n","cisco")
        risk=next(x for x in report["risks"] if x["id"]=="CIS-R02")
        self.assertEqual(risk["evidence"],["snmp-server community [REDACTED] ro"])
        self.assertNotIn("TOP_SECRET",render_markdown(report))
    def test_huawei_community_secret_redaction(self):
        report=audit("snmp-agent community read cipher HUAWEI_SECRET","huawei")
        risk=next(x for x in report["risks"] if x["id"]=="HUA-R02")
        self.assertEqual(risk["evidence"],["snmp-agent community read cipher [REDACTED]"])
    def test_telnet_warning_and_html_escape(self):
        report=audit("line vty 0 4\n transport input telnet ssh <script>alert(1)</script>\n","cisco")
        self.assertTrue(any(x["id"]=="CIS-R01" for x in report["risks"]))
        from netcmd_configguard.audit import render_html
        html=render_html(report)
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>",html)
    def test_aruba_sample_fixture(self):
        fixture=Path(__file__).resolve().parents[1]/"products"/"netcmd-configguard-lite"/"examples"/"aruba-sample.cfg"
        report=audit(fixture.read_text(encoding="utf-8"),"aruba")
        self.assertEqual(report["vendor"],"aruba")
        self.assertEqual(report["summary"]["passed"],9)

if __name__=="__main__": unittest.main()
