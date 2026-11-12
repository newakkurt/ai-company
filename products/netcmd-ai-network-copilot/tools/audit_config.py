#!/usr/bin/env python3
"""Offline, read-only evidence checker for sanitized network configuration exports.

This tool never connects to devices, executes commands, or changes configuration.
A missing indicator is reported as NOT_EVIDENCED, not as proof that a control is absent.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

VENDORS = ("auto", "cisco", "huawei", "aruba")


@dataclass(frozen=True)
class Rule:
    control: str
    positive: tuple[str, ...]
    disabled: tuple[str, ...] = ()


RULES = {
    "cisco": (
        Rule("AAA", (r"^\s*aaa\s+new-model\b", r"^\s*aaa\s+authentication\b", r"^\s*aaa\s+authorization\b")),
        Rule("NTP", (r"^\s*ntp\s+(?:server|peer)\b",)),
        Rule("Central logging", (r"^\s*logging\s+(?:host|\d|buffered|trap)\b",)),
        Rule("SNMPv3", (r"^\s*snmp-server\s+(?:group|user)\b.*\bv3\b",)),
        Rule("SSH management", (r"^\s*ip\s+ssh\s+version\s+[12]", r"^\s*transport\s+input\s+ssh\b")),
        Rule("BPDU Guard", (r"^\s*spanning-tree\s+bpduguard\s+enable\b",)),
        Rule("DHCP Snooping", (r"^\s*ip\s+dhcp\s+snooping\b",)),
        Rule("Port Security", (r"^\s*switchport\s+port-security\b",)),
    ),
    "huawei": (
        Rule("AAA", (r"^\s*aaa\s*$", r"^\s*authentication-scheme\s+\S+", r"^\s*authorization-scheme\s+\S+")),
        Rule("NTP", (r"^\s*ntp-service\s+(?:unicast-server|ipv6\s+unicast-server)\b",)),
        Rule("Central logging", (r"^\s*info-center\s+(?:loghost|logbuffer|source)\b",)),
        Rule("SNMPv3", (r"^\s*snmp-agent\s+usm-user\s+v3\b",)),
        Rule("SSH management", (r"^\s*stelnet\s+server\s+enable\b", r"^\s*ssh\s+server\b")),
        Rule("BPDU Protection", (r"^\s*stp\s+bpdu-protection\b",)),
        Rule("DHCP Snooping", (r"^\s*dhcp\s+snooping\s+enable\b",)),
        Rule("Port Security", (r"^\s*port-security\s+enable\b",)),
    ),
    "aruba": (
        Rule("AAA", (r"^\s*aaa\s+authentication\b", r"^\s*aaa\s+authorization\b")),
        Rule("NTP", (r"^\s*ntp\s+server\b", r"^\s*timesync\s+ntp\b")),
        Rule("Central logging", (r"^\s*logging\s+(?:\d|host|facility)\b",)),
        Rule("SNMPv3", (r"^\s*snmpv3\s+(?:user|group)\b",)),
        Rule("SSH management", (r"^\s*ip\s+ssh\b", r"^\s*crypto\s+key\s+generate\s+ssh\b")),
        Rule("BPDU Protection", (r"^\s*(?:spanning-tree\s+bpdu-protection|bpdu-protection)\b",)),
        Rule("DHCP Snooping", (r"^\s*(?:dhcp-snooping|ip\s+dhcp-snooping)\b",)),
        Rule("Port Security", (r"^\s*(?:port-security|port-security\s+enable)\b",)),
    ),
}


def detect_vendor(text: str) -> str:
    sample = text.lower()
    if any(token in sample for token in ("sysname ", "info-center ", "snmp-agent ", "stelnet ")):
        return "huawei"
    if any(token in sample for token in ("hostname ", "switchport ", "snmp-server ", "aaa new-model")):
        return "cisco"
    if any(token in sample for token in ("aruba", "vsf ", "timesync ntp", "snmpv3 user")):
        return "aruba"
    return "unknown"


def evaluate(text: str, vendor: str) -> list[dict[str, object]]:
    if vendor == "auto":
        vendor = detect_vendor(text)
    if vendor not in RULES:
        return [{"control": "Vendor detection", "status": "UNKNOWN", "evidence_lines": []}]
    lines = text.splitlines()
    results = []
    for rule in RULES[vendor]:
        positives = [i for i, line in enumerate(lines, 1)
                     if any(re.search(pattern, line, re.IGNORECASE) for pattern in rule.positive)]
        disabled = [i for i, line in enumerate(lines, 1)
                    if any(re.search(pattern, line, re.IGNORECASE) for pattern in rule.disabled)]
        if positives and not disabled:
            status = "EVIDENCED"
            evidence = positives[:5]
        elif disabled:
            status = "REVIEW"
            evidence = disabled[:5]
        else:
            status = "NOT_EVIDENCED"
            evidence = []
        results.append({"control": rule.control, "status": status, "evidence_lines": evidence})
    return results


def build_report(path: Path, vendor: str, text: str) -> str:
    selected_vendor = detect_vendor(text) if vendor == "auto" else vendor
    results = evaluate(text, selected_vendor)
    counts = {key: sum(item["status"] == key for item in results)
              for key in ("EVIDENCED", "REVIEW", "NOT_EVIDENCED", "UNKNOWN")}
    lines = [
        "# NetCmd AI Network Copilot — Configuration Evidence Report",
        "",
        f"- Source file: `{path.name}`",
        f"- Vendor: **{selected_vendor.upper()}**",
        f"- Generated (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "- Mode: offline / read-only; no device connection or configuration change",
        "",
        "## Summary",
        "",
        f"- EVIDENCED: {counts['EVIDENCED']}",
        f"- REVIEW: {counts['REVIEW']}",
        f"- NOT_EVIDENCED: {counts['NOT_EVIDENCED']}",
        f"- UNKNOWN: {counts['UNKNOWN']}",
        "",
        "## Control evidence",
        "",
        "| Control | Result | Evidence line(s) |",
        "|---|---|---|",
    ]
    for item in results:
        evidence = ", ".join(str(n) for n in item["evidence_lines"]) or "—"
        lines.append(f"| {item['control']} | **{item['status']}** | {evidence} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- EVIDENCED means a matching configuration line was found; it does not prove the control is effective.",
        "- NOT_EVIDENCED means this export did not contain a recognized indicator; it is not proof the control is absent.",
        "- REVIEW means a recognized exception/disable indicator was found, or manual review is required.",
        "- Validate syntax against the exact vendor, model and software release.",
        "- This report is not a penetration test, compliance certification or security guarantee.",
        "- Review all findings with the network owner before any change. This tool never applies changes.",
        "",
        "## Data handling",
        "",
        "The report intentionally does not copy configuration lines, credentials, IP addresses or secrets.",
        "Use sanitized evidence only and keep the original export in the customer's approved storage.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline network configuration evidence checker")
    parser.add_argument("config", type=Path, help="Path to a sanitized text configuration export")
    parser.add_argument("--vendor", choices=VENDORS, default="auto", help="Vendor family (default: auto)")
    parser.add_argument("--output", type=Path, default=Path("netcmd-audit-report.md"))
    args = parser.parse_args()
    if not args.config.is_file():
        parser.error(f"configuration file not found: {args.config}")
    text = args.config.read_text(encoding="utf-8", errors="replace")
    report = build_report(args.config, args.vendor, text)
    args.output.write_text(report, encoding="utf-8")
    print(f"Report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
