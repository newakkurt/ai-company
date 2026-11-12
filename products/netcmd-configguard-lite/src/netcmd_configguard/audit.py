"""Offline, read-only multi-vendor network configuration baseline auditor."""
from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass
from html import escape
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
Rule("CIS-001","SSH v2 enabled","high",r"(?im)^\s*ip ssh version 2\s*$","Enable SSH version 2 and restrict management sources."),
Rule("CIS-002","AAA configured","high",r"(?im)^\s*aaa new-model\s*$","Configure AAA and validate the intended authentication method."),
Rule("CIS-003","NTP server configured","medium",r"(?im)^\s*ntp server\s+\S+","Configure an approved NTP server."),
Rule("CIS-004","Syslog destination configured","medium",r"(?im)^\s*logging host\s+\S+","Forward logs to an approved central syslog collector."),
Rule("CIS-005","SNMPv3 user or group configured","high",r"(?im)^\s*snmp-server\s+(?:group\s+\S+\s+v3|user\s+\S+\s+\S+\s+v3)\b","Use SNMPv3 authentication and privacy; remove weak community strings."),
Rule("CIS-006","HTTP management disabled","high",r"(?im)^\s*no\s+ip\s+http\s+(?:server|secure-server)\s*$","Disable plaintext HTTP management; retain only approved secure access."),
Rule("CIS-007","BPDU Guard configured","high",r"(?im)^\s*spanning-tree\s+(?:portfast\s+bpduguard\s+default|bpduguard\s+enable)\s*$","Enable BPDU Guard on eligible edge ports after checking topology."),
Rule("CIS-008","DHCP snooping configured","high",r"(?im)^\s*ip\s+dhcp\s+snooping\s*$","Enable DHCP snooping on intended VLANs and trust only approved uplinks."),
Rule("CIS-009","Port security configured","medium",r"(?im)^\s*switchport\s+port-security(?:\s|$)","Apply port security to eligible access interfaces with a deliberate violation action."),
Rule("CIS-010","Trunk VLAN allow-list configured","medium",r"(?im)^\s*switchport\s+trunk\s+allowed\s+vlan\s+","Restrict each trunk to the VLANs it actually needs."),
],
"huawei": [
Rule("HUA-001","SSH/STelnet enabled","high",r"(?im)^\s*stelnet\s+server\s+enable\s*$","Enable secure STelnet only where required and restrict management sources."),
Rule("HUA-002","AAA/account configuration found","high",r"(?im)^\s*(?:aaa\s*$|local-user\s+\S+|domain\s+\S+)\b","Review AAA domains and local accounts; remove unused privileged accounts."),
Rule("HUA-003","NTP server configured","medium",r"(?im)^\s*ntp-service\s+unicast-server\s+\S+","Configure an approved NTP unicast server."),
Rule("HUA-004","Log host configured","medium",r"(?im)^\s*info-center\s+loghost\s+\S+","Forward logs to an approved central log host."),
Rule("HUA-005","SNMPv3 user configured","high",r"(?im)^\s*snmp-agent\s+usm-user\s+v3\s+\S+","Use SNMPv3 authentication and privacy; remove legacy communities."),
Rule("HUA-006","HTTP management disabled","high",r"(?im)^\s*undo\s+http\s+server\s+enable\s*$","Disable the HTTP server; retain only approved secure management."),
Rule("HUA-007","STP BPDU protection configured","high",r"(?im)^\s*stp\s+bpdu-protection(?:\s+enable)?\s*$","Enable BPDU protection on eligible edge ports after validating topology."),
Rule("HUA-008","DHCP snooping configured","high",r"(?im)^\s*dhcp\s+snooping\s+enable\s*$","Enable DHCP snooping on intended VLANs and trust only approved uplinks."),
Rule("HUA-009","Port security configured","medium",r"(?im)^\s*port-security\s+enable\s*$","Apply port security on eligible access interfaces."),
Rule("HUA-010","Trunk VLAN allow-list configured","medium",r"(?im)^\s*port\s+trunk\s+allow-pass\s+vlan\s+","Restrict trunk VLANs to the required set."),
],
"aruba": [
Rule("ARB-001","SSH enabled","high",r"(?im)^\s*ip\s+ssh\s*$","Enable SSH and restrict management access; disable insecure management."),
Rule("ARB-002","AAA authentication configured","high",r"(?im)^\s*(?:aaa\s+authentication|radius-server\s+host|tacacs-server\s+host)\b","Configure and validate the intended AAA/RADIUS/TACACS authentication path."),
Rule("ARB-003","NTP/SNTP server configured","medium",r"(?im)^\s*(?:sntp\s+unicast|ntp\s+server)\s+\S+","Configure an approved time server."),
Rule("ARB-004","Syslog server configured","medium",r"(?im)^\s*logging\s+\S+","Forward logs to an approved central syslog collector."),
Rule("ARB-005","SNMPv3 configured","high",r"(?im)^\s*snmpv3\s+(?:user|group)\s+\S+","Use SNMPv3 with authentication and privacy."),
Rule("ARB-006","Plaintext web management disabled","high",r"(?im)^\s*no\s+web-management\s*$","Disable plaintext web management; use approved secure management."),
Rule("ARB-007","BPDU protection configured","high",r"(?im)^\s*spanning-tree\s+bpdu-protection\s*$","Enable BPDU protection on eligible edge ports."),
Rule("ARB-008","DHCP snooping configured","high",r"(?im)^\s*dhcp-snooping\s*$","Enable DHCP snooping and trust only intended uplinks."),
Rule("ARB-009","Port security configured","medium",r"(?im)^\s*port-security\s*$","Apply port security to eligible access ports."),
Rule("ARB-010","Trunk VLAN allow-list configured","medium",r"(?im)^\s*(?:tagged|trunk)\s+\S+","Review tagged VLAN membership and remove unnecessary VLANs."),
]}

