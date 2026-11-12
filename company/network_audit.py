"""Read-only, evidence-backed network configuration audit."""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
from html import escape
import json
from pathlib import Path
import re
from typing import Iterable

SECRET_PATTERNS = (
    re.compile(r"(?i)(\b(?:password|passwd|secret|community|authentication-key|privacy-key|key-string)\s+(?:\d+\s+)?)(\S+)"),
    re.compile(r"(?i)(\b(?:snmp-server\s+community|snmp-agent\s+community)\s+(?:read|write)\s+)(\S+)"),
    re.compile(r"(?i)(\b(?:pre-shared-key|psk)\s+)(\S+)"),
)
NEGATIVE_PREFIXES = ("undo ", "no ", "disable ")
VENDOR_ALIASES = {"cisco":"cisco","huawei":"huawei","aruba":"aruba","procurve":"aruba","aruba_or_legacy_procurve":"aruba","unknown":"unknown"}

@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: str
    title: str
    detail: str
    evidence: tuple[str, ...]
    recommendation: str

@dataclass(frozen=True)
class AuditResult:
    vendor: str
    findings: tuple[Finding, ...]
    notes: tuple[str, ...]

    @property
    def severity_counts(self):
        counts = {key: 0 for key in ("critical","high","medium","low","info")}
        for item in self.findings:
            counts[item.severity] = counts.get(item.severity, 0) + 1
        return counts

    def to_dict(self):
        return {"vendor":self.vendor,"finding_count":len(self.findings),"severity_counts":self.severity_counts,
                "findings":[asdict(item) for item in self.findings],"notes":list(self.notes),
                "mode":"read_only_text_analysis"}

    def render_markdown(self, title="Network Configuration Audit"):
        lines=[f"# {title}","",f"- Vendor: {self.vendor}",f"- Findings: {len(self.findings)}",
               "- Mode: Read-only text analysis","",
               "> This report analyzes only the supplied text. It is not a live-device assessment, penetration test, certification, or proof that an absent directive is absent on the running device.","",
               "## Findings",""]
        if not self.findings:
            lines.append("No findings were produced by the enabled text checks. This does not prove the device is secure.")
        for n,item in enumerate(self.findings,1):
            lines.extend([f"### {n}. [{item.severity.upper()}] {item.title}","",
                          f"- Check: {item.check_id}",f"- Detail: {item.detail}",
                          f"- Recommendation: {item.recommendation}","- Evidence:"])
            lines.extend([f"  - {line}" for line in item.evidence] or ["  - No matching active directive was found in the supplied text."])
            lines.append("")
        lines.extend(["## Scope and limitations",""])
        lines.extend(f"- {note}" for note in self.notes)
        lines.extend(["- Review findings with the network owner before making changes.",
                      "- Any remediation requires change approval, backup, and rollback planning.",""])
        return "\n".join(lines)

    def render_html(self, title="Network Configuration Audit"):
        esc=escape
        cards=[]
        for item in self.findings:
            evidence="".join(f"<li><code>{esc(line)}</code></li>" for line in item.evidence)
            if not evidence:
                evidence="<li>No matching active directive was found in the supplied text.</li>"
            cards.append("<article><h2>"+esc(item.title)+" <small>"+esc(item.severity.upper())+"</small></h2>"
                         "<p><b>Check:</b> "+esc(item.check_id)+"</p><p>"+esc(item.detail)+"</p>"
                         "<p><b>Recommendation:</b> "+esc(item.recommendation)+"</p><ul>"+evidence+"</ul></article>")
        notes="".join(f"<li>{esc(note)}</li>" for note in self.notes)
        return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>"+esc(title)+"</title>"
                "<style>body{font:16px/1.55 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#172033}"
                "article{border:1px solid #ccd3df;border-radius:10px;padding:1rem;margin:1rem 0}small{font-size:.75rem}"
                "code{overflow-wrap:anywhere;background:#f3f5f8;padding:.1rem .25rem}</style><body><h1>"+esc(title)+"</h1>"
                "<p>Vendor: "+esc(self.vendor)+" | Findings: "+str(len(self.findings))+" | Read-only text analysis</p>"
                "<blockquote>This report analyzes only the supplied text. It is not a live-device assessment or certification.</blockquote>"
                "<h2>Findings</h2>"+("".join(cards) if cards else "<p>No findings were produced. This does not prove the device is secure.</p>")
                +"<h2>Scope and limitations</h2><ul>"+notes+"</ul></body></html>")

