"""Offline, read-only network configuration baseline auditor."""
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    severity: str
    pattern: str
    remediation: str

RULES = {
"cisco": [
Rule("CIS-001","SSH v2 enabled","high",r"(?im)^\s*ip ssh version 2\s*$","Enable SSH version 2 and disable legacy remote management."),
Rule("CIS-002","AAA configured","high",r"(?im)^\s*aaa new-model\s*$","Configure AAA and validate the intended authentication method."),
Rule("CIS-003","NTP server configured","medium",r"(?im)^\s*ntp server\s+\S+","Configure at least one approved NTP server."),
Rule("CIS-004","Syslog destination configured","medium",r"(?im)^\s*logging host\s+\S+","Forward logs to an approved central syslog collector."),
Rule("CIS-005","SNMPv3 user or group configured","high",r"(?im)^\s*snmp-server\s+(?:group\s+\S+\s+v3|user\s+\S+\s+\S+\s+v3)\b","Use SNMPv3 with authentication and privacy; remove weak community strings."),
Rule("CIS-006","HTTP management disabled","high",r"(?im)^\s*no\s+ip\s+http\s+server\s*$|^\s*no\s+ip\s+http\s+secure-server\s*$","Disable plaintext HTTP management; use secured management access."),
Rule("CIS-007","BPDU Guard configured","high",r"(?im)^\s*spanning-tree\s+portfast\s+bpduguard\s+default\s*$","Enable BPDU Guard on eligible edge ports after checking topology."),
Rule("CIS-008","DHCP snooping configured","high",r"(?im)^\s*ip\s+dhcp\s+snooping\s*$","Enable DHCP snooping on intended VLANs and mark trusted uplinks carefully."),
Rule("CIS-009","Port security configured","medium",r"(?im)^\s*switchport\s+port-security\s*$","Apply port security to eligible access interfaces with a deliberate violation action."),
Rule("CIS-010","Trunk VLAN allow-list configured","medium",r"(?im)^\s*switchport\s+trunk\s+allowed\s+vlan\s+","Restrict each trunk to the VLANs it actually needs."),
],
"huawei": [
Rule("HUA-001","SSH/STelnet enabled","high",r"(?im)^\s*stelnet\s+server\s+enable\s*$","Enable secure STelnet only where required and restrict management sources."),
Rule("HUA-002","AAA local-user or domain configured","high",r"(?im)^\s*(?:local-user\s+\S+|domain\s+\S+)\b","Review AAA domains and local accounts; remove unused privileged accounts."),
Rule("HUA-003","NTP server configured","medium",r"(?im)^\s*ntp-service\s+unicast-server\s+\S+","Configure an approved NTP unicast server."),
Rule("HUA-004","Log host configured","medium",r"(?im)^\s*info-center\s+loghost\s+\S+","Forward logs to an approved central log host."),
Rule("HUA-005","SNMPv3 user configured","high",r"(?im)^\s*snmp-agent\s+usm-user\s+v3\s+\S+","Use SNMPv3 authentication and privacy; remove legacy communities."),
Rule("HUA-006","HTTP management disabled","high",r"(?im)^\s*undo\s+http\s+server\s+enable\s*$","Disable the HTTP server; retain only approved secure management."),
Rule("HUA-007","STP BPDU protection configured","high",r"(?im)^\s*stp\s+bpdu-protection\s+enable\s*$","Enable BPDU protection on edge ports after validating topology."),
Rule("HUA-008","DHCP snooping configured","high",r"(?im)^\s*dhcp\s+snooping\s+enable\s*$","Enable DHCP snooping on intended VLANs and trust only uplinks."),
Rule("HUA-009","Port security configured","medium",r"(?im)^\s*port-security\s+enable\s*$","Apply port security on eligible access interfaces."),
Rule("HUA-010","Trunk VLAN allow-list configured","medium",r"(?im)^\s*port\s+trunk\s+allow-pass\s+vlan\s+","Restrict trunk VLANs to the required set."),
],
"aruba": [
Rule("ARB-001","SSH enabled","high",r"(?im)^\s*ip\s+ssh\s*$","Enable SSH and restrict management access; disable insecure management."),
Rule("ARB-002","AAA authentication configured","high",r"(?im)^\s*(?:aaa\s+authentication|radius-server\s+host|tacacs-server\s+host)\b","Configure and validate the intended AAA/RADIUS/TACACS authentication path."),
Rule("ARB-003","NTP server configured","medium",r"(?im)^\s*sntp\s+unicast\s+\S+","Configure an approved SNTP server."),
Rule("ARB-004","Syslog server configured","medium",r"(?im)^\s*logging\s+\S+","Forward logs to an approved central syslog collector."),
Rule("ARB-005","SNMPv3 configured","high",r"(?im)^\s*snmpv3\s+(?:user|group)\s+\S+","Use SNMPv3 with authentication and privacy."),
Rule("ARB-006","Plaintext web management disabled","high",r"(?im)^\s*no\s+web-management\s*$","Disable plaintext web management; use approved secure management."),
Rule("ARB-007","BPDU protection configured","high",r"(?im)^\s*spanning-tree\s+bpdu-protection\s*$","Enable BPDU protection on eligible edge ports."),
Rule("ARB-008","DHCP snooping configured","high",r"(?im)^\s*dhcp-snooping\s*$","Enable DHCP snooping and trust only intended uplinks."),
Rule("ARB-009","Port security configured","medium",r"(?im)^\s*port-security\s*$","Apply port security to eligible access interfaces."),
Rule("ARB-010","Trunk VLAN allow-list configured","medium",r"(?im)^\s*(?:tagged|trunk)\s+\S+","Review tagged VLAN membership and remove unnecessary VLANs."),
]}