RISK_RULES = {
"cisco": [
Rule("CIS-R01","Telnet management allowed","high",r"(?im)^\s*transport input\s+.*\btelnet\b","Remove Telnet from VTY transport only after validating SSH access and recovery."),
Rule("CIS-R02","Legacy SNMP community present","high",r"(?im)^\s*snmp-server\s+community\s+\S+","Prefer SNMPv3 authPriv and rotate any exposed community string."),
Rule("CIS-R03","HTTP management enabled","high",r"(?im)^\s*ip\s+http\s+server\s*$","Disable plaintext HTTP management through an approved change."),
],
"huawei": [
Rule("HUA-R01","Telnet management enabled","high",r"(?im)^\s*(?:telnet\s+server\s+enable|protocol\s+inbound\s+telnet)\b","Disable Telnet only after validating secure management access."),
Rule("HUA-R02","Legacy SNMP community present","high",r"(?im)^\s*snmp-agent\s+community\s+(?:read|write)\b","Prefer SNMPv3 authPriv and rotate any exposed community string."),
Rule("HUA-R03","HTTP management enabled","high",r"(?im)^\s*http\s+server\s+enable\s*$","Disable plaintext HTTP management through an approved change."),
],
"aruba": [
Rule("ARB-R01","Telnet management enabled","high",r"(?im)^\s*telnet-server\s+enable\s*$","Disable Telnet only after validating secure management access."),
Rule("ARB-R02","Legacy SNMP community present","high",r"(?im)^\s*snmp-server\s+community\s+\S+","Prefer SNMPv3 authPriv and rotate any exposed community string."),
Rule("ARB-R03","Plaintext web management enabled","high",r"(?im)^\s*web-management\s*$","Disable plaintext web management through an approved change."),
]}

SECRET_PATTERNS = (
    re.compile(r"(?i)(\bsnmp-agent\s+community\s+(?:read|write)\s+(?:cipher|simple)\s+)(\S+)"),
    re.compile(r"(?i)((?:^|\s)(?:password|passwd|secret|authentication-key|privacy-key|key-string)\s+(?:\d+\s+)?)(\S+)"),
    re.compile(r"(?i)(\bsnmp-server\s+community\s+)(\S+)"),
    re.compile(r"(?i)(\b(?:pre-shared-key|psk)\s+)(\S+)"),
)

def redact_line(line: str) -> str:
    safe=line.strip()
    for pattern in SECRET_PATTERNS:
        safe=pattern.sub(r"\1[REDACTED]",safe)
    return safe

def _evidence(config: str, pattern: str, limit: int=12) -> list[str]:
    found=[]
    for line in config.splitlines():
        if re.search(pattern,line,re.I):
            safe=redact_line(line)
            if safe not in found:
                found.append(safe)
            if len(found)>=limit:
                break
    return found

def detect_vendor(config: str) -> str:
    text=config.casefold()
    if any(x in text for x in ("stelnet server","snmp-agent","port trunk allow-pass","info-center","sysname ","undo http server")):
        return "huawei"
    if any(x in text for x in ("switchport","aaa new-model","ip ssh version","line vty","spanning-tree portfast","ip dhcp snooping")):
        return "cisco"
    if any(x in text for x in ("snmpv3 user","no web-management","sntp unicast","arubaos","procurve","aaa port-access","spanning-tree bpdu-protection")):
        return "aruba"
    raise ValueError("Vendor could not be detected safely; specify --vendor explicitly.")