def redact_evidence(line: str) -> str:
    safe=line.strip()
    for pattern in SECRET_PATTERNS:
        safe=pattern.sub(r"\1[REDACTED]",safe)
    return safe

def _is_active(line: str) -> bool:
    return not line.strip().casefold().startswith(NEGATIVE_PREFIXES)

def _matching_lines(lines: Iterable[str], patterns: tuple[str,...]) -> tuple[str,...]:
    result=[]
    for line in lines:
        if _is_active(line) and any(re.search(pattern,line,re.I) for pattern in patterns):
            safe=redact_evidence(line)
            if safe not in result:
                result.append(safe)
    return tuple(result[:20])

def detect_vendor(config: str) -> str:
    text=config.casefold()
    if any(x in text for x in ("sysname ","undo ","interface vlanif","port link-type","snmp-agent ","stelnet server")):
        return "huawei"
    if any(x in text for x in ("switchport ","line vty","aaa new-model","spanning-tree portfast","ip dhcp snooping","router ospf")):
        return "cisco"
    if any(x in text for x in ("aruba","procurve","aaa port-access","vlan access ","spanning-tree bpdu-protection")):
        return "aruba"
    return "unknown"

def _normalize_vendor(value: str) -> str:
    normalized=str(value or "unknown").strip().casefold()
    if normalized not in VENDOR_ALIASES:
        raise ValueError("Vendor must be cisco, huawei, aruba, or unknown")
    return VENDOR_ALIASES[normalized]

def _interface_blocks(lines: list[str]) -> list[tuple[str,list[str]]]:
    blocks=[]; name=None; body=[]
    for raw in lines:
        line=raw.strip()
        if re.match(r"^interface\s+\S+",line,re.I):
            if name is not None: blocks.append((name,body))
            name=line.split(None,1)[1]; body=[]
        elif line.casefold() in {"!","quit","exit","end"} and name is not None:
            blocks.append((name,body)); name=None; body=[]
        elif name is not None:
            body.append(line)
    if name is not None: blocks.append((name,body))
    return blocks

def _is_physical_interface(name: str, vendor: str) -> bool:
    value=name.casefold().replace(" ","")
    if value.startswith(("vlan","vlanif","loopback","null","tunnel","mgmt","management")):
        return False
    patterns={
        "huawei":r"^(?:gigabitethernet|xgigabitethernet|10ge|25ge|40ge|100ge|ge|eth-trunk)",
        "cisco":r"^(?:fastethernet|gigabitethernet|tengigabitethernet|twentyfivegig|fortygig|hundredgig|ethernet|gi\d|fa\d|te\d)",
        "aruba":r"^(?:\d+/\d+/\d+|[a-z]\d+|trk\d+|lag\d+|ethernet\d)",
    }
    return bool(re.match(patterns.get(vendor,r"^(?:gigabitethernet|fastethernet|xgigabitethernet|10ge|ge\d|gi\d|fa\d|\d+/\d+/\d+)"),value))

