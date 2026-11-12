import unittest
from pathlib import Path
from company.network_audit import audit_config, detect_vendor, redact_evidence

class NetworkAuditTests(unittest.TestCase):
    def test_huawei_fixture_and_physical_interface_filter(self):
        config="""sysname EDGE-HW-01
interface GigabitEthernet0/0/1
 port link-type access
 undo shutdown
quit
interface Vlanif10
 ip address 192.0.2.1 255.255.255.0
quit
"""
        result=audit_config(config)
        self.assertEqual(detect_vendor(config),"huawei")
        self.assertEqual(result.vendor,"huawei")
        ids={x.check_id for x in result.findings}
        self.assertTrue({"management.ntp","management.logging","management.aaa","interfaces.missing_description"} <= ids)
        evidence=next(x for x in result.findings if x.check_id=="interfaces.missing_description").evidence
        self.assertIn("interface GigabitEthernet0/0/1",evidence)
        self.assertNotIn("Vlanif10"," ".join(evidence))
        self.assertEqual(result.to_dict()["mode"],"read_only_text_analysis")

    def test_cisco_telnet_evidence(self):
        config="""hostname EDGE-CS-01
interface GigabitEthernet1/0/1
 switchport mode access
 no shutdown
!
line vty 0 4
 transport input telnet ssh
!
"""
        result=audit_config(config)
        self.assertEqual(result.vendor,"cisco")
        finding=next(x for x in result.findings if x.check_id=="management.telnet")
        self.assertTrue(any("transport input" in line for line in finding.evidence))

    def test_disabled_telnet_is_not_flagged(self):
        config="""sysname EDGE-HW-02
undo telnet server enable
interface GigabitEthernet0/0/1
 undo shutdown
quit
"""
        self.assertNotIn("management.telnet",{x.check_id for x in audit_config(config).findings})

    def test_aruba_detection_and_interface_parsing(self):
        config="""; ArubaOS-CX
hostname EDGE-ARUBA-01
vlan 10
 name USERS
interface 1/1/1
 description User access
 vlan access 10
 spanning-tree bpdu-protection
interface 1/1/2
 vlan access 10
"""
        result=audit_config(config)
        self.assertEqual(result.vendor,"aruba")
        evidence=next(x for x in result.findings if x.check_id=="interfaces.missing_description").evidence
        self.assertIn("interface 1/1/2",evidence)
        self.assertNotIn("interface 1/1/1",evidence)

    def test_secret_values_are_redacted(self):
        config="""hostname EDGE-CS-02
snmp-server community SUPER_SECRET ro
username admin secret 5 HASHED_PASSWORD
line vty 0 4
 transport input ssh
!
"""
        result=audit_config(config)
        output=result.render_markdown()+result.render_html()+str(result.to_dict())
        self.assertNotIn("SUPER_SECRET",output)
        self.assertNotIn("HASHED_PASSWORD",output)
        self.assertIn("[REDACTED]",output)
        self.assertIn("snmp-server community",output)

    def test_controls_are_recognized(self):
        config="""hostname EDGE-CS-03
ip ssh version 2
ntp server 192.0.2.10
logging host 192.0.2.20
aaa new-model
ip dhcp snooping
interface GigabitEthernet1/0/1
 switchport port-security
 spanning-tree bpduguard enable
 description uplink
!
"""
        ids={x.check_id for x in audit_config(config).findings}
        self.assertTrue({"management.ntp","management.logging","management.aaa","management.ssh",
                         "security.port_security","security.bpdu_protection","security.dhcp_snooping"}.isdisjoint(ids))

    def test_renderers_are_deterministic_and_escape_html(self):
        result=audit_config('hostname EDGE-CS-99\nline vty 0 4\n transport input telnet ssh <script>alert("x")</script>\n!')
        self.assertEqual(result.render_markdown(),result.render_markdown())
        self.assertIn("&lt;script&gt;",result.render_html())
        self.assertNotIn("<script>",result.render_html())

    def test_unknown_vendor_is_explicit(self):
        result=audit_config("unrecognized config")
        self.assertEqual(result.vendor,"unknown")
        self.assertTrue(any("Vendor could not be identified" in x for x in result.notes))

    def test_sanitized_fixtures_are_parseable(self):
        fixture_dir=Path("fixtures/network_audit")
        expected={"cisco_sample.cfg":"cisco","huawei_sample.cfg":"huawei","aruba_sample.cfg":"aruba"}
        for filename,vendor in expected.items():
            result=audit_config((fixture_dir/filename).read_text(encoding="utf-8"))
            self.assertEqual(result.vendor,vendor,filename)
            self.assertTrue(result.findings,filename)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError): audit_config(" ")
        with self.assertRaises(ValueError): audit_config("hostname X","juniper")

    def test_redaction_helper(self):
        self.assertEqual(redact_evidence("snmp-server community my-secret ro"),
                         "snmp-server community [REDACTED] ro")
        self.assertEqual(redact_evidence("snmp-agent community read cipher my-huawei-secret"),
                         "snmp-agent community read cipher [REDACTED]")

if __name__=="__main__":
    unittest.main()