def audit(config: str, vendor: str="auto") -> dict:
    if not isinstance(config,str) or not config.strip():
        raise ValueError("Configuration text is required.")
    selected=detect_vendor(config) if vendor=="auto" else vendor.lower()
    if selected not in RULES:
        raise ValueError(f"Unsupported vendor: {selected}")
    checks=[]
    for rule in RULES[selected]:
        evidence=_evidence(config,rule.pattern)
        passed=bool(evidence)
        checks.append({"id":rule.rule_id,"title":rule.title,"severity":rule.severity,
                       "status":"pass" if passed else "review",
                       "evidence":evidence,"remediation":"Matching text marker found; validate effective state and scope." if passed else rule.remediation})
    risks=[]
    for rule in RISK_RULES[selected]:
        evidence=_evidence(config,rule.pattern)
        if evidence:
            risks.append({"id":rule.rule_id,"title":rule.title,"severity":rule.severity,
                          "status":"warning","evidence":evidence,"remediation":rule.remediation})
    passed=sum(x["status"]=="pass" for x in checks)
    review=sum(x["status"]=="review" for x in checks)
    return {"product":"NetCmd ConfigGuard Lite","version":"1.1.0","vendor":selected,
            "mode":"offline_read_only_config_text",
            "summary":{"checks":len(checks),"passed":passed,"review":review,"warnings":len(risks)},
            "checks":checks,"risks":risks,
            "limitations":[
                "This audits only the supplied configuration text; it does not connect to a device.",
                "A matching command is not proof that the feature is active, correctly scoped, or operational.",
                "Missing text markers may be false positives for partial, sanitized, or platform-specific configurations.",
                "Validate device model, OS release, interface context, topology and operational state before remediation.",
                "Credential-like values in evidence are redacted; the original configuration is not persisted by this package.",
                "This is a starter baseline, not a compliance certification or penetration test.",
            ]}

def render_markdown(report: dict) -> str:
    lines=[f"# {report['product']} — Audit Report","",f"- Version: {report['version']}",
           f"- Vendor: {report['vendor']}",f"- Mode: {report['mode']}",
           f"- Checks: {report['summary']['checks']} | Pass: {report['summary']['passed']} | Review: {report['summary']['review']} | Warnings: {report['summary']['warnings']}",
           "","## Baseline checks","","| ID | Check | Severity | Result |","|---|---|---|---|"]
    lines += [f"| {x['id']} | {x['title']} | {x['severity']} | {x['status'].upper()} |" for x in report["checks"]]
    for item in report["checks"]:
        lines.extend(["",f"### {item['id']} — {item['title']}",f"- Result: {item['status'].upper()}",
                      f"- Remediation: {item['remediation']}","- Evidence:"])
        lines.extend([f"  - {line}" for line in item["evidence"]] or ["  - No matching line found in the supplied text."])
    lines.extend(["","## Risk indicators",""])
    if not report["risks"]:
        lines.append("No enabled risk indicators matched the supplied text.")
    for item in report["risks"]:
        lines.extend([f"### [{item['severity'].upper()}] {item['id']} — {item['title']}",
                      f"- Remediation: {item['remediation']}","- Evidence:"])
        lines.extend([f"  - {line}" for line in item["evidence"]])
    lines.extend(["","## Limitations"]+[f"- {x}" for x in report["limitations"]]+[""])
    return "\n".join(lines)

def render_html(report: dict) -> str:
    esc=escape
    cards=[]
    for item in report["checks"]+report["risks"]:
        evidence="".join(f"<li><code>{esc(line)}</code></li>" for line in item["evidence"])
        if not evidence:
            evidence="<li>No matching line found in the supplied text.</li>"
        cards.append("<article><h2>"+esc(item["title"])+" <small>"+esc(item["status"].upper())+"</small></h2>"
                     "<p>"+esc(item["id"])+" · "+esc(item["severity"])+"</p><p>"+esc(item["remediation"])+"</p><ul>"+evidence+"</ul></article>")
    notes="".join(f"<li>{esc(x)}</li>" for x in report["limitations"])
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>"+esc(report["product"])+"</title>"
            "<style>body{font:16px/1.55 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#172033}"
            "article{border:1px solid #ccd3df;border-radius:10px;padding:1rem;margin:1rem 0}small{font-size:.75rem}"
            "code{overflow-wrap:anywhere;background:#f3f5f8;padding:.1rem .25rem}</style><body><h1>"+esc(report["product"])+"</h1>"
            "<p>Vendor: "+esc(report["vendor"])+" | Checks: "+str(report["summary"]["checks"])+" | Warnings: "+str(report["summary"]["warnings"])+"</p>"
            "<blockquote>Offline, read-only analysis of the supplied text only. Not a live-device assessment or certification.</blockquote>"
            +"".join(cards)+"<h2>Limitations</h2><ul>"+notes+"</ul></body></html>")

def main(argv: Iterable[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Offline read-only Cisco/Huawei/Aruba configuration baseline auditor")
    parser.add_argument("config")
    parser.add_argument("--vendor",choices=["auto","cisco","huawei","aruba"],default="auto")
    parser.add_argument("--format",choices=["markdown","json","html"],default="markdown")
    parser.add_argument("--output")
    args=parser.parse_args(argv)
    try:
        report=audit(Path(args.config).read_text(encoding="utf-8",errors="replace"),args.vendor)
        output=json.dumps(report,ensure_ascii=False,indent=2) if args.format=="json" else render_html(report) if args.format=="html" else render_markdown(report)
        if args.output: Path(args.output).write_text(output,encoding="utf-8")
        else: print(output,end="" if output.endswith("\n") else "\n")
        return 0
    except (OSError,ValueError) as exc:
        print(f"error: {exc}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