def audit_config(config: str, vendor: str | None = None) -> AuditResult:
    if not isinstance(config,str) or not config.strip():
        raise ValueError("Configuration text is required")
    lines=[line.strip() for line in config.splitlines() if line.strip()]
    detected=_normalize_vendor(vendor if vendor is not None else detect_vendor(config))
    findings=[]
    notes=[
        "Analysis is limited to the supplied text; sanitized, partial, or truncated configs can create false positives and false negatives.",
        "No device connection, command execution, configuration change, credential validation, or shutdown action is performed.",
        "Credential-like values are redacted from report evidence. The original configuration is not stored by this module.",
        "Reachability, effective policy, hardware state, software version, and runtime behavior cannot be established from a text file alone.",
    ]
    checks=[
        ("management.ntp","NTP configuration not found","medium",(r"\bntp\b",r"ntp-service",r"\bsntp\b"),"Confirm approved time sources are configured, reachable, and monitored."),
        ("management.logging","Remote logging configuration not found","medium",(r"\blogging\s+(?:host|server|\d)",r"info-center\s+loghost",r"logging\s+\S+"),"Confirm logs are sent to the approved central collector and delivery is monitored."),
        ("management.aaa","Centralized AAA configuration not found","medium",(r"\baaa\b",r"authentication-scheme",r"radius-server",r"tacacs"),"Review centralized authentication, authorization, accounting, and local break-glass access."),
        ("management.ssh","SSH management configuration not found","medium",(r"\bip ssh\b",r"\bssh server\b",r"\bstelnet server\b",r"\bssh user\b"),"Confirm SSH is enabled with approved algorithms and management-plane ACLs."),
        ("security.port_security","Port-security directive not found","low",(r"port-security",r"port access security",r"aaa port-access"),"Review edge-port access controls and select a vendor-supported policy."),
        ("security.bpdu_protection","BPDU protection directive not found","low",(r"bpduguard",r"bpdu-protection",r"bpdu protection"),"Review spanning-tree edge-port protection on access-facing interfaces."),
        ("security.dhcp_snooping","DHCP snooping directive not found","low",(r"dhcp snooping",r"dhcp-snooping"),"Review DHCP snooping and trusted uplink configuration where topology supports it."),
    ]
    for check_id,title,severity,patterns,recommendation in checks:
        evidence=_matching_lines(lines,patterns)
        if not evidence:
            findings.append(Finding(check_id,severity,title,
                "No matching active directive was found in the supplied configuration text; this is not proof the control is absent on the live device.",
                (),recommendation))
    telnet=_matching_lines(lines,(r"transport input\s+.*\btelnet\b",r"telnet server enable",r"protocol inbound\s+telnet"))
    if telnet:
        findings.append(Finding("management.telnet","high","Telnet management directive found",
            "The supplied text contains an active directive that may permit unencrypted management access.",
            telnet,"Verify exposure and migrate to SSH through an approved change; do not remove access without a tested recovery path."))
    community=_matching_lines(lines,(r"snmp-server\s+community",r"snmp-agent\s+community"))
    if community:
        findings.append(Finding("management.snmp_community","medium","SNMP community string directive found",
            "An SNMP community directive is present; the value is redacted. Verify whether this is legacy SNMPv1/v2c and whether SNMPv3 is available.",
            community,"Prefer SNMPv3 authPriv, restrict manager source addresses, and rotate any exposed community string."))
    blocks=_interface_blocks(lines)
    candidates=[]
    for name,body in blocks:
        if not _is_physical_interface(name,detected): continue
        has_description=any(re.match(r"^(?:description|name|port-name)\s+\S+",x,re.I) for x in body)
        is_down=any(re.match(r"^(?:shutdown|disable)$",x,re.I) for x in body)
        if not has_description and not is_down: candidates.append("interface "+name)
    if candidates:
        findings.append(Finding("interfaces.missing_description","low","Physical interfaces without descriptions found",
            f"{len(candidates)} physical interface block(s) have no description/name directive in the supplied text.",
            tuple(candidates[:50]),"Confirm each port's owner and purpose, then document it; do not infer an undocumented port is unused."))
    if not blocks: notes.append("No interface blocks were parsed; interface-level checks were skipped.")
    if detected=="unknown": notes.append("Vendor could not be identified confidently; generic text checks only were applied.")
    return AuditResult(detected,tuple(findings),tuple(notes))

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Read-only text audit for Cisco, Huawei, and Aruba switch configs.")
    parser.add_argument("--input",required=True,help="Path to a customer-supplied configuration text file.")
    parser.add_argument("--vendor",choices=("auto","cisco","huawei","aruba","unknown"),default="auto")
    parser.add_argument("--format",choices=("markdown","html","json"),default="markdown")
    parser.add_argument("--output",help="Optional report path. Defaults to stdout.")
    args=parser.parse_args(argv)
    config=Path(args.input).read_text(encoding="utf-8",errors="replace")
    result=audit_config(config,None if args.vendor=="auto" else args.vendor)
    if args.format=="json": output=json.dumps(result.to_dict(),ensure_ascii=False,indent=2)+"\n"
    elif args.format=="html": output=result.render_html()
    else: output=result.render_markdown()
    if args.output: Path(args.output).write_text(output,encoding="utf-8")
    else: print(output)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