def detect_vendor(config: str) -> str:
    text=config.lower()
    if any(x in text for x in ("stelnet server","snmp-agent","port trunk allow-pass","info-center")): return "huawei"
    if any(x in text for x in ("switchport","aaa new-model","ip ssh version","spanning-tree portfast")): return "cisco"
    if any(x in text for x in ("snmpv3 user","no web-management","sntp unicast")): return "aruba"
    raise ValueError("Vendor could not be detected safely; specify --vendor explicitly.")

def audit(config: str, vendor: str="auto") -> dict:
    selected=detect_vendor(config) if vendor=="auto" else vendor.lower()
    if selected not in RULES: raise ValueError(f"Unsupported vendor: {selected}")
    checks=[]
    for rule in RULES[selected]:
        passed=re.search(rule.pattern,config) is not None
        checks.append({"id":rule.rule_id,"title":rule.title,"severity":rule.severity,"status":"pass" if passed else "review","remediation":"Configured marker found in the supplied text." if passed else rule.remediation})
    passed=sum(x["status"]=="pass" for x in checks)
    return {"product":"NetCmd ConfigGuard Lite","version":"1.0.0","vendor":selected,"mode":"offline_read_only_config_text","summary":{"checks":len(checks),"passed":passed,"review":len(checks)-passed},"checks":checks,"limitations":["This audits only the supplied configuration text; it does not connect to a device.","A matching command is not proof that the feature is active or correctly scoped.","Validate platform release, interface context, topology and operational state before changes."]}

def render_markdown(report: dict) -> str:
    lines=[f"# {report['product']} — Audit Report","",f"- Version: {report['version']}",f"- Vendor: {report['vendor']}",f"- Mode: {report['mode']}",f"- Checks: {report['summary']['checks']} | Pass: {report['summary']['passed']} | Review: {report['summary']['review']}","","| ID | Check | Severity | Result |","|---|---|---|---|"]
    lines += [f"| {x['id']} | {x['title']} | {x['severity']} | {x['status'].upper()} |" for x in report['checks']]
    lines += ["","## Remediation"]+[f"- **{x['id']} — {x['title']}:** {x['remediation']}" for x in report['checks'] if x['status']=="review"]+["","## Limitations"]+[f"- {x}" for x in report['limitations']]
    return "\n".join(lines)+"\n"

def main(argv: Iterable[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Offline read-only Cisco/Huawei/Aruba config baseline auditor")
    parser.add_argument("config"); parser.add_argument("--vendor",choices=["auto","cisco","huawei","aruba"],default="auto"); parser.add_argument("--format",choices=["markdown","json"],default="markdown"); parser.add_argument("--output")
    args=parser.parse_args(argv)
    try:
        report=audit(Path(args.config).read_text(encoding="utf-8",errors="replace"),args.vendor)
        output=json.dumps(report,ensure_ascii=False,indent=2) if args.format=="json" else render_markdown(report)
        if args.output: Path(args.output).write_text(output,encoding="utf-8")
        else: print(output,end="")
        return 0
    except (OSError,ValueError) as exc:
        print(f"error: {exc}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
